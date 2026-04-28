"""Tests for `StateStore` priming and refresh edge cases."""

from __future__ import annotations

from typing import Any

from haclient.core.events import EventBus
from haclient.core.state import StateStore
from haclient.exceptions import HAClientError


class _Rest:
    """`RestPort` stub used to drive `StateStore` priming edge cases."""

    base_url = "http://x"

    def __init__(self, *, raise_on_get_states: bool = False, states: list[Any] | None = None):
        """Configure the stub.

        Parameters
        ----------
        raise_on_get_states : bool, optional
            When ``True``, every `get_states` call raises `HAClientError`.
        states : list or None, optional
            States returned by `get_states` (when not raising).
        """
        self._raise = raise_on_get_states
        self._states = states or []
        self.calls = 0

    async def get_states(self) -> list[dict[str, Any]]:
        """Return the configured states or raise as configured."""
        self.calls += 1
        if self._raise:
            raise HAClientError("boom")
        return list(self._states)

    async def get_state(self, entity_id: str) -> dict[str, Any] | None:
        """Stub: return ``None`` for every entity."""
        return None

    async def call_service(
        self, domain: str, service: str, data: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Stub: return an empty state list."""
        return []

    async def close(self) -> None:
        """Stub: no resources to release."""


class _WS:
    """`WebSocketPort` stub that captures the registered event handlers."""

    connected = True

    def __init__(self) -> None:
        """Initialise the per-event-type handler map."""
        self.handlers: dict[str, Any] = {}

    async def connect(self) -> None:
        """Stub: no-op connect."""

    async def close(self) -> None:
        """Stub: no-op close."""

    async def send_command(self, payload: dict[str, Any], *, timeout: float | None = None) -> Any:
        """Stub: ignore commands and return ``None``."""
        return None

    async def subscribe_events(self, handler: Any, event_type: str | None = None) -> int:
        """Record the handler keyed by *event_type* and return id ``1``."""
        if event_type is not None:
            self.handlers[event_type] = handler
        return 1

    async def unsubscribe(self, subscription_id: int) -> None:
        """Stub: no-op unsubscribe."""

    def on_disconnect(self, handler: Any) -> Any:
        """Stub: return *handler* unchanged."""
        return handler

    def on_reconnect(self, handler: Any) -> Any:
        """Stub: return *handler* unchanged."""
        return handler


async def test_prime_swallows_rest_failure() -> None:
    rest = _Rest(raise_on_get_states=True)
    ws = _WS()
    bus = EventBus(ws)  # type: ignore[arg-type]
    store = StateStore(rest, bus)  # type: ignore[arg-type]
    await store.prime()
    assert rest.calls == 1


async def test_prime_skips_invalid_state_objects() -> None:
    rest = _Rest(
        states=[
            "not-a-dict",
            {"entity_id": 5, "state": "on"},
            {"entity_id": "light.x", "state": "on", "attributes": {}},
        ]
    )
    ws = _WS()
    bus = EventBus(ws)  # type: ignore[arg-type]
    store = StateStore(rest, bus)  # type: ignore[arg-type]
    await store.prime()  # should not raise


async def test_refresh_all_skips_non_dict_states() -> None:
    rest = _Rest(states=["not-a-dict", {"entity_id": "light.x", "state": "on"}])
    ws = _WS()
    bus = EventBus(ws)  # type: ignore[arg-type]
    store = StateStore(rest, bus)  # type: ignore[arg-type]
    await store.refresh_all()


async def test_get_and_iter() -> None:
    rest = _Rest()
    ws = _WS()
    bus = EventBus(ws)  # type: ignore[arg-type]
    store = StateStore(rest, bus)  # type: ignore[arg-type]
    assert store.get("light.unknown") is None
    assert list(store) == []
    assert store.rest is rest


async def test_connection_post_reconnect_refresh_swallows_errors() -> None:
    """The connection logs but does not propagate exceptions from refresh_all."""
    from haclient.core.connection import Connection

    rest = _Rest(raise_on_get_states=True)
    ws = _WS()
    bus = EventBus(ws)  # type: ignore[arg-type]
    store = StateStore(rest, bus)  # type: ignore[arg-type]
    conn = Connection(ws, rest, bus, store)  # type: ignore[arg-type]
    await conn._on_reconnect()  # should not raise


async def test_double_open_is_noop_on_connection() -> None:
    """Calling Connection.open twice does not re-prime."""
    from haclient.core.connection import Connection

    rest = _Rest()
    ws = _WS()
    bus = EventBus(ws)  # type: ignore[arg-type]
    store = StateStore(rest, bus)  # type: ignore[arg-type]
    conn = Connection(ws, rest, bus, store)  # type: ignore[arg-type]
    await conn.open()
    initial_calls = rest.calls
    await conn.open()  # noop
    assert rest.calls == initial_calls
    assert conn.is_connected
