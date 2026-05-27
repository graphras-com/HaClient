"""Public facade — `HAClient`.

The facade is intentionally thin. It wires together the infrastructure
adapters and core services, exposes the lifecycle methods, and presents
domain accessors. **No domain-specific logic lives here**: adding a new
domain is purely a matter of registering a `DomainSpec`.

Architecture
------------
::

    ┌─────────── HAClient (facade) ──────────────┐
    │  connection / events / services / state    │
    │  ha.<domain>("name") accessors             │
    └────┬───────────────┬────────────┬─────────┘
         │               │            │
    ┌────▼────┐    ┌─────▼─────┐ ┌────▼────────┐
    │EventBus │    │ServiceCal │ │ StateStore   │
    └─────────┘    └───────────┘ └──────────────┘
                  │            │
              ┌───▼────────────▼───┐
              │   Ports: REST/WS    │
              └─────┬───────────┬───┘
                    │           │
            ┌───────▼───┐  ┌────▼──────┐
            │ aiohttp   │  │ aiohttp   │
            │ REST      │  │ WS        │
            └───────────┘  └───────────┘

Both the connection lifecycle and the domain plugin layer are
discovered/composed at construction time. Third-party domains
discovered via the ``haclient.domains`` entry-point group are wired
identically to the built-ins — the facade has no special path for them.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from types import TracebackType
from typing import Any

import aiohttp

# Import the domains package eagerly so built-in DomainSpecs are registered
# before any HAClient is instantiated.
import haclient.domains  # noqa: F401  (side-effect import)
from haclient.config import ConnectionConfig, ServicePolicy
from haclient.core.clock import AsyncioClock
from haclient.core.connection import Connection
from haclient.core.events import EventBus
from haclient.core.factory import EntityFactory
from haclient.core.plugins import DomainAccessor, DomainRegistry, DomainSpec
from haclient.core.services import ServiceCaller
from haclient.core.state import StateStore
from haclient.infra.rest_aiohttp import AiohttpRestAdapter
from haclient.infra.ws_aiohttp import AiohttpWebSocketAdapter
from haclient.ports import RestPort, WebSocketPort


class HAClient:
    """High-level async Home Assistant client.

    Wires together transport adapters, core services, and the domain
    plugin registry. Use as an async context manager for the typical
    case::

        async with HAClient.from_url(BASE_URL, token=TOKEN) as ha:
            await ha.light("kitchen").set_brightness(200)

    Parameters
    ----------
    config : ConnectionConfig
        Resolved connection settings.
    session : aiohttp.ClientSession or None, optional
        Externally-owned session shared by REST and WS adapters.
    domains : list of str or None, optional
        Restrict the loaded domains to the names in this list. ``None``
        loads every registered domain.
    load_plugins : bool, optional
        Discover third-party plugins via the ``haclient.domains``
        entry-point group. Defaults to ``True``.
    registry : DomainRegistry or None, optional
        Override the shared `DomainRegistry`. Primarily for testing.
    """

    def __init__(
        self,
        config: ConnectionConfig,
        *,
        session: aiohttp.ClientSession | None = None,
        domains: list[str] | None = None,
        load_plugins: bool = True,
        registry: DomainRegistry | None = None,
    ) -> None:
        self._config = config
        self._registry = registry or DomainRegistry.shared()
        if load_plugins:
            self._registry.load_entry_points()

        self._rest: RestPort = AiohttpRestAdapter(
            config.base_url,
            config.token,
            session=session,
            timeout=config.request_timeout,
            verify_ssl=config.verify_ssl,
        )
        self._ws: WebSocketPort = AiohttpWebSocketAdapter(
            config.ws_url,
            config.token,
            session=session,
            reconnect=config.reconnect,
            ping_interval=config.ping_interval,
            request_timeout=config.request_timeout,
            verify_ssl=config.verify_ssl,
        )
        self._services = ServiceCaller(
            self._rest,
            self._ws,
            default_policy=config.service_policy,
        )
        self._events = EventBus(self._ws)
        self._state = StateStore(self._rest, self._events)
        self._clock = AsyncioClock()
        self._factory = EntityFactory(self._services, self._state, self._clock)
        self._connection = Connection(self._ws, self._rest, self._events, self._state)

        active = self._select_active_domains(domains)
        self._accessors: dict[str, DomainAccessor[Any]] = {}
        for spec in active:
            cls = spec.accessor_cls if spec.accessor_cls is not None else DomainAccessor
            accessor: DomainAccessor[Any] = cls(spec, self._factory)
            self._accessors[spec.accessor_name()] = accessor
            self._accessors[spec.name] = accessor
            for event_type in spec.event_subscriptions:
                self._events.subscribe(event_type, self._make_event_router(spec))

    # -- Construction helpers -----------------------------------------

    @classmethod
    def from_url(
        cls,
        base_url: str,
        *,
        token: str,
        ws_url: str | None = None,
        session: aiohttp.ClientSession | None = None,
        reconnect: bool = True,
        ping_interval: float = 30.0,
        request_timeout: float = 30.0,
        verify_ssl: bool = True,
        service_policy: ServicePolicy = "auto",
        domains: list[str] | None = None,
        load_plugins: bool = True,
        registry: DomainRegistry | None = None,
    ) -> HAClient:
        """Build an `HAClient` from a base URL and token.

        Parameters
        ----------
        base_url : str
            Home Assistant base URL.
        token : str
            Long-lived access token.
        ws_url : str or None, optional
            Explicit WebSocket URL (derived when omitted).
        session : aiohttp.ClientSession or None, optional
            Externally-owned aiohttp session.
        reconnect : bool, optional
            Whether the WebSocket should reconnect automatically.
        ping_interval : float, optional
            Seconds between WebSocket keepalive pings.
        request_timeout : float, optional
            Default timeout for individual requests.
        verify_ssl : bool, optional
            Verify TLS certificates.
        service_policy : ServicePolicy, optional
            Default service-call routing policy.
        domains : list of str or None, optional
            Restrict loaded domains. ``None`` loads all.
        load_plugins : bool, optional
            Discover third-party plugins.
        registry : DomainRegistry or None, optional
            Override the shared registry.

        Returns
        -------
        HAClient
            The configured client (not yet connected).
        """
        config = ConnectionConfig.from_url(
            base_url,
            token,
            ws_url=ws_url,
            reconnect=reconnect,
            ping_interval=ping_interval,
            request_timeout=request_timeout,
            verify_ssl=verify_ssl,
            service_policy=service_policy,
        )
        return cls(
            config,
            session=session,
            domains=domains,
            load_plugins=load_plugins,
            registry=registry,
        )

    def _select_active_domains(self, requested: list[str] | None) -> list[DomainSpec[Any]]:
        """Return the specs that should be active for this client.

        Parameters
        ----------
        requested : list of str or None
            Restrict to these domain names, or ``None`` to load every
            registered domain.

        Returns
        -------
        list of DomainSpec
            Specs in registration order.
        """
        if requested is None:
            return list(self._registry)
        return self._registry.filter(requested)

    def _make_event_router(self, spec: DomainSpec[Any]) -> Callable[[dict[str, Any]], None]:
        """Build a router that forwards a domain's HA events to its handler.

        The returned closure looks up the entity by id, then delegates
        to *spec*'s ``on_event`` callback. Events without a known entity
        or with no registered handler are silently dropped.

        Parameters
        ----------
        spec : DomainSpec
            The spec whose ``on_event`` callback should receive routed
            events.

        Returns
        -------
        callable
            Synchronous event handler suitable for `EventBus.subscribe`.
        """

        on_event = spec.on_event

        def route(event: dict[str, Any]) -> None:
            if on_event is None:
                return
            event_type = event.get("event_type", "")
            data = event.get("data") or {}
            eid = data.get("entity_id")
            if not isinstance(eid, str):
                return
            entity = self._state.registry.get(eid)
            if entity is None:
                return
            on_event(entity, event_type, data)

        return route

    # -- Lifecycle ----------------------------------------------------

    async def __aenter__(self) -> HAClient:
        """Enter the async context manager.

        Calls `connect` to open the WebSocket, authenticate, and prime
        the state cache. Any exception raised during connect propagates
        to the caller; in that case the partially-initialised client is
        not entered and `__aexit__` will not run, so callers that pre-
        construct the client should still call `close` on failure.

        Returns
        -------
        HAClient
            ``self``, fully connected and ready for use.

        Raises
        ------
        AuthenticationError
            If the provided token is rejected by Home Assistant.
        ConnectionClosedError
            If the WebSocket disconnects before the handshake completes.
        TimeoutError
            If the initial connect or state-priming request times out.
        HTTPError
            If the initial REST ``get_states`` call returns an error.
        """
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Exit the async context manager and release all resources.

        Delegates to `close`, which shuts down the WebSocket and REST
        adapters. Exceptions raised from the ``with`` block are **not**
        suppressed (the method always returns ``None``); any errors
        raised by `close` itself surface to the caller.

        Parameters
        ----------
        exc_type : type of BaseException or None
            Exception class raised inside the ``async with`` block, if
            any.
        exc : BaseException or None
            Exception instance, if any.
        tb : TracebackType or None
            Associated traceback, if any.

        Notes
        -----
        Registered ``on_disconnect`` listeners run as part of the close
        sequence.
        """
        await self.close()

    async def connect(self) -> None:
        """Open the WebSocket, authenticate, and prime the state cache.

        Side effects:

        * Opens the WebSocket and performs the auth handshake.
        * Issues an initial REST ``get_states`` request and seeds the
          `StateStore`.
        * Subscribes to ``state_changed`` events so the cache stays
          live.
        * Starts background reconnect/keepalive tasks (when reconnect
          is enabled in the `ConnectionConfig`).

        Raises
        ------
        AuthenticationError
            If the provided token is rejected.
        ConnectionClosedError
            If the WebSocket disconnects before the handshake completes.
        TimeoutError
            If a transport operation exceeds ``request_timeout``.
        HTTPError
            If the initial REST ``get_states`` call returns an error.

        Notes
        -----
        Calling `connect` while already connected is a no-op handled by
        the underlying `Connection`.
        """
        await self._connection.open()

    async def close(self) -> None:
        """Close all transports and stop background tasks.

        Closes the WebSocket (cancelling reconnect/keepalive tasks and
        firing registered ``on_disconnect`` listeners) and the REST
        adapter (releasing the owned aiohttp session, if any). An
        externally-supplied session is not closed.

        Notes
        -----
        Safe to call multiple times; subsequent calls are no-ops.
        Errors during shutdown propagate to the caller.
        """
        await self._connection.close()

    # -- Public service surface --------------------------------------

    @property
    def config(self) -> ConnectionConfig:
        """Resolved connection settings.

        Returns
        -------
        ConnectionConfig
            The frozen settings object built at construction time
            (URLs, token, timeouts, TLS, reconnect, service policy).
        """
        return self._config

    @property
    def base_url(self) -> str:
        """Configured Home Assistant base URL.

        Returns
        -------
        str
            The REST base URL (e.g. ``"https://homeassistant.local:8123"``).
        """
        return self._config.base_url

    @property
    def connection(self) -> Connection:
        """The `Connection` lifecycle service.

        Returns
        -------
        Connection
            Owns the open/close lifecycle, dispatches disconnect and
            reconnect listeners, and re-primes the state cache after
            each successful reconnect.
        """
        return self._connection

    @property
    def events(self) -> EventBus:
        """The shared `EventBus` for Home Assistant events.

        Returns
        -------
        EventBus
            User-facing pub/sub façade. Subscriptions take effect
            immediately and survive WebSocket reconnects transparently.
        """
        return self._events

    @property
    def services(self) -> ServiceCaller:
        """The shared `ServiceCaller`.

        Returns
        -------
        ServiceCaller
            Routes raw service calls over REST or WebSocket according
            to the configured `ServicePolicy`. Domain entity actions
            ultimately call through this object.
        """
        return self._services

    @property
    def state(self) -> StateStore:
        """The shared `StateStore`.

        Returns
        -------
        StateStore
            Owns the live entity cache, exposes the entity registry
            used by domain accessors, and dispatches per-entity
            listeners on every ``state_changed`` event.
        """
        return self._state

    @property
    def domains(self) -> DomainRegistry:
        """Active `DomainRegistry` for this client.

        Returns
        -------
        DomainRegistry
            Registry of built-in and plugin-discovered `DomainSpec`
            entries. Unless an explicit registry was passed at
            construction, this is the process-wide shared instance —
            mutating it affects every client that shares it.
        """
        return self._registry

    def loop(self) -> asyncio.AbstractEventLoop | None:
        """Return the running asyncio loop, if any.

        Returns
        -------
        asyncio.AbstractEventLoop or None
            The most recently observed running loop, or ``None`` when
            called outside any running loop and no loop has been
            captured yet.
        """
        return self._clock.loop()

    def on_disconnect(
        self,
        handler: Callable[[], Awaitable[None] | None],
    ) -> Callable[[], Awaitable[None] | None]:
        """Register a disconnect listener.

        Parameters
        ----------
        handler : callable
            Sync or async zero-argument callable invoked when the
            WebSocket connection drops.

        Returns
        -------
        callable
            The same *handler*, returned so the method can be used as a
            decorator.
        """
        return self._connection.on_disconnect(handler)

    def on_reconnect(
        self,
        handler: Callable[[], Awaitable[None] | None],
    ) -> Callable[[], Awaitable[None] | None]:
        """Register a reconnect listener.

        Parameters
        ----------
        handler : callable
            Sync or async zero-argument callable invoked after the
            WebSocket reconnects successfully and the state cache has
            been re-primed.

        Returns
        -------
        callable
            The same *handler*, returned so the method can be used as a
            decorator.
        """
        return self._connection.on_reconnect(handler)

    # -- Domain accessors --------------------------------------------

    def domain(self, name: str) -> DomainAccessor[Any]:
        """Return the `DomainAccessor` for *name*.

        Works for any active domain — including third-party plugins
        registered via entry points.

        Parameters
        ----------
        name : str
            The HA domain name.

        Returns
        -------
        DomainAccessor
            The accessor for the domain.

        Raises
        ------
        HAClientError
            If *name* is not a registered or active domain.
        """
        accessor = self._accessors.get(name)
        if accessor is None:
            # Fall back to the registry to give a clear error message.
            self._registry.get(name)
            raise KeyError(f"Domain {name!r} is not active on this client")
        return accessor

    def __getattr__(self, name: str) -> DomainAccessor[Any]:
        """Return the `DomainAccessor` for a registered domain.

        Enables ``ha.light("kitchen")``, ``ha.scene.create(...)``, etc.
        for *any* registered domain — built-in or third-party — without
        the facade needing to know which domains exist.

        Parameters
        ----------
        name : str
            The domain or accessor name (e.g. ``"light"``,
            ``"media_player"``).

        Returns
        -------
        DomainAccessor
            The accessor for the domain.

        Raises
        ------
        AttributeError
            If *name* does not match any active domain.
        """
        # Guard: only intercept after __init__ has populated _accessors.
        try:
            accessors: dict[str, DomainAccessor[Any]] = self.__dict__["_accessors"]
        except KeyError:
            raise AttributeError(name) from None
        try:
            return accessors[name]
        except KeyError:
            raise AttributeError(
                f"{type(self).__name__!r} object has no attribute {name!r}"
            ) from None
