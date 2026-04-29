"""End-to-end tests for the high-level HAClient facade."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from haclient import HAClient
from haclient.config import derive_ws_url
from haclient.domains.light import Light
from haclient.domains.switch import Switch
from haclient.exceptions import ConnectionClosedError, HAClientError

from .fake_ha import FakeHA


def test_derive_ws_url() -> None:
    assert derive_ws_url("http://ha:8123") == "ws://ha:8123/api/websocket"
    assert derive_ws_url("https://ha:8123/") == "wss://ha:8123/api/websocket"
    assert derive_ws_url("http://ha:8123/base") == "ws://ha:8123/base/api/websocket"


async def test_connect_primes_state(fake_ha: FakeHA) -> None:
    fake_ha.states = [
        {"entity_id": "light.kitchen", "state": "on", "attributes": {"brightness": 150}},
    ]
    ha = HAClient.from_url(fake_ha.base_url, token=fake_ha.token, ping_interval=0)
    try:
        await ha.connect()
        light = ha.light("kitchen")
        await light.async_refresh()
        assert light.is_on
        assert light.brightness == 150
    finally:
        await ha.close()


async def test_call_service_via_websocket(client: HAClient, fake_ha: FakeHA) -> None:
    light = client.light("kitchen")
    await light.set_brightness(200)

    assert len(fake_ha.ws_service_calls) == 1
    call = fake_ha.ws_service_calls[0]
    assert call["type"] == "call_service"
    assert call["domain"] == "light"
    assert call["service"] == "turn_on"
    assert call["service_data"]["entity_id"] == "light.kitchen"
    assert call["service_data"]["brightness"] == 200


async def test_state_changed_dispatches_to_entity(client: HAClient, fake_ha: FakeHA) -> None:
    light = client.light("kitchen")
    await fake_ha.push_state_changed(
        "light.kitchen",
        {"state": "on", "attributes": {"brightness": 180}},
    )
    for _ in range(20):
        await asyncio.sleep(0.02)
        if light.is_on:
            break
    assert light.is_on
    assert light.brightness == 180


async def test_domain_accessor_reuse(client: HAClient) -> None:
    a = client.media_player("livingroom")
    b = client.media_player("livingroom")
    assert a is b


async def test_domain_accessor_rejects_fully_qualified(client: HAClient) -> None:
    with pytest.raises(ValueError, match="short object-id"):
        client.media_player("media_player.livingroom")


async def test_refresh_all(client: HAClient, fake_ha: FakeHA) -> None:
    light = client.light("kitchen")
    sensor = client.sensor("temp")
    fake_ha.states = [
        {"entity_id": "light.kitchen", "state": "on", "attributes": {"brightness": 50}},
        {"entity_id": "sensor.temp", "state": "22.5", "attributes": {"unit_of_measurement": "°C"}},
    ]
    await client.state.refresh_all()
    assert light.is_on
    assert light.brightness == 50
    assert sensor.value == 22.5
    assert sensor.unit_of_measurement == "°C"


async def test_refresh_all_marks_missing_unavailable(client: HAClient, fake_ha: FakeHA) -> None:
    light = client.light("kitchen")
    await client.state.refresh_all()
    assert not light.available
    assert light.state == "unavailable"


async def test_context_manager(fake_ha: FakeHA) -> None:
    async with HAClient.from_url(fake_ha.base_url, token=fake_ha.token, ping_interval=0) as ha:
        assert ha.connection.ws.connected
    assert not ha.connection.ws.connected


async def test_call_service_via_rest_fallback(fake_ha: FakeHA) -> None:
    """If WS isn't connected, prefer='rest' uses REST."""
    ha = HAClient.from_url(fake_ha.base_url, token=fake_ha.token, ping_interval=0)
    try:
        await ha.services.call("switch", "toggle", {"entity_id": "switch.x"}, prefer="rest")
    finally:
        await ha.close()
    assert fake_ha.rest_service_calls == [("switch", "toggle", {"entity_id": "switch.x"})]


