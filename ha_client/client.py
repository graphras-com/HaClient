"""High-level Home Assistant client.

This module ties together the REST and WebSocket layers, the entity registry
and the domain helper classes into a single coherent API:

.. code-block:: python

    async with HAClient("http://localhost:8123", token="...") as ha:
        light = ha.light("kitchen")
        await light.turn_on(brightness=200)

The client exposes one accessor per supported domain (``media_player``,
``light``, ``switch``, ...). The accessor performs name resolution, creates a
domain object lazily if needed and returns the registered instance.
"""

from __future__ import annotations

import asyncio
import logging
from types import TracebackType
from typing import TYPE_CHECKING, Any, TypeVar
from urllib.parse import urlparse, urlunparse

import aiohttp

from .entity import Entity
from .exceptions import HAClientError
from .registry import EntityRegistry
from .rest import RestClient
from .websocket import WebSocketClient

if TYPE_CHECKING:
    from .domains.binary_sensor import BinarySensor
    from .domains.climate import Climate
    from .domains.cover import Cover
    from .domains.light import Light
    from .domains.media_player import MediaPlayer
    from .domains.sensor import Sensor
    from .domains.switch import Switch

_E = TypeVar("_E", bound=Entity)

_LOGGER = logging.getLogger(__name__)


def _derive_ws_url(base_url: str) -> str:
    """Derive the WebSocket URL from a Home Assistant base URL."""
    parsed = urlparse(base_url)
    scheme_map = {"http": "ws", "https": "wss", "ws": "ws", "wss": "wss"}
    scheme = scheme_map.get(parsed.scheme, "ws")
    path = parsed.path.rstrip("/") + "/api/websocket"
    return urlunparse((scheme, parsed.netloc, path, "", "", ""))


