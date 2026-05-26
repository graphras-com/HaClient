"""Tests covering the basic domain wrapper classes."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from haclient import HAClient

from .fake_ha import FakeHA


def _find_call(fake_ha: FakeHA, service: str) -> dict[str, Any]:
    """Return the first WS ``call_service`` payload for *service*.

    Parameters
    ----------
    fake_ha : FakeHA
        The fake server whose `ws_service_calls` log to search.
    service : str
        The service name to match (e.g. ``"turn_on"``).

    Returns
    -------
    dict
        The recorded payload.

    Raises
    ------
    AssertionError
        If no matching call is found, so that test failures point at
        the missing service rather than indexing on an empty result.
    """
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
    ha = HAClient.from_url("http://x", token="t", load_plugins=False)
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
    ha = HAClient.from_url("http://x", token="t", load_plugins=False)
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
    ha = HAClient.from_url("http://x", token="t", load_plugins=False)
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
    ha = HAClient.from_url("http://x", token="t", load_plugins=False)
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


async def test_now_playing_entity_picture_absolute_url() -> None:
    """entity_picture is resolved to an absolute URL using the client base_url."""
    ha = HAClient.from_url("http://ha.local:8123", token="t", load_plugins=False)
    try:
        mp = ha.media_player("livingroom")
        mp._apply_state(
            {
                "state": "playing",
                "attributes": {
                    "entity_picture": "/api/media_player_proxy/media_player.livingroom",
                },
            }
        )
        assert (
            mp.now_playing.entity_picture
            == "http://ha.local:8123/api/media_player_proxy/media_player.livingroom"
        )
    finally:
        await ha.close()


async def test_now_playing_entity_picture_already_absolute() -> None:
    """entity_picture that is already absolute is left unchanged."""
    ha = HAClient.from_url("http://ha.local:8123", token="t", load_plugins=False)
    try:
        mp = ha.media_player("livingroom")
        mp._apply_state(
            {
                "state": "playing",
                "attributes": {
                    "entity_picture": "https://cdn.example.com/art.jpg",
                },
            }
        )
        assert mp.now_playing.entity_picture == "https://cdn.example.com/art.jpg"
    finally:
        await ha.close()


async def test_now_playing_entity_picture_none() -> None:
    """entity_picture is None when not present."""
    ha = HAClient.from_url("http://ha.local:8123", token="t", load_plugins=False)
    try:
        mp = ha.media_player("livingroom")
        mp._apply_state({"state": "playing", "attributes": {}})
        assert mp.now_playing.entity_picture is None
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
    ha = HAClient.from_url("http://x", token="t", load_plugins=False)
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
    ha = HAClient.from_url("http://x", token="t", load_plugins=False)
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
    ha = HAClient.from_url("http://x", token="t", load_plugins=False)
    try:
        sc = ha.scene("broken")
        sc._apply_state({"state": "unavailable", "attributes": {}})
        assert sc.last_activated is None
        sc._apply_state({"state": "unknown", "attributes": {}})
        assert sc.last_activated is None
    finally:
        await ha.close()


async def test_scene_empty_attributes() -> None:
    ha = HAClient.from_url("http://x", token="t", load_plugins=False)
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


async def test_scene_delete(client: HAClient, fake_ha: FakeHA) -> None:
    sc = client.scene("romantic")
    await sc.delete()
    calls = fake_ha.ws_service_calls
    assert len(calls) == 1
    assert calls[0]["domain"] == "scene"
    assert calls[0]["service"] == "delete"
    assert calls[0]["service_data"]["entity_id"] == "scene.romantic"


async def test_timer_time_remaining_active() -> None:
    """``time_remaining`` computes live seconds from ``finishes_at`` when active."""
    import datetime

    ha = HAClient.from_url("http://x", token="t", load_plugins=False)
    try:
        t = ha.timer("remaining_timer")
        # Set finishes_at to 120 seconds from now
        finish = datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=120)
        t._apply_state(
            {
                "state": "active",
                "attributes": {
                    "duration": "0:02:00",
                    "remaining": "0:02:00",
                    "finishes_at": finish.isoformat(),
                },
            }
        )
        rem = t.time_remaining
        assert rem is not None
        # Should be close to 120s (allow some tolerance for test execution)
        assert 118.0 <= rem <= 121.0
    finally:
        await ha.close()


async def test_timer_time_remaining_paused() -> None:
    """``time_remaining`` parses remaining attribute when paused."""
    ha = HAClient.from_url("http://x", token="t", load_plugins=False)
    try:
        t = ha.timer("paused_timer")
        t._apply_state(
            {
                "state": "paused",
                "attributes": {"duration": "0:05:00", "remaining": "0:03:30"},
            }
        )
        rem = t.time_remaining
        assert rem is not None
        assert rem == 210.0  # 3 min 30 sec
    finally:
        await ha.close()


async def test_timer_time_remaining_idle() -> None:
    """``time_remaining`` returns ``None`` when idle."""
    ha = HAClient.from_url("http://x", token="t", load_plugins=False)
    try:
        t = ha.timer("idle_timer")
        t._apply_state({"state": "idle", "attributes": {"duration": "0:05:00"}})
        assert t.time_remaining is None
    finally:
        await ha.close()


async def test_timer_time_remaining_missing_attrs() -> None:
    """``time_remaining`` returns ``None`` when attributes are missing."""
    ha = HAClient.from_url("http://x", token="t", load_plugins=False)
    try:
        t = ha.timer("no_attrs_timer")
        t._apply_state({"state": "active", "attributes": {}})
        assert t.time_remaining is None
        t._apply_state({"state": "paused", "attributes": {}})
        assert t.time_remaining is None
    finally:
        await ha.close()


async def test_timer_time_remaining_bad_finishes_at() -> None:
    """``time_remaining`` returns ``None`` for unparseable ``finishes_at``."""
    ha = HAClient.from_url("http://x", token="t", load_plugins=False)
    try:
        t = ha.timer("bad_timer")
        t._apply_state({"state": "active", "attributes": {"finishes_at": "not-a-date"}})
        assert t.time_remaining is None
    finally:
        await ha.close()


async def test_timer_time_remaining_bad_remaining() -> None:
    """``time_remaining`` returns ``None`` for unparseable ``remaining``."""
    ha = HAClient.from_url("http://x", token="t", load_plugins=False)
    try:
        t = ha.timer("bad_rem_timer")
        t._apply_state({"state": "paused", "attributes": {"remaining": "bad"}})
        assert t.time_remaining is None
    finally:
        await ha.close()


# ---------------------------------------------------------------------------
# Lock
# ---------------------------------------------------------------------------


async def test_lock_actions_and_state(client: HAClient, fake_ha: FakeHA) -> None:
    """``lock`` / ``unlock`` dispatch the expected services and state flags work."""
    door = client.lock("front_door")
    await door.lock()
    await door.unlock()
    svc = [c["service"] for c in fake_ha.ws_service_calls]
    assert svc == ["lock", "unlock"]
    assert all(c["domain"] == "lock" for c in fake_ha.ws_service_calls)
    assert all(
        c["service_data"]["entity_id"] == "lock.front_door" for c in fake_ha.ws_service_calls
    )

    door._apply_state({"state": "locked", "attributes": {}})
    assert door.is_locked
    assert not door.is_unlocked
    assert not door.is_jammed

    door._apply_state({"state": "unlocked", "attributes": {}})
    assert door.is_unlocked
    assert not door.is_locked

    door._apply_state({"state": "locking", "attributes": {}})
    assert door.is_locking

    door._apply_state({"state": "unlocking", "attributes": {}})
    assert door.is_unlocking

    door._apply_state({"state": "jammed", "attributes": {}})
    assert door.is_jammed


async def test_lock_open_supported(client: HAClient, fake_ha: FakeHA) -> None:
    """``open()`` dispatches ``lock.open`` when ``OPEN`` feature is advertised."""
    door = client.lock("smart_door")
    # Bit 1 = LockEntityFeature.OPEN.
    door._apply_state({"state": "locked", "attributes": {"supported_features": 1}})
    assert door.supports_open is True

    await door.open()
    services = [c["service"] for c in fake_ha.ws_service_calls]
    assert services == ["open"]


async def test_lock_open_unsupported_is_noop(client: HAClient, fake_ha: FakeHA) -> None:
    """``open()`` degrades safely when the hardware lacks the OPEN feature."""
    door = client.lock("basic_door")
    door._apply_state({"state": "locked", "attributes": {"supported_features": 0}})
    assert door.supports_open is False

    await door.open()
    assert fake_ha.ws_service_calls == []

    # Missing attribute entirely behaves the same.
    door._apply_state({"state": "locked", "attributes": {}})
    assert door.supports_open is False
    await door.open()
    assert fake_ha.ws_service_calls == []

    # Non-int ``supported_features`` is treated as unsupported.
    door._apply_state({"state": "locked", "attributes": {"supported_features": "1"}})
    assert door.supports_open is False


async def test_lock_listeners(client: HAClient, fake_ha: FakeHA) -> None:
    """Lock listener decorators fire on the relevant state transitions."""
    door = client.lock("hall")
    locked: list[tuple[Any, Any]] = []
    unlocked: list[tuple[Any, Any]] = []
    jammed: list[tuple[Any, Any]] = []

    @door.on_lock
    def _on_lock(old: Any, new: Any) -> None:
        locked.append((old, new))

    @door.on_unlock
    def _on_unlock(old: Any, new: Any) -> None:
        unlocked.append((old, new))

    @door.on_jam
    def _on_jam(old: Any, new: Any) -> None:
        jammed.append((old, new))

    await fake_ha.push_state_changed(
        "lock.hall",
        {"state": "locked", "attributes": {}},
        {"state": "unlocked", "attributes": {}},
    )
    await fake_ha.push_state_changed(
        "lock.hall",
        {"state": "unlocked", "attributes": {}},
        {"state": "locked", "attributes": {}},
    )
    await fake_ha.push_state_changed(
        "lock.hall",
        {"state": "jammed", "attributes": {}},
        {"state": "locked", "attributes": {}},
    )
    await asyncio.sleep(0.05)

    assert locked == [("unlocked", "locked")]
    assert unlocked == [("locked", "unlocked")]
    assert jammed == [("locked", "jammed")]


async def test_valve_actions_full_featured(client: HAClient, fake_ha: FakeHA) -> None:
    """A full-featured valve dispatches every intent-specific service."""
    valve = client.valve("main_water")
    # All ValveEntityFeature bits: OPEN|CLOSE|SET_POSITION|STOP = 15.
    valve._apply_state({"state": "open", "attributes": {"supported_features": 15}})

    await valve.open()
    await valve.close()
    await valve.stop()
    await valve.set_position(40)
    await valve.toggle()

    svc = [c["service"] for c in fake_ha.ws_service_calls]
    assert svc == ["open_valve", "close_valve", "stop_valve", "set_valve_position", "toggle"]
    assert all(c["domain"] == "valve" for c in fake_ha.ws_service_calls)
    position_call = _find_call(fake_ha, "set_valve_position")
    assert position_call["service_data"]["position"] == 40


async def test_valve_state_properties(client: HAClient) -> None:
    """State helpers reflect the underlying HA state and attributes."""
    valve = client.valve("garden")

    valve._apply_state({"state": "open", "attributes": {"current_position": 75}})
    assert valve.is_open
    assert not valve.is_closed
    assert not valve.is_opening
    assert not valve.is_closing
    assert valve.current_position == 75

    valve._apply_state({"state": "closed", "attributes": {}})
    assert valve.is_closed
    assert not valve.is_open
    assert valve.current_position is None

    valve._apply_state({"state": "opening", "attributes": {"current_position": 50.0}})
    assert valve.is_opening
    assert valve.current_position == 50

    valve._apply_state({"state": "closing", "attributes": {"current_position": "bad"}})
    assert valve.is_closing
    assert valve.current_position is None


async def test_valve_degrades_when_features_missing(client: HAClient, fake_ha: FakeHA) -> None:
    """``set_position`` and ``stop`` no-op on binary valves; ``open``/``close`` still work."""
    valve = client.valve("shutoff")
    # OPEN|CLOSE only — no SET_POSITION, no STOP.
    valve._apply_state({"state": "open", "attributes": {"supported_features": 3}})

    assert valve.supports_set_position is False
    assert valve.supports_stop is False

    await valve.set_position(50)
    await valve.stop()
    assert fake_ha.ws_service_calls == []

    await valve.open()
    await valve.close()
    svc = [c["service"] for c in fake_ha.ws_service_calls]
    assert svc == ["open_valve", "close_valve"]

    # Missing attribute entirely behaves the same.
    valve._apply_state({"state": "open", "attributes": {}})
    assert valve.supports_set_position is False
    assert valve.supports_stop is False

    # Non-int ``supported_features`` is treated as unsupported.
    valve._apply_state({"state": "open", "attributes": {"supported_features": "15"}})
    assert valve.supports_set_position is False
    assert valve.supports_stop is False


async def test_valve_supports_set_position_and_stop_when_advertised(
    client: HAClient, fake_ha: FakeHA
) -> None:
    """Feature flags surface positional/stop support independently."""
    valve = client.valve("irrigation")
    # SET_POSITION only.
    valve._apply_state({"state": "open", "attributes": {"supported_features": 4}})
    assert valve.supports_set_position is True
    assert valve.supports_stop is False
    await valve.set_position(25)
    await valve.stop()
    svc = [c["service"] for c in fake_ha.ws_service_calls]
    assert svc == ["set_valve_position"]

    # STOP only.
    fake_ha.ws_service_calls.clear()
    valve._apply_state({"state": "open", "attributes": {"supported_features": 8}})
    assert valve.supports_set_position is False
    assert valve.supports_stop is True
    await valve.set_position(25)
    await valve.stop()
    svc = [c["service"] for c in fake_ha.ws_service_calls]
    assert svc == ["stop_valve"]


async def test_valve_listeners(client: HAClient, fake_ha: FakeHA) -> None:
    """``on_open`` / ``on_close`` / ``on_position_change`` fire as expected."""
    valve = client.valve("zone1")
    opened: list[tuple[Any, Any]] = []
    closed: list[tuple[Any, Any]] = []
    positions: list[Any] = []

    @valve.on_open
    def _on_open(old: Any, new: Any) -> None:
        opened.append((old, new))

    @valve.on_close
    def _on_close(old: Any, new: Any) -> None:
        closed.append((old, new))

    @valve.on_position_change
    def _on_position(old: Any, new: Any) -> None:
        positions.append((old, new))

    await fake_ha.push_state_changed(
        "valve.zone1",
        {"state": "closed", "attributes": {"current_position": 0}},
        {"state": "open", "attributes": {"current_position": 100}},
    )
    await fake_ha.push_state_changed(
        "valve.zone1",
        {"state": "open", "attributes": {"current_position": 100}},
        {"state": "closed", "attributes": {"current_position": 0}},
    )
    await asyncio.sleep(0.05)

    assert opened == [("closed", "open")]
    assert closed == [("open", "closed")]
    # Position changes fire for both transitions (order is not guaranteed
    # across distinct ``push_state_changed`` events).
    assert sorted(positions) == [(0, 100), (100, 0)]


async def test_humidifier_actions(client: HAClient, fake_ha: FakeHA) -> None:
    h = client.humidifier("bedroom")
    await h.on()
    await h.set_humidity(50)
    await h.off()
    await h.toggle()
    calls = fake_ha.ws_service_calls
    assert [c["service"] for c in calls] == ["turn_on", "set_humidity", "turn_off", "toggle"]
    assert calls[1]["service_data"]["humidity"] == 50

    h._apply_state(
        {
            "state": "on",
            "attributes": {
                "humidity": 45,
                "current_humidity": 38,
                "mode": "auto",
                "available_modes": ["auto", "sleep", "baby"],
                "device_class": "humidifier",
            },
        }
    )
    assert h.is_on
    assert h.target_humidity == 45
    assert h.current_humidity == 38
    assert h.mode == "auto"
    assert h.available_modes == ["auto", "sleep", "baby"]
    assert h.device_class == "humidifier"

    await h.set_mode("sleep")
    assert fake_ha.ws_service_calls[-1]["service"] == "set_mode"
    assert fake_ha.ws_service_calls[-1]["service_data"]["mode"] == "sleep"

    with pytest.raises(ValueError):
        await h.set_mode("nope")

    with pytest.raises(ValueError):
        await h.set_humidity(150)
    with pytest.raises(ValueError):
        await h.set_humidity(-1)


async def test_humidifier_degrades_when_unsupported(client: HAClient, fake_ha: FakeHA) -> None:
    h = client.humidifier("basement")
    # Device reports no modes and no current humidity reading.
    h._apply_state({"state": "off", "attributes": {}})
    assert not h.is_on
    assert h.target_humidity is None
    assert h.current_humidity is None
    assert h.mode is None
    assert h.available_modes == []
    assert h.device_class is None

    # set_mode is a no-op when the device exposes no modes.
    before = len(fake_ha.ws_service_calls)
    await h.set_mode("auto")
    assert len(fake_ha.ws_service_calls) == before


async def test_humidifier_listeners(client: HAClient, fake_ha: FakeHA) -> None:
    h = client.humidifier("nursery")

    turned_on: list[tuple[Any, Any]] = []
    turned_off: list[tuple[Any, Any]] = []
    humidity_events: list[tuple[Any, Any]] = []
    mode_events: list[tuple[Any, Any]] = []

    @h.on_turn_on
    def _on(old: Any, new: Any) -> None:
        turned_on.append((old, new))

    @h.on_turn_off
    def _off(old: Any, new: Any) -> None:
        turned_off.append((old, new))

    @h.on_humidity_change
    def _hum(old: Any, new: Any) -> None:
        humidity_events.append((old, new))

    @h.on_mode_change
    def _mode(old: Any, new: Any) -> None:
        mode_events.append((old, new))

    await fake_ha.push_state_changed(
        "humidifier.nursery",
        {"state": "on", "attributes": {"humidity": 55, "mode": "sleep"}},
        {"state": "off", "attributes": {"humidity": 40, "mode": "auto"}},
    )
    await fake_ha.push_state_changed(
        "humidifier.nursery",
        {"state": "off", "attributes": {"humidity": 55, "mode": "sleep"}},
        {"state": "on", "attributes": {"humidity": 55, "mode": "sleep"}},
    )

    await asyncio.sleep(0.05)
    assert turned_on == [("off", "on")]
    assert turned_off == [("on", "off")]
    assert humidity_events == [(40, 55)]
    assert mode_events == [("auto", "sleep")]


# ---------------------------------------------------------------------------
# Air quality
# ---------------------------------------------------------------------------


async def test_air_quality_full_metrics() -> None:
    """Every typed metric is read from its underlying attribute."""
    ha = HAClient.from_url("http://x", token="t", load_plugins=False)
    try:
        aq = ha.air_quality("bedroom")
        aq._apply_state(
            {
                "state": "42",
                "attributes": {
                    "particulate_matter_2_5": 12.3,
                    "particulate_matter_10": 20,
                    "carbon_dioxide": 800,
                    "carbon_monoxide": 1.5,
                    "volatile_organic_compounds": 0.4,
                    "nitrogen_dioxide": 5,
                    "ozone": 18.0,
                },
            }
        )
        # AQI falls back to the state when no explicit attribute is set.
        assert aq.air_quality_index == 42.0
        assert aq.particulate_matter_2_5 == 12.3
        assert aq.particulate_matter_10 == 20
        assert aq.carbon_dioxide == 800
        assert aq.carbon_monoxide == 1.5
        assert aq.volatile_organic_compounds == 0.4
        assert aq.nitrogen_dioxide == 5
        assert aq.ozone == 18.0
    finally:
        await ha.close()


async def test_air_quality_degrades_when_metrics_missing() -> None:
    """Unsupported metrics return ``None`` rather than raising."""
    ha = HAClient.from_url("http://x", token="t", load_plugins=False)
    try:
        aq = ha.air_quality("minimal")
        aq._apply_state({"state": "unknown", "attributes": {}})
        assert aq.air_quality_index is None
        assert aq.particulate_matter_2_5 is None
        assert aq.particulate_matter_10 is None
        assert aq.carbon_dioxide is None
        assert aq.carbon_monoxide is None
        assert aq.volatile_organic_compounds is None
        assert aq.nitrogen_dioxide is None
        assert aq.ozone is None
    finally:
        await ha.close()


async def test_air_quality_index_prefers_explicit_attribute() -> None:
    """An explicit ``air_quality_index`` attribute overrides the state."""
    ha = HAClient.from_url("http://x", token="t", load_plugins=False)
    try:
        aq = ha.air_quality("outdoor")
        aq._apply_state(
            {
                "state": "99",
                "attributes": {"air_quality_index": 55},
            }
        )
        assert aq.air_quality_index == 55
    finally:
        await ha.close()


async def test_air_quality_coercion_handles_strings_and_bad_values() -> None:
    """Numeric strings coerce to ``float``; junk values yield ``None``."""
    ha = HAClient.from_url("http://x", token="t", load_plugins=False)
    try:
        aq = ha.air_quality("noisy")
        aq._apply_state(
            {
                "state": "unavailable",
                "attributes": {
                    "particulate_matter_2_5": "12.5",
                    "carbon_dioxide": "not-a-number",
                    "carbon_monoxide": True,  # bools are not real readings
                    "ozone": "",
                    "nitrogen_dioxide": [1, 2, 3],  # unsupported type -> None
                },
            }
        )
        assert aq.air_quality_index is None
        assert aq.particulate_matter_2_5 == 12.5
        assert aq.carbon_dioxide is None
        assert aq.carbon_monoxide is None
        assert aq.ozone is None
        assert aq.nitrogen_dioxide is None
    finally:
        await ha.close()


async def test_air_quality_listeners(client: HAClient, fake_ha: FakeHA) -> None:
    """``on_aqi_change`` / ``on_pm25_change`` / ``on_co2_change`` fire as expected."""
    aq = client.air_quality("bedroom")
    aqi_events: list[tuple[Any, Any]] = []
    pm25_events: list[tuple[Any, Any]] = []
    co2_events: list[tuple[Any, Any]] = []

    @aq.on_aqi_change
    def _aqi(old: Any, new: Any) -> None:
        aqi_events.append((old, new))

    @aq.on_pm25_change
    def _pm25(old: Any, new: Any) -> None:
        pm25_events.append((old, new))

    @aq.on_co2_change
    def _co2(old: Any, new: Any) -> None:
        co2_events.append((old, new))

    await fake_ha.push_state_changed(
        "air_quality.bedroom",
        {
            "state": "55",
            "attributes": {"particulate_matter_2_5": 14.0, "carbon_dioxide": 950},
        },
        {
            "state": "42",
            "attributes": {"particulate_matter_2_5": 10.0, "carbon_dioxide": 800},
        },
    )
    await asyncio.sleep(0.05)

    assert aqi_events == [("42", "55")]
    assert pm25_events == [(10.0, 14.0)]
    assert co2_events == [(800, 950)]


# ---------------------------------------------------------------------------
# Vacuum
# ---------------------------------------------------------------------------


# All ``VacuumEntityFeature`` bits OR'd together (START|PAUSE|STOP|
# RETURN_HOME|FAN_SPEED|LOCATE|SEND_COMMAND|CLEAN_SPOT).
_VACUUM_FULL_FEATURES = 8192 | 4 | 8 | 16 | 32 | 512 | 256 | 1024


async def test_vacuum_actions_full_featured(client: HAClient, fake_ha: FakeHA) -> None:
    """A full-featured vacuum dispatches every intent-specific service."""
    robo = client.vacuum("roborock")
    robo._apply_state(
        {"state": "cleaning", "attributes": {"supported_features": _VACUUM_FULL_FEATURES}}
    )

    await robo.start()
    await robo.pause()
    await robo.stop()
    await robo.return_to_base()
    await robo.locate()
    await robo.clean_spot()
    await robo.set_fan_speed("turbo")
    await robo.send_command("set_zone", {"zone": [1, 2, 3, 4]})

    services = [c["service"] for c in fake_ha.ws_service_calls]
    assert services == [
        "start",
        "pause",
        "stop",
        "return_to_base",
        "locate",
        "clean_spot",
        "set_fan_speed",
        "send_command",
    ]
    assert all(c["domain"] == "vacuum" for c in fake_ha.ws_service_calls)
    assert all(
        c["service_data"]["entity_id"] == "vacuum.roborock" for c in fake_ha.ws_service_calls
    )

    fan = _find_call(fake_ha, "set_fan_speed")
    assert fan["service_data"]["fan_speed"] == "turbo"

    cmd = _find_call(fake_ha, "send_command")
    assert cmd["service_data"]["command"] == "set_zone"
    assert cmd["service_data"]["params"] == {"zone": [1, 2, 3, 4]}


async def test_vacuum_send_command_without_params(client: HAClient, fake_ha: FakeHA) -> None:
    """``send_command`` omits the ``params`` key when none are provided."""
    robo = client.vacuum("roborock")
    robo._apply_state(
        {"state": "cleaning", "attributes": {"supported_features": _VACUUM_FULL_FEATURES}}
    )

    await robo.send_command("find_dock")
    cmd = _find_call(fake_ha, "send_command")
    assert cmd["service_data"]["command"] == "find_dock"
    assert "params" not in cmd["service_data"]


async def test_vacuum_unsupported_features_are_noops(client: HAClient, fake_ha: FakeHA) -> None:
    """Actions degrade safely on vacuums that lack the relevant feature bits."""
    basic = client.vacuum("basic")
    # No supported_features attribute at all.
    basic._apply_state({"state": "docked", "attributes": {}})

    assert basic.supports_start is False
    assert basic.supports_pause is False
    assert basic.supports_stop is False
    assert basic.supports_return_home is False
    assert basic.supports_locate is False
    assert basic.supports_fan_speed is False
    assert basic.supports_send_command is False
    assert basic.supports_clean_spot is False

    await basic.start()
    await basic.pause()
    await basic.stop()
    await basic.return_to_base()
    await basic.locate()
    await basic.clean_spot()
    await basic.set_fan_speed("turbo")
    await basic.send_command("find_dock", {"x": 1})

    assert fake_ha.ws_service_calls == []

    # Non-int supported_features is treated as unsupported.
    basic._apply_state({"state": "docked", "attributes": {"supported_features": "32"}})
    assert basic.supports_fan_speed is False


async def test_vacuum_state_props() -> None:
    """Vacuum state convenience properties reflect the underlying string state."""
    ha = HAClient.from_url("http://x", token="t", load_plugins=False)
    try:
        robo = ha.vacuum("roborock")
        robo._apply_state(
            {
                "state": "cleaning",
                "attributes": {
                    "battery_level": 72,
                    "fan_speed": "balanced",
                    "fan_speed_list": ["quiet", "balanced", "turbo"],
                },
            }
        )
        assert robo.is_cleaning
        assert not robo.is_docked
        assert robo.battery_level == 72
        assert robo.fan_speed == "balanced"
        assert robo.fan_speed_list == ["quiet", "balanced", "turbo"]

        for state, prop in [
            ("docked", "is_docked"),
            ("idle", "is_idle"),
            ("paused", "is_paused"),
            ("returning", "is_returning"),
            ("error", "is_error"),
        ]:
            robo._apply_state({"state": state, "attributes": {}})
            assert getattr(robo, prop)

        # Missing / malformed attributes degrade to None / empty.
        robo._apply_state({"state": "docked", "attributes": {}})
        assert robo.battery_level is None
        assert robo.fan_speed is None
        assert robo.fan_speed_list == []

        # Non-string entries are filtered out of fan_speed_list.
        robo._apply_state({"state": "docked", "attributes": {"fan_speed_list": ["a", 1, "b"]}})
        assert robo.fan_speed_list == ["a", "b"]

        # Non-list fan_speed_list returns empty list.
        robo._apply_state({"state": "docked", "attributes": {"fan_speed_list": "not-a-list"}})
        assert robo.fan_speed_list == []
    finally:
        await ha.close()


async def test_vacuum_listeners(client: HAClient, fake_ha: FakeHA) -> None:
    """Vacuum listener decorators fire on the relevant transitions."""
    robo = client.vacuum("hall")
    started: list[tuple[Any, Any]] = []
    docked: list[tuple[Any, Any]] = []
    errored: list[tuple[Any, Any]] = []
    battery: list[tuple[Any, Any]] = []
    fan: list[tuple[Any, Any]] = []

    @robo.on_start
    def _on_start(old: Any, new: Any) -> None:
        started.append((old, new))

    @robo.on_dock
    def _on_dock(old: Any, new: Any) -> None:
        docked.append((old, new))

    @robo.on_error
    def _on_error(old: Any, new: Any) -> None:
        errored.append((old, new))

    @robo.on_battery_change
    def _on_battery(old: Any, new: Any) -> None:
        battery.append((old, new))

    @robo.on_fan_speed_change
    def _on_fan(old: Any, new: Any) -> None:
        fan.append((old, new))

    await fake_ha.push_state_changed(
        "vacuum.hall",
        {"state": "cleaning", "attributes": {"battery_level": 75, "fan_speed": "turbo"}},
        {"state": "docked", "attributes": {"battery_level": 80, "fan_speed": "balanced"}},
    )
    await fake_ha.push_state_changed(
        "vacuum.hall",
        {"state": "docked", "attributes": {"battery_level": 90, "fan_speed": "balanced"}},
        {"state": "cleaning", "attributes": {"battery_level": 75, "fan_speed": "turbo"}},
    )
    await fake_ha.push_state_changed(
        "vacuum.hall",
        {"state": "error", "attributes": {}},
        {"state": "docked", "attributes": {}},
    )
    await asyncio.sleep(0.05)

    assert started == [("docked", "cleaning")]
    assert docked == [("cleaning", "docked")]
    assert errored == [("docked", "error")]
    assert battery == [(80, 75), (75, 90)]
    assert fan == [("balanced", "turbo"), ("turbo", "balanced")]