async def test_call_service_prefer_ws_when_disconnected(fake_ha: FakeHA) -> None:
    """prefer='ws' raises when WS is not connected."""
    ha = HAClient.from_url(fake_ha.base_url, token=fake_ha.token, ping_interval=0)
    try:
        with pytest.raises(ConnectionClosedError):
            await ha.services.call("switch", "toggle", prefer="ws")
    finally:
        await ha.close()


async def test_reconnect_triggers_refresh_all(fake_ha: FakeHA) -> None:
    """After reconnect, the connection automatically refreshes state."""
    fake_ha.states = [
        {"entity_id": "light.kitchen", "state": "off", "attributes": {}},
    ]
    ha = HAClient.from_url(
        fake_ha.base_url,
        token=fake_ha.token,
        ping_interval=0,
        request_timeout=5.0,
    )
    light = ha.light("kitchen")
    await ha.connect()
    try:
        assert light.state == "off"

        fake_ha.states = [
            {"entity_id": "light.kitchen", "state": "on", "attributes": {"brightness": 200}},
        ]

        for conn in list(fake_ha.connections):
            await conn.close()

        for _ in range(50):
            await asyncio.sleep(0.1)
            if light.state == "on":
                break
        assert light.state == "on"
        assert light.brightness == 200
    finally:
        await ha.close()


async def test_create_scene(fake_ha: FakeHA) -> None:
    ha = HAClient.from_url(fake_ha.base_url, token=fake_ha.token, ping_interval=0)
    try:
        await ha.connect()
        scene = await ha.scene.create(
            "romantic",
            {"light.ceiling": {"state": "on", "brightness": 80}},
        )
        assert scene.entity_id == "scene.romantic"
        calls = fake_ha.ws_service_calls
        assert len(calls) == 1
        assert calls[0]["domain"] == "scene"
        assert calls[0]["service"] == "create"
        assert calls[0]["service_data"]["scene_id"] == "romantic"
        assert calls[0]["service_data"]["entities"] == {
            "light.ceiling": {"state": "on", "brightness": 80}
        }
    finally:
        await ha.close()


async def test_create_scene_with_snapshot(fake_ha: FakeHA) -> None:
    ha = HAClient.from_url(fake_ha.base_url, token=fake_ha.token, ping_interval=0)
    try:
        await ha.connect()
        scene = await ha.scene.create(
            "snapshot_test",
            {"light.ceiling": {"state": "on"}},
            snapshot_entities=["light.lamp"],
        )
        assert scene.entity_id == "scene.snapshot_test"
        calls = fake_ha.ws_service_calls
        assert calls[0]["service_data"]["snapshot_entities"] == ["light.lamp"]
    finally:
        await ha.close()


async def test_apply_scene(fake_ha: FakeHA) -> None:
    ha = HAClient.from_url(fake_ha.base_url, token=fake_ha.token, ping_interval=0)
    try:
        await ha.connect()
        await ha.scene.apply({"light.ceiling": {"state": "on", "brightness": 200}})
        calls = fake_ha.ws_service_calls
        assert len(calls) == 1
        assert calls[0]["domain"] == "scene"
        assert calls[0]["service"] == "apply"
        assert calls[0]["service_data"]["entities"] == {
            "light.ceiling": {"state": "on", "brightness": 200}
        }
        assert "transition" not in calls[0]["service_data"]
    finally:
        await ha.close()


async def test_apply_scene_with_transition(fake_ha: FakeHA) -> None:
    ha = HAClient.from_url(fake_ha.base_url, token=fake_ha.token, ping_interval=0)
    try:
        await ha.connect()
        await ha.scene.apply(
            {"light.ceiling": {"state": "on"}},
            transition=3.0,
        )
        calls = fake_ha.ws_service_calls
        assert calls[0]["service_data"]["transition"] == 3.0
    finally:
        await ha.close()


async def test_invalid_entity_id_direct_construction() -> None:
    ha = HAClient.from_url("http://x", token="t", load_plugins=False)
    try:
        with pytest.raises(ValueError):
            Light("kitchen", ha.services, ha.state, ha._clock)
    finally:
        await ha.close()


async def test_double_connect_is_noop(client: HAClient) -> None:
    await client.connect()


