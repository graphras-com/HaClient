"""Tests covering the basic domain wrapper classes."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from haclient import HAClient

from .fake_ha import FakeHA


def _find_call(fake_ha: FakeHA, service: str) -> dict[str, Any]:
    for call in fake_ha.ws_service_calls:
        if call["service"] == service:
            return call
    raise AssertionError(f"No call_service for service={service}")


async def test_light_actions(client: HAClient, fake_ha: FakeHA) -> None:
    light = client.light("kitchen")
    await light.on()
    await light.set_brightness(120)
    await light.set_rgb(1, 2, 3)
    await light.off(transition=0.5)
    await light.toggle()
    await light.set_kelvin(4000)
    assert [c["service"] for c in fake_ha.ws_service_calls] == [
        "turn_on",
        "turn_on",
        "turn_on",
        "turn_off",
        "toggle",
        "turn_on",
    ]
    second = fake_ha.ws_service_calls[1]["service_data"]
    assert second["brightness"] == 120
    third = fake_ha.ws_service_calls[2]["service_data"]
    assert third["rgb_color"] == [1, 2, 3]
    kelvin_call = fake_ha.ws_service_calls[5]["service_data"]
    assert kelvin_call["color_temp_kelvin"] == 4000


async def test_light_state_properties() -> None:
    ha = HAClient("http://x", "t")
    try:
        light = ha.light("kitchen")
        light._apply_state(
            {
                "state": "on",
                "attributes": {
                    "brightness": 99,
                    "rgb_color": [1, 2, 3],
                    "color_temp_kelvin": 4000,
                    "min_color_temp_kelvin": 2000,
                    "max_color_temp_kelvin": 6500,
                },
            }
        )
        assert light.is_on
        assert light.brightness == 99
        assert light.rgb_color == (1, 2, 3)
        assert light.kelvin == 4000
        assert light.min_kelvin == 2000
        assert light.max_kelvin == 6500
        light._apply_state({"state": "off", "attributes": {}})
        assert not light.is_on
        assert light.brightness is None
        assert light.rgb_color is None
        assert light.kelvin is None
        assert light.min_kelvin is None
        assert light.max_kelvin is None
    finally:
        await ha.close()


async def test_light_set_brightness(client: HAClient, fake_ha: FakeHA) -> None:
    light = client.light("kitchen")
    await light.set_brightness(200)
    await light.set_brightness(100, transition=2.0)
    calls = fake_ha.ws_service_calls
    assert calls[0]["service"] == "turn_on"
    assert calls[0]["service_data"]["brightness"] == 200
    assert "transition" not in calls[0]["service_data"]
    assert calls[1]["service_data"]["brightness"] == 100
    assert calls[1]["service_data"]["transition"] == 2.0


async def test_light_set_kelvin(client: HAClient, fake_ha: FakeHA) -> None:
    light = client.light("kitchen")
    await light.set_kelvin(4000)
    await light.set_kelvin(3000, transition=1.0)
    calls = fake_ha.ws_service_calls
    assert calls[0]["service_data"]["color_temp_kelvin"] == 4000
    assert calls[1]["service_data"]["color_temp_kelvin"] == 3000
    assert calls[1]["service_data"]["transition"] == 1.0


async def test_light_set_rgb(client: HAClient, fake_ha: FakeHA) -> None:
    light = client.light("kitchen")
    await light.set_rgb(255, 0, 128)
    await light.set_rgb(0, 255, 0, transition=0.5)
    calls = fake_ha.ws_service_calls
    assert calls[0]["service_data"]["rgb_color"] == [255, 0, 128]
    assert calls[1]["service_data"]["rgb_color"] == [0, 255, 0]
    assert calls[1]["service_data"]["transition"] == 0.5


async def test_light_set_color_rgb(client: HAClient, fake_ha: FakeHA) -> None:
    light = client.light("kitchen")
    await light.set_color(rgb=(10, 20, 30))
    call = fake_ha.ws_service_calls[0]
    assert call["service_data"]["rgb_color"] == [10, 20, 30]


async def test_light_set_color_kelvin(client: HAClient, fake_ha: FakeHA) -> None:
    light = client.light("kitchen")
    await light.set_color(kelvin=5000, transition=1.0)
    call = fake_ha.ws_service_calls[0]
    assert call["service_data"]["color_temp_kelvin"] == 5000
    assert call["service_data"]["transition"] == 1.0


async def test_light_on_off(client: HAClient, fake_ha: FakeHA) -> None:
    light = client.light("kitchen")
    await light.on()
    await light.on(transition=1.0)
    await light.off()
    await light.off(transition=0.5)
    calls = fake_ha.ws_service_calls
    assert calls[0]["service"] == "turn_on"
    assert "transition" not in calls[0].get("service_data", {})
    assert calls[1]["service_data"]["transition"] == 1.0
    assert calls[2]["service"] == "turn_off"
    assert calls[3]["service_data"]["transition"] == 0.5


async def test_light_set_color_requires_exactly_one(client: HAClient, fake_ha: FakeHA) -> None:
    light = client.light("kitchen")
    with pytest.raises(ValueError, match="Exactly one"):
        await light.set_color()
    with pytest.raises(ValueError, match="Exactly one"):
        await light.set_color(rgb=(1, 2, 3), kelvin=4000)


async def test_switch_actions(client: HAClient, fake_ha: FakeHA) -> None:
    sw = client.switch("outlet")
    await sw.on()
    await sw.off()
    await sw.toggle()
    assert [c["service"] for c in fake_ha.ws_service_calls] == [
        "turn_on",
        "turn_off",
        "toggle",
    ]
    sw._apply_state({"state": "on", "attributes": {}})
    assert sw.is_on


async def test_climate_actions(client: HAClient, fake_ha: FakeHA) -> None:
    c = client.climate("main")
    await c.set_temperature(21.5, hvac_mode="heat")
    await c.set_hvac_mode("cool")
    await c.set_fan_mode("auto")
    await c.set_hvac_mode("off")
    calls = fake_ha.ws_service_calls
    assert calls[0]["service"] == "set_temperature"
    assert calls[0]["service_data"]["temperature"] == 21.5
    assert calls[0]["service_data"]["hvac_mode"] == "heat"
    assert calls[1]["service_data"]["hvac_mode"] == "cool"
    assert calls[2]["service_data"]["fan_mode"] == "auto"
    assert calls[3]["service_data"]["hvac_mode"] == "off"

    c._apply_state(
        {
            "state": "heat",
            "attributes": {
                "current_temperature": 20.1,
                "temperature": 22.0,
                "hvac_modes": ["off", "heat", "cool"],
            },
        }
    )
    assert c.current_temperature == 20.1
    assert c.target_temperature == 22.0
    assert c.hvac_mode == "heat"
    assert c.hvac_modes == ["off", "heat", "cool"]


async def test_cover_actions(client: HAClient, fake_ha: FakeHA) -> None:
    cv = client.cover("garage")
    await cv.open()
    await cv.close()
    await cv.stop()
    await cv.set_position(40)
    await cv.toggle()
    svc = [c["service"] for c in fake_ha.ws_service_calls]
    assert svc == ["open_cover", "close_cover", "stop_cover", "set_cover_position", "toggle"]

    cv._apply_state({"state": "open", "attributes": {"current_position": 75}})
    assert cv.is_open
    assert not cv.is_closed
    assert cv.current_position == 75
    cv._apply_state({"state": "closed", "attributes": {}})
    assert cv.is_closed
    assert cv.current_position is None


async def test_sensor_values() -> None:
    ha = HAClient("http://x", "t")
    try:
        s = ha.sensor("temp")
        s._apply_state(
            {
                "state": "22.5",
                "attributes": {"unit_of_measurement": "°C", "device_class": "temperature"},
            }
        )
        assert s.value == 22.5
        assert s.unit_of_measurement == "°C"
        assert s.device_class == "temperature"
        s._apply_state({"state": "text", "attributes": {}})
        assert s.value == "text"
        s._apply_state(None)
        assert s.value is None
        assert s.device_class is None
    finally:
        await ha.close()


async def test_binary_sensor_values() -> None:
    ha = HAClient("http://x", "t")
    try:
        b = ha.binary_sensor("door")
        b._apply_state({"state": "on", "attributes": {"device_class": "door"}})
        assert b.is_on
        assert b.device_class == "door"
        b._apply_state({"state": "off", "attributes": {}})
        assert not b.is_on
        assert b.device_class is None
    finally:
        await ha.close()


async def test_media_player_volume_bounds(client: HAClient) -> None:
    mp = client.media_player("livingroom")
    with pytest.raises(ValueError):
        await mp.set_volume(1.5)
    with pytest.raises(ValueError):
        await mp.set_volume(-0.1)


async def test_media_player_playback(client: HAClient, fake_ha: FakeHA) -> None:
    mp = client.media_player("livingroom")
    await mp.play()
    await mp.pause()
    await mp.play_pause()
    await mp.stop()
    await mp.next()
    await mp.previous()
    await mp.set_volume(0.5)
    await mp.mute(True)
    await mp.power_on()
    await mp.power_off()
    await mp.select_source("Spotify")
    services = [c["service"] for c in fake_ha.ws_service_calls]
    assert services == [
        "media_play",
        "media_pause",
        "media_play_pause",
        "media_stop",
        "media_next_track",
        "media_previous_track",
        "volume_set",
        "volume_mute",
        "turn_on",
        "turn_off",
        "select_source",
    ]


async def test_media_player_state_props() -> None:
    ha = HAClient("http://x", "t")
    try:
        mp = ha.media_player("livingroom")
        mp._apply_state(
            {
                "state": "playing",
                "attributes": {
                    "volume_level": 0.3,
                    "source": "Spotify",
                    "is_volume_muted": True,
                },
            }
        )
        assert mp.is_playing
        assert not mp.is_paused
        assert mp.is_muted
        assert mp.volume_level == 0.3
        assert mp.now_playing.source == "Spotify"
        mp._apply_state({"state": "paused", "attributes": {}})
        assert mp.is_paused
        assert not mp.is_muted
        assert mp.volume_level is None
        assert mp.now_playing.source is None
    finally:
        await ha.close()


async def test_entity_refresh_via_rest(client: HAClient, fake_ha: FakeHA) -> None:
    fake_ha.states = [
        {"entity_id": "light.kitchen", "state": "on", "attributes": {"brightness": 77}}
    ]
    light = client.light("kitchen")
    await light.async_refresh()
    assert light.brightness == 77


async def test_entity_refresh_missing(client: HAClient) -> None:
    light = client.light("missing")
    await light.async_refresh()
    assert light.state == "unavailable"


async def test_timer_actions(client: HAClient, fake_ha: FakeHA) -> None:
    t = client.timer("my_timer")
    await t.start()
    await t.start(duration="00:05:00")
    await t.pause()
    await t.cancel()
    await t.finish()
    await t.change(duration="00:01:00")
    assert [c["service"] for c in fake_ha.ws_service_calls] == [
        "start",
        "start",
        "pause",
        "cancel",
        "finish",
        "change",
    ]
    # First start has no extra service_data beyond entity_id
    assert "duration" not in fake_ha.ws_service_calls[0].get("service_data", {})
    # Second start carries duration
    assert fake_ha.ws_service_calls[1]["service_data"]["duration"] == "00:05:00"
    # Change carries duration
    assert fake_ha.ws_service_calls[5]["service_data"]["duration"] == "00:01:00"


async def test_timer_state_properties() -> None:
    ha = HAClient("http://x", "t")
    try:
        t = ha.timer("my_timer")
        t._apply_state(
            {
                "state": "active",
                "attributes": {
                    "duration": "0:05:00",
                    "remaining": "0:04:30",
                    "finishes_at": "2024-01-01T12:05:00+00:00",
                },
            }
        )
        assert t.is_active
        assert not t.is_paused
        assert not t.is_idle
        assert t.duration == "0:05:00"
        assert t.remaining == "0:04:30"
        assert t.finishes_at == "2024-01-01T12:05:00+00:00"

        t._apply_state(
            {
                "state": "paused",
                "attributes": {"duration": "0:05:00", "remaining": "0:03:00"},
            }
        )
        assert not t.is_active
        assert t.is_paused
        assert not t.is_idle
        assert t.remaining == "0:03:00"
        assert t.finishes_at is None

        t._apply_state({"state": "idle", "attributes": {"duration": "0:05:00"}})
        assert not t.is_active
        assert not t.is_paused
        assert t.is_idle
        assert t.remaining is None
        assert t.finishes_at is None
    finally:
        await ha.close()


async def test_scene_activate(client: HAClient, fake_ha: FakeHA) -> None:
    sc = client.scene("romantic")
    await sc.activate()
    await sc.activate(transition=2.5)
    calls = fake_ha.ws_service_calls
    assert [c["service"] for c in calls] == ["turn_on", "turn_on"]
    assert "service_data" not in calls[0] or "transition" not in calls[0].get("service_data", {})
    assert calls[1]["service_data"]["transition"] == 2.5


async def test_scene_state_properties() -> None:
    ha = HAClient("http://x", "t")
    try:
        sc = ha.scene("romantic")
        sc._apply_state(
            {
                "state": "2024-06-15T20:30:00+00:00",
                "attributes": {
                    "friendly_name": "Romantic",
                    "icon": "mdi:candle",
                    "entity_id": ["light.ceiling", "light.lamp"],
                },
            }
        )
        assert sc.last_activated == "2024-06-15T20:30:00+00:00"
        assert sc.name == "Romantic"
        assert sc.icon == "mdi:candle"
        assert sc.entity_ids == ["light.ceiling", "light.lamp"]
    finally:
        await ha.close()


async def test_scene_unavailable_state() -> None:
    ha = HAClient("http://x", "t")
    try:
        sc = ha.scene("broken")
        sc._apply_state({"state": "unavailable", "attributes": {}})
        assert sc.last_activated is None
        sc._apply_state({"state": "unknown", "attributes": {}})
        assert sc.last_activated is None
    finally:
        await ha.close()


async def test_scene_empty_attributes() -> None:
    ha = HAClient("http://x", "t")
    try:
        sc = ha.scene("minimal")
        sc._apply_state(
            {
                "state": "2024-01-01T00:00:00+00:00",
                "attributes": {},
            }
        )
        assert sc.entity_ids == []
        assert sc.name is None
        assert sc.icon is None
    finally:
        await ha.close()


async def test_scene_on_activate_listener(client: HAClient, fake_ha: FakeHA) -> None:
    sc = client.scene("romantic")
    fired: list[tuple[Any, Any]] = []

    @sc.on_activate
    def _listener(old: Any, new: Any) -> None:
        fired.append((old, new))

    await fake_ha.push_state_changed(
        "scene.romantic",
        old_state={"state": "2024-06-15T20:00:00+00:00", "attributes": {}},
        new_state={"state": "2024-06-15T20:30:00+00:00", "attributes": {}},
    )
    await asyncio.sleep(0.05)
    assert len(fired) == 1
    assert fired[0][1] == "2024-06-15T20:30:00+00:00"