class HAClient:
    """High-level async Home Assistant client.

    Parameters
    ----------
    base_url:
        The Home Assistant base URL (e.g. ``http://homeassistant.local:8123``).
    token:
        Long-lived access token.
    ws_url:
        Optional explicit WebSocket URL. If omitted it is derived from
        ``base_url``.
    session:
        Optional shared :class:`aiohttp.ClientSession`.
    reconnect:
        Whether to reconnect the WebSocket automatically.
    ping_interval:
        Seconds between keepalive pings (set to ``0`` to disable).
    request_timeout:
        Default timeout for WebSocket/REST operations.
    verify_ssl:
        Verify TLS certificates (``True`` by default).
    """

    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        ws_url: str | None = None,
        session: aiohttp.ClientSession | None = None,
        reconnect: bool = True,
        ping_interval: float = 30.0,
        request_timeout: float = 30.0,
        verify_ssl: bool = True,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._token = token
        self._session = session
        self._owns_session = session is None

        self.registry = EntityRegistry()
        self.rest = RestClient(
            self.base_url,
            token,
            session=session,
            timeout=request_timeout,
            verify_ssl=verify_ssl,
        )
        self.ws = WebSocketClient(
            ws_url or _derive_ws_url(self.base_url),
            token,
            session=session,
            reconnect=reconnect,
            ping_interval=ping_interval,
            request_timeout=request_timeout,
            verify_ssl=verify_ssl,
        )
        self._state_sub_id: int | None = None
        self._connected = False

    # -------------------------------------------------- async context manager
    async def __aenter__(self) -> HAClient:
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.close()

    # ------------------------------------------------------- lifecycle
    @property
    def loop(self) -> asyncio.AbstractEventLoop | None:
        """Return the event loop the client is bound to (if running)."""
        try:
            return asyncio.get_running_loop()
        except RuntimeError:
            return None

    async def connect(self) -> None:
        """Connect the WebSocket, subscribe to state changes and prime the cache."""
        if self._connected:
            return
        await self.ws.connect()
        # Seed entity states from REST so attribute access works immediately.
        try:
            states = await self.rest.get_states()
        except HAClientError as err:
            _LOGGER.warning("Initial state fetch failed: %s", err)
            states = []
        for state in states:
            eid = state.get("entity_id")
            if not isinstance(eid, str):
                continue
            entity = self.registry.get(eid)
            if entity is not None:
                entity._apply_state(state)  # noqa: SLF001
        # Subscribe to state_changed events so registered entities stay fresh.
        self._state_sub_id = await self.ws.subscribe_events(
            self._on_state_changed_event, "state_changed"
        )
        self._connected = True

    async def close(self) -> None:
        """Close the WebSocket and any owned HTTP session."""
        self._connected = False
        await self.ws.close()
        await self.rest.close()

    # -------------------------------------------------------- event wiring
    def _on_state_changed_event(self, event: dict[str, Any]) -> None:
        data = event.get("data") or {}
        eid = data.get("entity_id")
        if not isinstance(eid, str):
            return
        entity = self.registry.get(eid)
        if entity is None:
            return
        entity._handle_state_changed(  # noqa: SLF001
            data.get("old_state"), data.get("new_state")
        )

    # ---------------------------------------------------- service helpers
    async def call_service(
        self,
        domain: str,
        service: str,
        data: dict[str, Any] | None = None,
        *,
        use_websocket: bool = True,
    ) -> Any:
        """Invoke a Home Assistant service.

        By default the call is made via the WebSocket API (which gives richer
        error information). Set ``use_websocket=False`` to use the REST API
        instead – useful before the WS connection is established.
        """
        if use_websocket and self.ws.connected:
            payload: dict[str, Any] = {
                "type": "call_service",
                "domain": domain,
                "service": service,
            }
            if data:
                # HA expects 'target'/'service_data' separation; 'service_data'
                # works with entity_id embedded for all domains we care about.
                payload["service_data"] = data
            return await self.ws.send_command(payload)
        return await self.rest.call_service(domain, service, data)

    async def refresh_all(self) -> None:
        """Refresh all registered entities from the REST API."""
        states = await self.rest.get_states()
        index = {s.get("entity_id"): s for s in states if isinstance(s, dict)}
        for entity in list(self.registry):
            entity._apply_state(index.get(entity.entity_id))  # noqa: SLF001

    # --------------------------------------------------- domain accessors
    def _get_or_create(self, domain: str, name: str, cls: type[_E]) -> _E:
        entity_id = self.registry.resolve(domain, name)
        existing = self.registry.get(entity_id)
        if existing is not None:
            if not isinstance(existing, cls):
                raise HAClientError(
                    f"Entity {entity_id} is registered as {type(existing).__name__}, "
                    f"not {cls.__name__}"
                )
            return existing
        return cls(entity_id, self)

    def media_player(self, name: str) -> MediaPlayer:
        """Return the :class:`MediaPlayer` for ``name`` (creating it if needed)."""
        from .domains.media_player import MediaPlayer as _MediaPlayer

        return self._get_or_create("media_player", name, _MediaPlayer)

    def light(self, name: str) -> Light:
        """Return the :class:`Light` for ``name``."""
        from .domains.light import Light as _Light

        return self._get_or_create("light", name, _Light)

    def switch(self, name: str) -> Switch:
        """Return the :class:`Switch` for ``name``."""
        from .domains.switch import Switch as _Switch

        return self._get_or_create("switch", name, _Switch)

    def climate(self, name: str) -> Climate:
        """Return the :class:`Climate` for ``name``."""
        from .domains.climate import Climate as _Climate

        return self._get_or_create("climate", name, _Climate)

    def cover(self, name: str) -> Cover:
        """Return the :class:`Cover` for ``name``."""
        from .domains.cover import Cover as _Cover

        return self._get_or_create("cover", name, _Cover)

    def sensor(self, name: str) -> Sensor:
        """Return the :class:`Sensor` for ``name`` (read-only)."""
        from .domains.sensor import Sensor as _Sensor

        return self._get_or_create("sensor", name, _Sensor)

    def binary_sensor(self, name: str) -> BinarySensor:
        """Return the :class:`BinarySensor` for ``name`` (read-only)."""
        from .domains.binary_sensor import BinarySensor as _BinarySensor

        return self._get_or_create("binary_sensor", name, _BinarySensor)