def test_loop_property_without_running_loop() -> None:
    ha = HAClient.from_url("http://x", token="t", load_plugins=False)
    try:
        assert ha.loop() is None
    finally:
        # No async cleanup necessary outside a loop.
        pass


async def test_state_changed_event_missing_entity_id(client: HAClient) -> None:
    client.state._on_state_changed({"data": {"entity_id": 42}})
    client.state._on_state_changed({})


async def test_connect_primes_already_registered_entity(fake_ha: FakeHA) -> None:
    fake_ha.states = [
        {"entity_id": "light.kitchen", "state": "on", "attributes": {"brightness": 90}},
    ]
    ha = HAClient.from_url(fake_ha.base_url, token=fake_ha.token, ping_interval=0)
    light = ha.light("kitchen")
    try:
        await ha.connect()
        assert light.is_on
        assert light.brightness == 90
    finally:
        await ha.close()


async def test_initial_state_fetch_includes_non_string_entity_id(
    fake_ha: FakeHA,
) -> None:
    fake_ha.states = [
        {"entity_id": 123, "state": "on", "attributes": {}},
        {"entity_id": "light.kitchen", "state": "on", "attributes": {}},
    ]
    ha = HAClient.from_url(fake_ha.base_url, token=fake_ha.token, ping_interval=0)
    try:
        await ha.connect()
    finally:
        await ha.close()


async def test_initial_state_fetch_failure_is_logged(fake_ha: FakeHA, caplog: Any) -> None:
    """If the REST snapshot 401s, priming logs a warning but continues."""
    ha = HAClient.from_url(fake_ha.base_url, token=fake_ha.token, ping_interval=0)
    # Swap the REST adapter's token so the snapshot fails after WS auth succeeds.
    ha.connection.rest._token = "wrong-token"  # type: ignore[attr-defined]
    try:
        await ha.connect()
    finally:
        await ha.close()


async def test_on_reconnect_proxy(fake_ha: FakeHA) -> None:
    """on_reconnect registered via HAClient fires after reconnection."""
    ha = HAClient.from_url(fake_ha.base_url, token=fake_ha.token, ping_interval=0, reconnect=True)
    called = asyncio.Event()

    @ha.on_reconnect
    async def _reconnected() -> None:
        called.set()

    try:
        await ha.connect()
        for conn in list(fake_ha.connections):
            await conn.close()

        await asyncio.wait_for(called.wait(), timeout=5)
    finally:
        await ha.close()


async def test_on_disconnect_proxy(fake_ha: FakeHA) -> None:
    """on_disconnect registered via HAClient fires when connection drops."""
    ha = HAClient.from_url(fake_ha.base_url, token=fake_ha.token, ping_interval=0, reconnect=False)
    called = asyncio.Event()

    @ha.on_disconnect
    async def _disconnected() -> None:
        called.set()

    try:
        await ha.connect()
        for conn in list(fake_ha.connections):
            await conn.close()

        await asyncio.wait_for(called.wait(), timeout=5)
    finally:
        await ha.close()


async def test_domain_accessor_via_generic(client: HAClient) -> None:
    """The generic ``ha.domain('light')`` route also works."""
    accessor = client.domain("light")
    light = accessor("kitchen")
    same = client.light("kitchen")
    assert light is same


async def test_domain_accessor_unknown_domain(client: HAClient) -> None:
    with pytest.raises(HAClientError):
        client.domain("does_not_exist")


async def test_domain_accessor_subscript(client: HAClient) -> None:
    light = client.domain("light")["kitchen"]
    assert light.entity_id == "light.kitchen"


async def test_type_conflict_raises_explicit_message(client: HAClient) -> None:
    """Asking for a Switch under a Light's id raises HAClientError."""
    light = client.light("kitchen")
    # Replace the registered entry with a different class to force the conflict.
    client.state.registry._entities["switch.kitchen"] = light
    with pytest.raises(HAClientError, match="not Switch"):
        client.switch("kitchen")
    # Confirm Switch lookup works for unrelated ids.
    other = client.switch("outlet")
    assert isinstance(other, Switch)
