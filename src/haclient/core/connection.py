"""`Connection` — owns the WebSocket lifecycle and the state-priming pipeline.

The connection is the single place that knows the order in which the
core services must be brought up: subscribe to events first (with
buffering enabled), then prime the state cache from REST, then drain the
buffered events. The same sequence runs on reconnect so the cache stays
consistent.

Disconnect / reconnect listeners live here as a thin pass-through to the
underlying `WebSocketPort`.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from haclient.ports import DisconnectListener, ReconnectListener, RestPort, WebSocketPort

if TYPE_CHECKING:
    from haclient.core.events import EventBus
    from haclient.core.state import StateStore

_LOGGER = logging.getLogger(__name__)


class Connection:
    """Lifecycle facade for the transport layer.

    Parameters
    ----------
    ws : WebSocketPort
        Underlying WebSocket adapter.
    rest : RestPort
        Underlying REST adapter.
    events : EventBus
        Event bus to bring up.
    state : StateStore
        State store to prime.
    """

    def __init__(
        self,
        ws: WebSocketPort,
        rest: RestPort,
        events: EventBus,
        state: StateStore,
    ) -> None:
        self._ws = ws
        self._rest = rest
        self._events = events
        self._state = state
        self._connected = False
        # Wire post-reconnect refresh.
        self._ws.on_reconnect(self._on_reconnect)

    @property
    def ws(self) -> WebSocketPort:
        """Return the underlying WebSocket adapter."""
        return self._ws

    @property
    def rest(self) -> RestPort:
        """Return the underlying REST adapter."""
        return self._rest

    @property
    def is_connected(self) -> bool:
        """Return ``True`` once `open` has completed successfully."""
        return self._connected

    async def open(self) -> None:
        """Connect, subscribe to events, and prime the state cache.

        Idempotent: a second call while already connected is a no-op.
        """
        if self._connected:
            return
        await self._ws.connect()
        await self._state.prime()
        self._connected = True

    async def close(self) -> None:
        """Tear down the connection and release infrastructure resources."""
        self._connected = False
        await self._ws.close()
        await self._rest.close()

    def on_disconnect(self, handler: DisconnectListener) -> DisconnectListener:
        """Register a disconnect listener (forwarded to the WS adapter).

        Parameters
        ----------
        handler : DisconnectListener
            Sync or async zero-argument callable invoked when the
            underlying WebSocket connection drops.

        Returns
        -------
        DisconnectListener
            The same *handler*, returned so the method can be used as a
            decorator.
        """
        return self._ws.on_disconnect(handler)

    def on_reconnect(self, handler: ReconnectListener) -> ReconnectListener:
        """Register a reconnect listener (forwarded to the WS adapter).

        Parameters
        ----------
        handler : ReconnectListener
            Sync or async zero-argument callable invoked after the
            underlying WebSocket reconnects.

        Returns
        -------
        ReconnectListener
            The same *handler*, returned so the method can be used as a
            decorator.
        """
        return self._ws.on_reconnect(handler)

    async def _on_reconnect(self) -> None:
        """Re-prime the state store after a successful reconnection."""
        try:
            await self._state.refresh_all()
        except Exception:  # noqa: BLE001
            _LOGGER.warning("Post-reconnect refresh failed", exc_info=True)
