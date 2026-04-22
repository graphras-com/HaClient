"""Home Assistant WebSocket API client.

The implementation focuses on being robust and test-friendly:

* A single background task (``_reader_task``) consumes the WebSocket.
* All outgoing commands get a monotonically increasing ``id`` and resolve
  through an :class:`asyncio.Future` when the matching ``result`` frame
  arrives.
* A separate ``_keepalive_task`` periodically sends ``ping`` messages.
* If the socket drops unexpectedly an exponential back-off reconnect loop
  restarts the connection, and any previously registered subscriptions are
  re-established transparently.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import random
from collections.abc import Awaitable, Callable
from typing import Any

import aiohttp

from .exceptions import (
    AuthenticationError,
    CommandError,
    ConnectionClosedError,
    HAClientError,
)
from .exceptions import TimeoutError as HATimeoutError

_LOGGER = logging.getLogger(__name__)

EventHandler = Callable[[dict[str, Any]], Awaitable[None] | None]


class WebSocketClient:
    """Async Home Assistant WebSocket client.

    Parameters
    ----------
    url:
        Fully-qualified WebSocket URL (e.g. ``ws://localhost:8123/api/websocket``).
    token:
        Long-lived access token.
    session:
        Optional pre-existing :class:`aiohttp.ClientSession`. If not provided
        one will be created and closed automatically.
    reconnect:
        Whether to reconnect automatically when the socket drops.
    ping_interval:
        Seconds between keepalive pings. Set to ``0`` to disable.
    request_timeout:
        Default timeout (seconds) for individual WebSocket commands.
    """

    def __init__(
        self,
        url: str,
        token: str,
        *,
        session: aiohttp.ClientSession | None = None,
        reconnect: bool = True,
        ping_interval: float = 30.0,
        request_timeout: float = 30.0,
        verify_ssl: bool = True,
    ) -> None:
        self._url = url
        self._token = token
        self._session = session
        self._owns_session = session is None
        self._reconnect = reconnect
        self._ping_interval = ping_interval
        self._request_timeout = request_timeout
        self._verify_ssl = verify_ssl

        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._message_id = 0
        self._pending: dict[int, asyncio.Future[Any]] = {}
        self._pong_waiters: dict[int, asyncio.Future[Any]] = {}
        # id -> handler for subscription/event messages
        self._subscriptions: dict[int, EventHandler] = {}
        # event_type -> (subscription_id, handler) - used for resubscribe
        self._event_subs: dict[str, tuple[int, EventHandler]] = {}
        self._trigger_subs: dict[int, dict[str, Any]] = {}

        self._reader_task: asyncio.Task[None] | None = None
        self._keepalive_task: asyncio.Task[None] | None = None
        self._closing = False
        self._connected = asyncio.Event()
        self._disconnect_listeners: list[Callable[[], Awaitable[None] | None]] = []

    # ---------------------------------------------------------- properties
    @property
    def connected(self) -> bool:
        """Return ``True`` while the underlying socket is open."""
        return self._ws is not None and not self._ws.closed

    # ------------------------------------------------------------- lifecycle
    async def connect(self) -> None:
        """Establish the WebSocket connection and authenticate."""
        if self.connected:
            return
        self._closing = False
        await self._do_connect()
        self._reader_task = asyncio.create_task(self._reader_loop(), name="ha-ws-reader")
        if self._ping_interval > 0:
            self._keepalive_task = asyncio.create_task(
                self._keepalive_loop(), name="ha-ws-keepalive"
            )

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
            self._owns_session = True
        return self._session

    async def _do_connect(self) -> None:
        session = await self._ensure_session()
        try:
            self._ws = await session.ws_connect(
                self._url,
                heartbeat=None,
                ssl=self._verify_ssl,
                autoping=False,
            )
        except aiohttp.ClientError as err:
            raise HAClientError(f"Failed to connect to {self._url}: {err}") from err

        # Auth handshake: auth_required -> auth -> auth_ok | auth_invalid
        msg = await self._recv_json()
        if msg.get("type") != "auth_required":
            raise AuthenticationError(f"Expected auth_required, got {msg.get('type')!r}")
        await self._ws.send_json({"type": "auth", "access_token": self._token})
        msg = await self._recv_json()
        mtype = msg.get("type")
        if mtype == "auth_invalid":
            await self._ws.close()
            raise AuthenticationError(msg.get("message", "Invalid access token"))
        if mtype != "auth_ok":
            raise AuthenticationError(f"Unexpected auth response: {mtype!r}")

        self._connected.set()

    async def close(self) -> None:
        """Close the WebSocket and stop background tasks."""
        self._closing = True
        self._connected.clear()
        if self._keepalive_task is not None:
            self._keepalive_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._keepalive_task
            self._keepalive_task = None
        if self._ws is not None and not self._ws.closed:
            await self._ws.close()
        if self._reader_task is not None:
            try:
                await asyncio.wait_for(self._reader_task, timeout=5.0)
            except (TimeoutError, asyncio.CancelledError, Exception):  # noqa: BLE001
                self._reader_task.cancel()
            self._reader_task = None
        # Fail any pending requests so callers don't hang forever.
        for fut in self._pending.values():
            if not fut.done():
                fut.set_exception(ConnectionClosedError("WebSocket closed"))
        self._pending.clear()
        for fut in self._pong_waiters.values():
            if not fut.done():
                fut.set_exception(ConnectionClosedError("WebSocket closed"))
        self._pong_waiters.clear()
        if self._owns_session and self._session is not None and not self._session.closed:
            await self._session.close()

    def on_disconnect(
        self, handler: Callable[[], Awaitable[None] | None]
    ) -> Callable[[], Awaitable[None] | None]:
        """Register ``handler`` to be called when the connection drops."""
        self._disconnect_listeners.append(handler)
        return handler

    # ------------------------------------------------------- send / receive
    def _next_id(self) -> int:
        self._message_id += 1
        return self._message_id

    async def _recv_json(self) -> dict[str, Any]:
        assert self._ws is not None
        msg = await self._ws.receive()
        if msg.type == aiohttp.WSMsgType.TEXT:
            data = msg.json()
            if isinstance(data, dict):
                return data
            raise HAClientError(f"Unexpected WebSocket payload: {data!r}")
        if msg.type in (
            aiohttp.WSMsgType.CLOSE,
            aiohttp.WSMsgType.CLOSED,
            aiohttp.WSMsgType.CLOSING,
        ):
            raise ConnectionClosedError("WebSocket closed during handshake")
        if msg.type == aiohttp.WSMsgType.ERROR:
            raise HAClientError(f"WebSocket error: {self._ws.exception()}")
        raise HAClientError(f"Unexpected WebSocket message type: {msg.type}")

    async def send_command(
        self,
        payload: dict[str, Any],
        *,
        timeout: float | None = None,
    ) -> Any:
        """Send a command and await its ``result`` frame.

        Returns the ``result`` payload (the value of the ``result`` key in the
        response). Raises :class:`CommandError` if Home Assistant returns a
        ``success: false`` response, and :class:`HATimeoutError` if no reply
        arrives within ``timeout`` seconds.
        """
        if not self.connected:
            raise ConnectionClosedError("WebSocket is not connected")
        assert self._ws is not None

        cmd_id = self._next_id()
        msg = {"id": cmd_id, **payload}
        fut: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
        self._pending[cmd_id] = fut
        try:
            await self._ws.send_json(msg)
            result = await asyncio.wait_for(
                fut, timeout=timeout if timeout is not None else self._request_timeout
            )
        except TimeoutError as err:
            self._pending.pop(cmd_id, None)
            raise HATimeoutError(f"Timed out waiting for response to command id={cmd_id}") from err
        finally:
            self._pending.pop(cmd_id, None)
        return result

    # ---------------------------------------------------------- subscriptions
    async def subscribe_events(
        self,
        handler: EventHandler,
        event_type: str | None = None,
    ) -> int:
        """Subscribe to Home Assistant events.

        Returns the subscription id (needed for :meth:`unsubscribe`).
        """
        payload: dict[str, Any] = {"type": "subscribe_events"}
        if event_type is not None:
            payload["event_type"] = event_type
        cmd_id = self._next_id()
        self._subscriptions[cmd_id] = handler
        if event_type is not None:
            self._event_subs[event_type] = (cmd_id, handler)
        msg = {"id": cmd_id, **payload}
        assert self._ws is not None
        fut: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
        self._pending[cmd_id] = fut
        try:
            await self._ws.send_json(msg)
            await asyncio.wait_for(fut, timeout=self._request_timeout)
        except Exception:
            self._subscriptions.pop(cmd_id, None)
            if event_type is not None:
                self._event_subs.pop(event_type, None)
            self._pending.pop(cmd_id, None)
            raise
        return cmd_id

    async def unsubscribe(self, subscription_id: int) -> None:
        """Unsubscribe a previously registered subscription."""
        await self.send_command({"type": "unsubscribe_events", "subscription": subscription_id})
        self._subscriptions.pop(subscription_id, None)
        for k, (sid, _handler) in list(self._event_subs.items()):
            if sid == subscription_id:
                self._event_subs.pop(k, None)

    # ------------------------------------------------------------- reader loop
    async def _reader_loop(self) -> None:
        assert self._ws is not None
        try:
            while not self._closing:
                try:
                    msg = await self._ws.receive()
                except Exception as err:  # noqa: BLE001
                    _LOGGER.warning("WebSocket receive failed: %s", err)
                    break

                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        data = msg.json()
                    except ValueError:
                        _LOGGER.warning("Non-JSON WebSocket frame: %r", msg.data)
                        continue
                    if isinstance(data, dict):
                        await self._dispatch(data)
                elif msg.type in (
                    aiohttp.WSMsgType.CLOSE,
                    aiohttp.WSMsgType.CLOSED,
                    aiohttp.WSMsgType.CLOSING,
                ):
                    _LOGGER.debug("WebSocket closed by peer")
                    break
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    _LOGGER.warning("WebSocket error: %s", self._ws.exception())
                    break
        finally:
            self._connected.clear()
            # Fail any pending requests so callers unblock.
            for fut in list(self._pending.values()):
                if not fut.done():
                    fut.set_exception(ConnectionClosedError("WebSocket closed"))
            self._pending.clear()
            for fut in list(self._pong_waiters.values()):
                if not fut.done():
                    fut.set_exception(ConnectionClosedError("WebSocket closed"))
            self._pong_waiters.clear()
            await self._notify_disconnect()
            if self._reconnect and not self._closing:
                asyncio.create_task(self._reconnect_loop(), name="ha-ws-reconnect")

    async def _notify_disconnect(self) -> None:
        for listener in list(self._disconnect_listeners):
            try:
                result = listener()
                if asyncio.iscoroutine(result):
                    await result
            except Exception:  # pragma: no cover - defensive
                _LOGGER.exception("Disconnect listener raised")

    async def _dispatch(self, msg: dict[str, Any]) -> None:
        mtype = msg.get("type")
        mid = msg.get("id")
        if mtype == "result":
            fut = self._pending.get(mid) if isinstance(mid, int) else None
            if fut is None or fut.done():
                return
            if msg.get("success", False):
                fut.set_result(msg.get("result"))
            else:
                err = msg.get("error") or {}
                fut.set_exception(
                    CommandError(
                        str(err.get("code", "unknown")),
                        str(err.get("message", "unknown error")),
                    )
                )
            return
        if mtype == "event":
            if isinstance(mid, int):
                handler = self._subscriptions.get(mid)
                if handler is not None:
                    await self._invoke_handler(handler, msg.get("event", {}))
            return
        if mtype == "pong":
            if isinstance(mid, int):
                pong_fut = self._pong_waiters.get(mid)
                if pong_fut is not None and not pong_fut.done():
                    pong_fut.set_result(msg)
            return
        # Unhandled – log at debug for visibility in tests.
        _LOGGER.debug("Unhandled WS message: %s", mtype)

    async def _invoke_handler(self, handler: EventHandler, event: dict[str, Any]) -> None:
        try:
            result = handler(event)
            if asyncio.iscoroutine(result):
                await result
        except Exception:  # pragma: no cover - defensive
            _LOGGER.exception("Event handler raised")

    # ---------------------------------------------------------- reconnect
    async def _reconnect_loop(self) -> None:
        delay = 1.0
        attempt = 0
        while not self._closing:
            attempt += 1
            try:
                _LOGGER.info("Reconnecting to %s (attempt %d)", self._url, attempt)
                await self._do_connect()
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("Reconnect attempt %d failed: %s", attempt, err)
                await asyncio.sleep(delay + random.uniform(0, 0.5))
                delay = min(delay * 2, 60.0)
                continue

            # Restart background loops.
            self._reader_task = asyncio.create_task(self._reader_loop(), name="ha-ws-reader")
            if self._ping_interval > 0:
                self._keepalive_task = asyncio.create_task(
                    self._keepalive_loop(), name="ha-ws-keepalive"
                )
            # Re-subscribe prior event subscriptions.
            for event_type, (_old_id, handler) in list(self._event_subs.items()):
                try:
                    await self.subscribe_events(handler, event_type)
                except Exception as err:  # noqa: BLE001
                    _LOGGER.warning("Failed to resubscribe to %s: %s", event_type, err)
            return

    # ---------------------------------------------------------- keepalive
    async def ping(self, *, timeout: float | None = None) -> None:
        """Send a ``ping`` frame and wait for the matching ``pong``.

        Home Assistant replies with ``{"type": "pong"}`` rather than a
        ``result`` frame, so this is implemented as a separate code path.
        """
        if not self.connected:
            raise ConnectionClosedError("WebSocket is not connected")
        assert self._ws is not None
        cmd_id = self._next_id()
        fut: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
        self._pong_waiters[cmd_id] = fut
        try:
            await self._ws.send_json({"id": cmd_id, "type": "ping"})
            await asyncio.wait_for(
                fut, timeout=timeout if timeout is not None else self._request_timeout
            )
        except TimeoutError as err:
            raise HATimeoutError("Ping timed out") from err
        finally:
            self._pong_waiters.pop(cmd_id, None)

    async def _keepalive_loop(self) -> None:
        try:
            while self.connected and not self._closing:
                await asyncio.sleep(self._ping_interval)
                if not self.connected:
                    return
                try:
                    await self.ping(timeout=self._ping_interval)
                except HATimeoutError:
                    _LOGGER.warning("Ping timed out – forcing reconnect")
                    if self._ws is not None and not self._ws.closed:
                        await self._ws.close()
                    return
                except Exception as err:  # noqa: BLE001
                    _LOGGER.debug("Keepalive error: %s", err)
                    return
        except asyncio.CancelledError:  # pragma: no cover
            pass
