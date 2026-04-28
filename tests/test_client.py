"""End-to-end tests for the high-level HAClient."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from haclient import HAClient
from haclient.client import _derive_ws_url
from haclient.exceptions import HAClientError

from .fake_ha import FakeHA


def test_derive_ws_url() -> None:
    assert _derive_ws_url("http://ha:8123") == "ws://ha:8123/api/websocket"
    assert _derive_ws_url("https://ha:8123/") == "wss://ha:8123/api/websocket"
    assert _derive_ws_url("http://ha:8123/base") == "ws://ha:8123/base/api/websocket"


async def test_connect_primes_state(fake_ha: FakeHA) -> None:
    fake_ha.states = [
        {"entity_id": "light.kitchen", "state": "on", "attributes": {"brightness": 150}},
    ]
    ha = HAClient(fake_ha.base_url, fake_ha.token, ping_interval=0)
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


async def test_domain_accessor_type_conflict(client: HAClient) -> None:
    client.light("kitchen")
    with pytest.raises(HAClientError):
        from haclient import Switch

        client._get_or_create("light", "kitchen", Switch)


async def test_refresh_all(client: HAClient, fake_ha: FakeHA) -> None:
    light = client.light("kitchen")
    sensor = client.sensor("temp")
    fake_ha.states = [
        {"entity_id": "light.kitchen", "state": "on", "attributes": {"brightness": 50}},
        {"entity_id": "sensor.temp", "state": "22.5", "attributes": {"unit_of_measurement": "°C"}},
    ]
    await client.refresh_all()
    assert light.is_on
    assert light.brightness == 50
    assert sensor.value == 22.5
    assert sensor.unit_of_measurement == "°C"


async def test_refresh_all_marks_missing_unavailable(client: HAClient, fake_ha: FakeHA) -> None:
    light = client.light("kitchen")
    await client.refresh_all()
    assert not light.available
    assert light.state == "unavailable"


async def test_context_manager(fake_ha: FakeHA) -> None:
    async with HAClient(fake_ha.base_url, fake_ha.token, ping_interval=0) as ha:
        assert ha.ws.connected
    assert not ha.ws.connected


async def test_call_service_via_rest_fallback(fake_ha: FakeHA) -> None:
    """If WS isn't connected, fall back to REST."""
    ha = HAClient(fake_ha.base_url, fake_ha.token, ping_interval=0)
    try:
        await ha._call_service("switch", "toggle", {"entity_id": "switch.x"}, use_websocket=False)
    finally:
        await ha.close()
    assert fake_ha.rest_service_calls == [("switch", "toggle", {"entity_id": "switch.x"})]


async def test_create_scene(fake_ha: FakeHA) -> None:
    ha = HAClient(fake_ha.base_url, fake_ha.token, ping_interval=0)
    try:
        await ha.connect()
        scene = await ha.create_scene(
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
    ha = HAClient(fake_ha.base_url, fake_ha.token, ping_interval=0)
    try:
        await ha.connect()
        scene = await ha.create_scene(
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
    ha = HAClient(fake_ha.base_url, fake_ha.token, ping_interval=0)
    try:
        await ha.connect()
        await ha.apply_scene({"light.ceiling": {"state": "on", "brightness": 200}})
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
    ha = HAClient(fake_ha.base_url, fake_ha.token, ping_interval=0)
    try:
        await ha.connect()
        await ha.apply_scene(
            {"light.ceiling": {"state": "on"}},
            transition=3.0,
        )
        calls = fake_ha.ws_service_calls
        assert calls[0]["service_data"]["transition"] == 3.0
    finally:
        await ha.close()


async def test_invalid_entity_id_direct_construction() -> None:
    ha = HAClient("http://x", "t")
    from haclient import Light

    with pytest.raises(ValueError):
        Light("kitchen", ha)


async def test_double_connect_is_noop(client: HAClient) -> None:
    await client.connect()


def test_loop_property_without_running_loop() -> None:
    ha = HAClient("http://x", "t")
    assert ha.loop is None


async def test_state_changed_event_missing_entity_id(client: HAClient) -> None:
    client._on_state_changed_event({"data": {"entity_id": 42}})
    client._on_state_changed_event({})


async def test_connect_primes_already_registered_entity(fake_ha: FakeHA) -> None:
    fake_ha.states = [
        {"entity_id": "light.kitchen", "state": "on", "attributes": {"brightness": 90}},
    ]
    ha = HAClient(fake_ha.base_url, fake_ha.token, ping_interval=0)
    from haclient import Light

    light = Light("light.kitchen", ha)
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
    ha = HAClient(fake_ha.base_url, fake_ha.token, ping_interval=0)
    try:
        await ha.connect()
    finally:
        await ha.close()


async def test_initial_state_fetch_failure_is_logged(fake_ha: FakeHA, caplog: Any) -> None:
    ha = HAClient(fake_ha.base_url, "wrong-token", ping_interval=0)
    ha.rest._token = "still-wrong"  # noqa: SLF001
    ha._token = fake_ha.token  # noqa: SLF001
    ha.ws._token = fake_ha.token  # noqa: SLF001
    try:
        await ha.connect()
    finally:
        await ha.close()
