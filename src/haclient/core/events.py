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
    """

    def __init__(self, ws: WebSocketPort) -> None:
        self._ws = ws
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._subscription_ids: dict[str, int] = {}
        self._buffers: dict[str, deque[dict[str, Any]]] = {}
        self._started = False

    def subscribe(self, event_type: str, handler: EventHandler) -> EventHandler:
        """Register *handler* for the given *event_type*.

        Subscriptions registered before `start` are batched; those added
        afterwards trigger an immediate WebSocket subscribe if it is the
        first handler for the type.

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
        """
        first_for_type = event_type not in self._handlers
        self._handlers[event_type].append(handler)
        if self._started and first_for_type:
            # Subscribe lazily; the WS adapter handles re-subscription on reconnect.
            import asyncio

            asyncio.ensure_future(self._ensure_subscription(event_type))
        return handler

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        """Remove a previously registered handler.

        If the last handler for *event_type* is removed the WebSocket
        subscription is also cancelled.

        Parameters
        ----------
        event_type : str
            The Home Assistant event type to unsubscribe from.
        handler : callable
            The exact handler previously passed to `subscribe`. Removing
            an unknown handler is a no-op.
        """
        handlers = self._handlers.get(event_type)
        if not handlers:
            return
        try:
            handlers.remove(handler)
        except ValueError:
            return
        if not handlers:
            self._handlers.pop(event_type, None)
            sub_id = self._subscription_ids.pop(event_type, None)
            if sub_id is not None and self._ws.connected:
                import asyncio

                asyncio.ensure_future(self._safe_unsubscribe(sub_id))

    async def _safe_unsubscribe(self, sub_id: int) -> None:
        """Unsubscribe, swallowing transport errors."""
        try:
            await self._ws.unsubscribe(sub_id)
        except Exception:  # noqa: BLE001 - defensive
            _LOGGER.debug("EventBus failed to unsubscribe %s", sub_id, exc_info=True)

    async def start(self) -> None:
        """Subscribe to every registered event type and arm reconnect.

        Safe to call multiple times.
        """
        if self._started:
            return
        for event_type in list(self._handlers.keys()):
            await self._ensure_subscription(event_type)
        self._started = True

    async def _ensure_subscription(self, event_type: str) -> None:
        """Subscribe on the WS if not already subscribed."""
        if event_type in self._subscription_ids:
            return
        try:
            sub_id = await self._ws.subscribe_events(self._make_dispatcher(event_type), event_type)
        except Exception:
            _LOGGER.exception("EventBus failed to subscribe to %s", event_type)
            return
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
