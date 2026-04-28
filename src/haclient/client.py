"""High-level Home Assistant client.

This module ties together the REST and WebSocket layers, the entity registry
and the domain helper classes into a single coherent API.

The client exposes one accessor per supported domain (``media_player``,
``light``, ``switch``, ...). The accessor performs name resolution, creates a
domain object lazily if needed and returns the registered instance.

Examples
--------
::

    async with HAClient("http://localhost:8123", token="...") as ha:
        light = ha.light("kitchen")
        await light.set_brightness(200)
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
    from .domains.scene import Scene
    from .domains.sensor import Sensor
    from .domains.switch import Switch
    from .domains.timer import Timer

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
    base_url : str
        The Home Assistant base URL (e.g. ``http://homeassistant.local:8123``).
    token : str
        Long-lived access token.
    ws_url : str or None, optional
        Explicit WebSocket URL. If omitted it is derived from *base_url*.
    session : aiohttp.ClientSession or None, optional
        Shared ``aiohttp.ClientSession``.
    reconnect : bool, optional
        Whether to reconnect the WebSocket automatically.
    ping_interval : float, optional
        Seconds between keepalive pings (set to ``0`` to disable).
    request_timeout : float, optional
        Default timeout for WebSocket/REST operations.
    verify_ssl : bool, optional
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
        self._timer_finished_sub_id: int | None = None
        self._timer_cancelled_sub_id: int | None = None
        self._connected = False

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
        self._state_sub_id = await self.ws.subscribe_events(
            self._on_state_changed_event, "state_changed"
        )
        self._timer_finished_sub_id = await self.ws.subscribe_events(
            self._on_timer_event, "timer.finished"
        )
        self._timer_cancelled_sub_id = await self.ws.subscribe_events(
            self._on_timer_event, "timer.cancelled"
        )
        self.ws.on_reconnect(self._on_reconnect)
        self._connected = True

    async def close(self) -> None:
        """Close the WebSocket and any owned HTTP session."""
        self._connected = False
        await self.ws.close()
        await self.rest.close()

    def _on_state_changed_event(self, event: dict[str, Any]) -> None:
        """Dispatch a ``state_changed`` event to the appropriate entity.

        Parameters
        ----------
        event : dict
            The raw event payload from the WebSocket.
        """
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

    def _on_timer_event(self, event: dict[str, Any]) -> None:
        """Dispatch a ``timer.finished`` or ``timer.cancelled`` event.

        Parameters
        ----------
        event : dict
            The raw event payload from the WebSocket.
        """
        from .domains.timer import Timer as _Timer

        event_type = event.get("event_type", "")
        data = event.get("data") or {}
        eid = data.get("entity_id")
        if not isinstance(eid, str):
            return
        entity = self.registry.get(eid)
        if entity is None or not isinstance(entity, _Timer):
            return
        entity._handle_timer_event(event_type, data)  # noqa: SLF001

    async def _on_reconnect(self) -> None:
        """Refresh all entity state after the WebSocket reconnects.

        This is registered as a reconnect listener so that entities whose
        state changed while the connection was down are brought up to date
        automatically.
        """
        try:
            await self.refresh_all()
        except HAClientError as err:
            _LOGGER.warning("Post-reconnect refresh failed: %s", err)

    async def _call_service(
        self,
        domain: str,
        service: str,
        data: dict[str, Any] | None = None,
        *,
        use_websocket: bool = True,
    ) -> Any:
        """Invoke a Home Assistant service.

        By default the call is made via the WebSocket API (which gives richer
        error information). Set *use_websocket* to ``False`` to use the REST API
        instead -- useful before the WS connection is established.

        Parameters
        ----------
        domain : str
            The service domain (e.g. ``"light"``).
        service : str
            The service name (e.g. ``"turn_on"``).
        data : dict or None, optional
            Service data payload.
        use_websocket : bool, optional
            If ``True`` (default), use the WebSocket API when connected.

        Returns
        -------
        Any
            The result payload from Home Assistant.
        """
        if use_websocket and self.ws.connected:
            payload: dict[str, Any] = {
                "type": "call_service",
                "domain": domain,
                "service": service,
            }
            if data:
                payload["service_data"] = data
            return await self.ws.send_command(payload)
        return await self.rest.call_service(domain, service, data)

    async def refresh_all(self) -> None:
        """Refresh all registered entities from the REST API."""
        states = await self.rest.get_states()
        index = {s.get("entity_id"): s for s in states if isinstance(s, dict)}
        for entity in list(self.registry):
            entity._apply_state(index.get(entity.entity_id))  # noqa: SLF001

    def _get_or_create(self, domain: str, name: str, cls: type[_E]) -> _E:
        """Return the entity for *name* in *domain*, creating it if needed.

        Parameters
        ----------
        domain : str
            The Home Assistant domain (e.g. ``"light"``).
        name : str
            Short object-id (e.g. ``"kitchen"``).  The domain prefix is
            added automatically; do not pass a fully-qualified entity id.
        cls : type
            The ``Entity`` subclass to instantiate if absent.

        Returns
        -------
        Entity
            The existing or newly created entity instance.

        Raises
        ------
        HAClientError
            If the entity exists but is registered under a different class.
        """
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
        """Return the `MediaPlayer` for *name*, creating it if needed.

        Parameters
        ----------
        name : str
            Short object-id (e.g. ``"livingroom"``).  The domain prefix
            is added automatically.

        Returns
        -------
        MediaPlayer
            The media player entity.
        """
        from .domains.media_player import MediaPlayer as _MediaPlayer

        return self._get_or_create("media_player", name, _MediaPlayer)

    def light(self, name: str) -> Light:
        """Return the `Light` for *name*, creating it if needed.

        Parameters
        ----------
        name : str
            Short object-id (e.g. ``"livingroom"``).  The domain prefix
            is added automatically.

        Returns
        -------
        Light
            The light entity.
        """
        from .domains.light import Light as _Light

        return self._get_or_create("light", name, _Light)

    def switch(self, name: str) -> Switch:
        """Return the `Switch` for *name*, creating it if needed.

        Parameters
        ----------
        name : str
            Short object-id (e.g. ``"livingroom"``).  The domain prefix
            is added automatically.

        Returns
        -------
        Switch
            The switch entity.
        """
        from .domains.switch import Switch as _Switch

        return self._get_or_create("switch", name, _Switch)

    def climate(self, name: str) -> Climate:
        """Return the `Climate` for *name*, creating it if needed.

        Parameters
        ----------
        name : str
            Short object-id (e.g. ``"livingroom"``).  The domain prefix
            is added automatically.

        Returns
        -------
        Climate
            The climate entity.
        """
        from .domains.climate import Climate as _Climate

        return self._get_or_create("climate", name, _Climate)

    def cover(self, name: str) -> Cover:
        """Return the `Cover` for *name*, creating it if needed.

        Parameters
        ----------
        name : str
            Short object-id (e.g. ``"livingroom"``).  The domain prefix
            is added automatically.

        Returns
        -------
        Cover
            The cover entity.
        """
        from .domains.cover import Cover as _Cover

        return self._get_or_create("cover", name, _Cover)

    def sensor(self, name: str) -> Sensor:
        """Return the `Sensor` for *name* (read-only), creating it if needed.

        Parameters
        ----------
        name : str
            Short object-id (e.g. ``"livingroom"``).  The domain prefix
            is added automatically.

        Returns
        -------
        Sensor
            The sensor entity.
        """
        from .domains.sensor import Sensor as _Sensor

        return self._get_or_create("sensor", name, _Sensor)

    def binary_sensor(self, name: str) -> BinarySensor:
        """Return the `BinarySensor` for *name* (read-only), creating it if needed.

        Parameters
        ----------
        name : str
            Short object-id (e.g. ``"livingroom"``).  The domain prefix
            is added automatically.

        Returns
        -------
        BinarySensor
            The binary sensor entity.
        """
        from .domains.binary_sensor import BinarySensor as _BinarySensor

        return self._get_or_create("binary_sensor", name, _BinarySensor)

    def scene(self, name: str) -> Scene:
        """Return the `Scene` for *name*, creating it if needed.

        Parameters
        ----------
        name : str
            Short object-id (e.g. ``"livingroom"``).  The domain prefix
            is added automatically.

        Returns
        -------
        Scene
            The scene entity.
        """
        from .domains.scene import Scene as _Scene

        return self._get_or_create("scene", name, _Scene)

    async def create_scene(
        self,
        scene_id: str,
        entities: dict[str, dict[str, Any]],
        *,
        snapshot_entities: list[str] | None = None,
    ) -> Scene:
        """Create a dynamic scene and return the `Scene` object.

        This calls the ``scene.create`` service, which creates (or updates)
        a scene at runtime.  The resulting scene can later be deleted with
        `Scene.delete`.

        Parameters
        ----------
        scene_id : str
            The object-id for the new scene (e.g. ``"romantic"`` becomes
            ``scene.romantic``).
        entities : dict[str, dict[str, Any]]
            Mapping of entity IDs to the state/attribute dicts that the
            scene should apply.  For example::

                {"light.ceiling": {"state": "on", "brightness": 120}}
        snapshot_entities : list of str or None, optional
            Entity IDs whose **current** state should be captured into
            the scene instead of using explicit values.

        Returns
        -------
        Scene
            The newly created (or updated) `Scene` instance.
        """
        from .domains.scene import Scene as _Scene

        data: dict[str, Any] = {
            "scene_id": scene_id,
            "entities": entities,
        }
        if snapshot_entities is not None:
            data["snapshot_entities"] = snapshot_entities

        await self._call_service("scene", "create", data)
        return self._get_or_create("scene", scene_id, _Scene)

    async def apply_scene(
        self,
        entities: dict[str, dict[str, Any]],
        *,
        transition: float | None = None,
    ) -> None:
        """Apply entity states without creating a persistent scene.

        This calls the ``scene.apply`` service.  It works like activating
        a scene, but the state combination is not saved.

        Parameters
        ----------
        entities : dict[str, dict[str, Any]]
            Mapping of entity IDs to desired state/attribute dicts.
        transition : float or None, optional
            Transition time in seconds for entities that support it.
        """
        data: dict[str, Any] = {"entities": entities}
        if transition is not None:
            data["transition"] = transition
        await self._call_service("scene", "apply", data)

    def timer(self, name: str | None = None, *, persistent: bool = False) -> Timer:
        """Return a `Timer`, creating the Python object if needed.

        Timers are **ephemeral by default**: the HA helper is created on the
        first action and deleted automatically when the timer returns to idle.
        Pass ``persistent=True`` to keep the helper alive.

        Parameters
        ----------
        name : str or None, optional
            Short object-id (e.g. ``"my_timer"``).  The ``timer.`` prefix
            is added automatically.  When ``None`` a unique id is
            generated automatically (only allowed for ephemeral timers).
        persistent : bool, optional
            If ``True``, the HA helper is **not** deleted on idle.
            Requires an explicit *name*.

        Returns
        -------
        Timer
            The timer entity.

        Raises
        ------
        ValueError
            If ``persistent=True`` and *name* is ``None``.
        """
        from .domains.timer import Timer as _Timer
        from .domains.timer import _generate_timer_id

        if name is None:
            if persistent:
                raise ValueError("Persistent timers require an explicit name")
            name = _generate_timer_id()

        entity_id = self.registry.resolve("timer", name)
        existing = self.registry.get(entity_id)
        if existing is not None:
            if not isinstance(existing, _Timer):
                raise HAClientError(
                    f"Entity {entity_id} is registered as {type(existing).__name__}, "
                    f"not {_Timer.__name__}"
                )
            return existing
        return _Timer(entity_id, self, persistent=persistent)
