"""Tests for `ServiceCaller` policy routing."""

from __future__ import annotations

from typing import Any

import pytest

from haclient.core.services import ServiceCaller
from haclient.exceptions import ConnectionClosedError


class _FakeRest:
    """`RestPort` stub that records every ``call_service`` invocation."""

    base_url = "http://x"

    def __init__(self) -> None:
        """Initialise the (domain, service, data) call log."""
        self.calls: list[tuple[str, str, dict[str, Any] | None]] = []

    async def get_states(self) -> list[dict[str, Any]]:
        """Stub: return no states."""
        return []

    async def get_state(self, entity_id: str) -> dict[str, Any] | None:
        """Stub: return ``None`` for every entity."""
        return None

    async def call_service(
        self,
        domain: str,
        service: str,
        data: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Record the call and return an empty state list."""
        self.calls.append((domain, service, data))
        return []

    async def close(self) -> None:
        """Stub: no resources to release."""


class _FakeWS:
    """`WebSocketPort` stub that records every command sent through it."""

    def __init__(self, *, connected: bool = True) -> None:
        """Initialise the connection flag and command log.

        Parameters
        ----------
        connected : bool, optional
            Initial value for `connected`. Tests use ``False`` to
            simulate a closed socket.
        """
        self._connected = connected
        self.commands: list[dict[str, Any]] = []

    @property
    def connected(self) -> bool:
        """Return the configured connection flag."""
        return self._connected

    async def connect(self) -> None:
        """Stub: no-op connect."""

    async def close(self) -> None:
        """Stub: no-op close."""

    async def send_command(self, payload: dict[str, Any], *, timeout: float | None = None) -> Any:
        """Record *payload* and return a fixed ``"ws-result"`` token."""
        self.commands.append(payload)
        return "ws-result"

    async def subscribe_events(self, handler: Any, event_type: str | None = None) -> int:
        """Stub: return a fixed subscription id of ``0``."""
        return 0

    async def unsubscribe(self, subscription_id: int) -> None:
        """Stub: no-op unsubscribe."""

    def on_disconnect(self, handler: Any) -> Any:
        """Stub: return *handler* unchanged."""
        return handler

    def on_reconnect(self, handler: Any) -> Any:
        """Stub: return *handler* unchanged."""
        return handler


async def test_default_policy_attribute() -> None:
    sc = ServiceCaller(_FakeRest(), _FakeWS(), default_policy="rest")  # type: ignore[arg-type]
    assert sc.default_policy == "rest"


async def test_ws_property_exposed() -> None:
    rest = _FakeRest()
    ws = _FakeWS()
    sc = ServiceCaller(rest, ws)  # type: ignore[arg-type]
    assert sc.ws is ws
    assert sc.rest is rest


async def test_prefer_ws_when_connected_sends_payload_with_data() -> None:
    sc = ServiceCaller(_FakeRest(), _FakeWS())  # type: ignore[arg-type]
    await sc.call("light", "turn_on", {"entity_id": "light.x", "brightness": 50})
    cmd = sc.ws.commands[0]  # type: ignore[attr-defined]
    assert cmd["type"] == "call_service"
    assert cmd["service_data"] == {"entity_id": "light.x", "brightness": 50}


async def test_prefer_ws_without_data_omits_service_data() -> None:
    sc = ServiceCaller(_FakeRest(), _FakeWS())  # type: ignore[arg-type]
    await sc.call("light", "turn_off", prefer="ws")
    cmd = sc.ws.commands[0]  # type: ignore[attr-defined]
    assert "service_data" not in cmd


async def test_prefer_rest_uses_rest_even_when_ws_connected() -> None:
    rest = _FakeRest()
    ws = _FakeWS(connected=True)
    sc = ServiceCaller(rest, ws)  # type: ignore[arg-type]
    await sc.call("switch", "toggle", prefer="rest")
    assert rest.calls == [("switch", "toggle", None)]
    assert ws.commands == []


async def test_prefer_ws_disconnected_raises() -> None:
    sc = ServiceCaller(_FakeRest(), _FakeWS(connected=False))  # type: ignore[arg-type]
    with pytest.raises(ConnectionClosedError):
        await sc.call("light", "turn_on", prefer="ws")


async def test_auto_falls_back_to_rest_when_disconnected() -> None:
    rest = _FakeRest()
    ws = _FakeWS(connected=False)
    sc = ServiceCaller(rest, ws)  # type: ignore[arg-type]
    await sc.call("light", "turn_on")
    assert rest.calls == [("light", "turn_on", None)]


async def test_default_policy_used_when_prefer_none() -> None:
    rest = _FakeRest()
    ws = _FakeWS()
    sc = ServiceCaller(rest, ws, default_policy="rest")  # type: ignore[arg-type]
    await sc.call("light", "turn_on")
    assert rest.calls
    assert ws.commands == []
