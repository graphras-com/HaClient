"""`EventBus` — typed event subscriptions over a `WebSocketPort`.

The bus tracks per-event-type subscriptions and dispatches each incoming
event to every registered handler. It also exposes a buffering mode used
by `StateStore` during initial state priming to fix the race between the
REST snapshot and the first incoming event.

Lifecycle
---------
1. Constructed with a `WebSocketPort`.
2. After the WS connects, call `start` to subscribe to all desired event
   types in a single batch.
3. While priming, call `enable_buffering(event_type)` to capture matching
   events into an in-memory queue. Drain with `drain_buffer(event_type)`.
4. Reconnect re-subscriptions are handled automatically by the underlying
   `WebSocketPort.on_reconnect` hook installed by `start`.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections import defaultdict, deque
from collections.abc import Awaitable
from typing import Any

from haclient.ports import EventHandler, WebSocketPort

_LOGGER = logging.getLogger(__name__)


class EventBus:
    """Pub/sub facade over a `WebSocketPort`.

    Parameters
    ----------
    ws : WebSocketPort
        The transport used to subscribe to Home Assistant events.

    Notes
    -----
    Subscriptions can fail at the transport layer. The bus exposes two
    APIs to handle this:

    * `subscribe` / `unsubscribe` — fire-and-forget; failures are logged
      and recorded on the bus so callers can inspect them via
      `subscription_failure` and `pending_subscription`.
    * `subscribe_async` / `unsubscribe_async` — awaitable; transport
      errors are raised to the caller. Prefer these whenever the caller
      needs confirmation that Home Assistant actually accepted the
      subscription.
    """

    def __init__(self, ws: WebSocketPort) -> None:
        self._ws = ws
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._subscription_ids: dict[str, int] = {}
        self._buffers: dict[str, deque[dict[str, Any]]] = {}
        self._started = False
        # Per-event-type background subscription task scheduled by the
        # fire-and-forget `subscribe()` path. Replaced (and the previous
        # task discarded) on each new attempt.
        self._pending_subscriptions: dict[str, asyncio.Task[None]] = {}
        # Last subscription failure observed for a given event type via
        # the fire-and-forget path. Cleared on a successful retry.
        self._subscription_failures: dict[str, BaseException] = {}

    def subscribe(self, event_type: str, handler: EventHandler) -> EventHandler:
        """Register *handler* for the given *event_type*.

        Subscriptions registered before `start` are batched; those added
        afterwards trigger an immediate WebSocket subscribe if it is the
        first handler for the type. The scheduled task is tracked so
        callers can await it (`pending_subscription`) or inspect its
        outcome (`subscription_failure`).

        Parameters
        ----------
        event_type : str
            The Home Assistant event type.
        handler : callable
            Sync or async callable receiving the event dict.

        Returns
        -------
        callable
            The same *handler*, for use as a decorator.

        Notes
        -----
        This method does not raise transport errors. Use
        `subscribe_async` when the caller needs to know whether Home
        Assistant accepted the subscription.
        """
        first_for_type = event_type not in self._handlers
        self._handlers[event_type].append(handler)
        if self._started and first_for_type:
            # Subscribe lazily; the WS adapter handles re-subscription on reconnect.
            task = asyncio.ensure_future(self._ensure_subscription(event_type))
            self._pending_subscriptions[event_type] = task

            def _done(t: asyncio.Task[None], et: str = event_type) -> None:
                self._on_subscription_task_done(et, t)

            task.add_done_callback(_done)
        return handler

    async def subscribe_async(self, event_type: str, handler: EventHandler) -> EventHandler:
        """Register *handler* and await the underlying WebSocket subscribe.

        Like `subscribe`, but transport failures propagate to the caller
        and the handler is rolled back if the first subscribe for an
        event type fails — so callers can rely on the returned handler
        being live.

        Parameters
        ----------
        event_type : str
            The Home Assistant event type.
        handler : callable
            Sync or async callable receiving the event dict.

        Returns
        -------
        callable
            The registered handler.

        Raises
        ------
        Exception
            Any exception raised by the underlying `WebSocketPort` when
            the first handler for *event_type* triggers a subscribe.
        """
        first_for_type = event_type not in self._handlers
        self._handlers[event_type].append(handler)
        if not (self._started and first_for_type):
            return handler
        try:
            await self._subscribe_now(event_type)
        except BaseException:
            # Roll back the handler so the caller's view is consistent
            # with the transport state.
            handlers = self._handlers.get(event_type)
            if handlers is not None:
                with contextlib.suppress(ValueError):  # pragma: no cover - defensive
                    handlers.remove(handler)
                if not handlers:
                    self._handlers.pop(event_type, None)
            raise
        return handler

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        """Remove a previously registered handler.

        If the last handler for *event_type* is removed the WebSocket
        subscription is also cancelled in the background.

        Parameters
        ----------
        event_type : str
            The Home Assistant event type to unsubscribe from.
        handler : callable
            The exact handler previously passed to `subscribe`. Removing
            an unknown handler is a no-op.
        """
        sub_id = self._drop_handler(event_type, handler)
        if sub_id is not None and self._ws.connected:
            asyncio.ensure_future(self._safe_unsubscribe(sub_id))

    async def unsubscribe_async(self, event_type: str, handler: EventHandler) -> None:
        """Remove a handler and await any resulting WebSocket unsubscribe.

        Unlike `unsubscribe`, transport errors raised while telling Home
        Assistant to stop sending events propagate to the caller.

        Parameters
        ----------
        event_type : str
            The Home Assistant event type to unsubscribe from.
        handler : callable
            The exact handler previously passed to `subscribe` or
            `subscribe_async`. Removing an unknown handler is a no-op.

        Raises
        ------
        Exception
            Any exception raised by `WebSocketPort.unsubscribe`.
        """
        sub_id = self._drop_handler(event_type, handler)
        if sub_id is not None and self._ws.connected:
            await self._ws.unsubscribe(sub_id)

    def _drop_handler(self, event_type: str, handler: EventHandler) -> int | None:
        """Remove *handler* and return the WS subscription id to release.

        Returns ``None`` if the handler was unknown or other handlers
        remain for *event_type*.
        """
        handlers = self._handlers.get(event_type)
        if not handlers:
            return None
        try:
            handlers.remove(handler)
        except ValueError:
            return None
        if handlers:
            return None
        self._handlers.pop(event_type, None)
        return self._subscription_ids.pop(event_type, None)

    def subscription_failure(self, event_type: str) -> BaseException | None:
        """Return the last fire-and-forget subscribe failure, if any.

        Parameters
        ----------
        event_type : str
            The event type to inspect.

        Returns
        -------
        BaseException or None
            The exception raised by the most recent fire-and-forget
            subscribe attempt, or ``None`` if the current subscription
            is healthy (or no attempt has been made).
        """
        return self._subscription_failures.get(event_type)

    def pending_subscription(self, event_type: str) -> asyncio.Task[None] | None:
        """Return the in-flight subscribe task for *event_type*, if any.

        Awaiting the returned task lets callers convert a fire-and-forget
        `subscribe` into a confirmed registration without changing the
        original call site.

        Parameters
        ----------
        event_type : str
            The event type whose pending subscribe task to return.

        Returns
        -------
        asyncio.Task or None
            The scheduled task, or ``None`` if no subscribe is in flight
            for *event_type*.
        """
        task = self._pending_subscriptions.get(event_type)
        if task is None or task.done():
            return None
        return task

    def _on_subscription_task_done(self, event_type: str, task: asyncio.Task[None]) -> None:
        """Record the outcome of a fire-and-forget subscribe task."""
        # Only forget the task if it is still the registered one — a
        # later attempt may have replaced it.
        if self._pending_subscriptions.get(event_type) is task:
            self._pending_subscriptions.pop(event_type, None)
        if task.cancelled():
            return
        exc = task.exception()
        if exc is None:
            # Success: clear any stale failure.
            self._subscription_failures.pop(event_type, None)
        else:
            self._subscription_failures[event_type] = exc

    async def _safe_unsubscribe(self, sub_id: int) -> None:
        """Unsubscribe, swallowing transport errors."""
        try:
            await self._ws.unsubscribe(sub_id)
        except Exception:  # noqa: BLE001 - defensive
            _LOGGER.debug("EventBus failed to unsubscribe %s", sub_id, exc_info=True)

    async def start(self) -> None:
        """Subscribe to every registered event type and arm reconnect.

        Safe to call multiple times.

        Notes
        -----
        Transport failures during the initial batch are recorded on the
        bus (see `subscription_failure`) but not raised, so a single
        flaky event type does not abort startup. Use `subscribe_async`
        afterwards if you need confirmation that a specific subscription
        is live.
        """
        if self._started:
            return
        for event_type in list(self._handlers.keys()):
            try:
                await self._ensure_subscription(event_type)
            except Exception:  # noqa: BLE001 - logged & recorded by _ensure_subscription
                continue
        self._started = True

    async def _ensure_subscription(self, event_type: str) -> None:
        """Subscribe on the WS, logging transport errors and recording them.

        Used by `start` and by the fire-and-forget `subscribe` path. The
        exception is re-raised so the post-start path's task done
        callback can store it on `_subscription_failures`; the `start`
        path catches it again to preserve the historic "start never
        raises on subscribe failure" behaviour, but still records the
        failure for observability.
        """
        try:
            await self._subscribe_now(event_type)
        except Exception as exc:
            _LOGGER.exception("EventBus failed to subscribe to %s", event_type)
            self._subscription_failures[event_type] = exc
            raise

    async def _subscribe_now(self, event_type: str) -> None:
        """Subscribe on the WS, propagating transport errors.

        Used by `subscribe_async` and (indirectly) by
        `_ensure_subscription`. Idempotent — returns immediately if a
        subscription id is already recorded for *event_type*.
        """
        if event_type in self._subscription_ids:
            return
        sub_id = await self._ws.subscribe_events(self._make_dispatcher(event_type), event_type)
        self._subscription_ids[event_type] = sub_id

    def _make_dispatcher(self, event_type: str) -> EventHandler:
        """Return a handler that buffers or fans out events for *event_type*."""

        def dispatch(event: dict[str, Any]) -> Awaitable[None] | None:
            buffer = self._buffers.get(event_type)
            if buffer is not None:
                buffer.append(event)
                return None
            return self._fanout(event_type, event)

        return dispatch

    async def _fanout(self, event_type: str, event: dict[str, Any]) -> None:
        """Invoke every handler registered for *event_type*."""
        for handler in list(self._handlers.get(event_type, [])):
            try:
                result = handler(event)
                if hasattr(result, "__await__"):
                    await result  # type: ignore[misc]
            except Exception:  # pragma: no cover - defensive
                _LOGGER.exception("Event handler raised for %s", event_type)

    def enable_buffering(self, event_type: str) -> None:
        """Begin buffering events of *event_type* instead of dispatching them.

        Used by `StateStore` while the initial REST snapshot is being
        applied. Idempotent.

        Parameters
        ----------
        event_type : str
            Event type whose incoming frames should be queued in memory
            until `drain_buffer` (or `discard_buffer`) is called.
        """
        self._buffers.setdefault(event_type, deque())

    async def drain_buffer(self, event_type: str) -> None:
        """Stop buffering and dispatch any accumulated events.

        Parameters
        ----------
        event_type : str
            The event type whose buffer should be drained.
        """
        buffer = self._buffers.pop(event_type, None)
        if buffer is None:
            return
        while buffer:
            event = buffer.popleft()
            await self._fanout(event_type, event)

    def discard_buffer(self, event_type: str) -> None:
        """Drop any buffered events for *event_type* without dispatching."""
        self._buffers.pop(event_type, None)

    def install_reconnect_hook(
        self,
        on_reconnect: EventHandler | None = None,
    ) -> None:
        """Wire the bus into the WebSocket reconnect lifecycle.

        After a reconnect, the underlying WS adapter re-subscribes for us
        (it stores the original handlers). All we need to do is invoke the
        optional *on_reconnect* callback (e.g. `StateStore.refresh_all`).

        Parameters
        ----------
        on_reconnect : callable or None, optional
            Sync or async callable invoked once the WebSocket reconnects.
            Receives an empty event dict for compatibility with the
            generic event-handler signature. ``None`` (the default) is a
            no-op — useful for callers that only need the WS adapter's
            built-in re-subscription behaviour.
        """
        if on_reconnect is None:
            return

        async def _hook() -> None:
            try:
                result = on_reconnect({})
                if hasattr(result, "__await__"):
                    await result  # type: ignore[misc]
            except Exception:  # pragma: no cover - defensive
                _LOGGER.exception("Reconnect hook raised")

        self._ws.on_reconnect(_hook)
