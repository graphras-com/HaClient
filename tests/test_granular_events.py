"""Tests for granular (attribute/state-transition) event listeners."""

from __future__ import annotations

import asyncio
from typing import Any

from haclient import HAClient
from haclient.domains.media_player import NowPlaying

from .fake_ha import FakeHA


async def test_media_player_on_volume_change(client: HAClient, fake_ha: FakeHA) -> None:
    player = client.media_player("living_room")
    captured: list[tuple[Any, Any]] = []

    @player.on_volume_change
    def handler(old: Any, new: Any) -> None:
        captured.append((old, new))

    await fake_ha.push_state_changed(
        "media_player.living_room",
        {"state": "playing", "attributes": {"volume_level": 0.5}},
        {"state": "playing", "attributes": {"volume_level": 0.3}},
    )
    await asyncio.sleep(0.05)
    assert captured == [(0.3, 0.5)]


async def test_media_player_on_volume_change_not_fired_when_same(
    client: HAClient, fake_ha: FakeHA
) -> None:
    player = client.media_player("living_room")
    captured: list[tuple[Any, Any]] = []

    @player.on_volume_change
    def handler(old: Any, new: Any) -> None:
        captured.append((old, new))

    await fake_ha.push_state_changed(
        "media_player.living_room",
        {"state": "playing", "attributes": {"volume_level": 0.5}},
        {"state": "paused", "attributes": {"volume_level": 0.5}},
    )
    await asyncio.sleep(0.05)
    assert captured == []


async def test_media_player_on_mute_change(client: HAClient, fake_ha: FakeHA) -> None:
    player = client.media_player("living_room")
    captured: list[tuple[Any, Any]] = []

    @player.on_mute_change
    def handler(old: Any, new: Any) -> None:
        captured.append((old, new))

    await fake_ha.push_state_changed(
        "media_player.living_room",
        {"state": "playing", "attributes": {"is_volume_muted": True}},
        {"state": "playing", "attributes": {"is_volume_muted": False}},
    )
    await asyncio.sleep(0.05)
    assert captured == [(False, True)]


async def test_media_player_on_media_change_source(client: HAClient, fake_ha: FakeHA) -> None:
    player = client.media_player("living_room")
    captured: list[tuple[NowPlaying, NowPlaying]] = []

    @player.on_media_change
    def handler(old: NowPlaying, new: NowPlaying) -> None:
        captured.append((old, new))

    await fake_ha.push_state_changed(
        "media_player.living_room",
        {"state": "playing", "attributes": {"source": "Spotify", "media_title": "Song"}},
        {"state": "playing", "attributes": {"source": "Radio", "media_title": "Song"}},
    )
    await asyncio.sleep(0.05)
    assert len(captured) == 1
    assert captured[0][0].source == "Radio"
    assert captured[0][1].source == "Spotify"


async def test_media_player_on_media_change_title(client: HAClient, fake_ha: FakeHA) -> None:
    player = client.media_player("living_room")
    captured: list[tuple[NowPlaying, NowPlaying]] = []

    @player.on_media_change
    def handler(old: NowPlaying, new: NowPlaying) -> None:
        captured.append((old, new))

    await fake_ha.push_state_changed(
        "media_player.living_room",
        {
            "state": "playing",
            "attributes": {"media_title": "Lazarus", "media_artist": "David Bowie"},
        },
        {
            "state": "playing",
            "attributes": {"media_title": "Heroes", "media_artist": "David Bowie"},
        },
    )
    await asyncio.sleep(0.05)
    assert len(captured) == 1
    assert captured[0][0].title == "Heroes"
    assert captured[0][1].title == "Lazarus"


async def test_media_player_on_media_change_not_fired_on_position(
    client: HAClient, fake_ha: FakeHA
) -> None:
    """on_media_change must NOT fire when only position/progress changes."""
    player = client.media_player("living_room")
    captured: list[Any] = []

    @player.on_media_change
    def handler(old: Any, new: Any) -> None:
        captured.append((old, new))

    await fake_ha.push_state_changed(
        "media_player.living_room",
        {
            "state": "playing",
            "attributes": {
                "media_title": "Lazarus",
                "media_position": 120,
                "media_position_updated_at": "2026-04-20T23:03:00+00:00",
            },
        },
        {
            "state": "playing",
            "attributes": {
                "media_title": "Lazarus",
                "media_position": 75,
                "media_position_updated_at": "2026-04-20T23:02:14+00:00",
            },
        },
    )
    await asyncio.sleep(0.05)
    assert captured == []


async def test_media_player_now_playing_property(client: HAClient, fake_ha: FakeHA) -> None:
    player = client.media_player("living_room")

    await fake_ha.push_state_changed(
        "media_player.living_room",
        {
            "state": "playing",
            "attributes": {
                "source": "TV",
                "media_title": "Lazarus",
                "media_artist": "David Bowie",
                "media_album_name": "Blackstar",
                "media_channel": "Kringvarp Føroya",
                "media_content_type": "music",
                "media_content_id": "x-sonos-http:song",
                "media_duration": 597,
                "entity_picture": "/api/proxy",
            },
        },
        None,
    )
    await asyncio.sleep(0.05)
    np = player.now_playing
    assert np.source == "TV"
    assert np.title == "Lazarus"
    assert np.artist == "David Bowie"
    assert np.album == "Blackstar"
    assert np.channel == "Kringvarp Føroya"
    assert np.content_type == "music"
    assert np.duration == 597


async def test_media_player_remove_media_change_listener(client: HAClient, fake_ha: FakeHA) -> None:
    player = client.media_player("living_room")
    calls = 0

    def handler(old: Any, new: Any) -> None:
        nonlocal calls
        calls += 1

    player.on_media_change(handler)
    player.remove_granular_listener(handler)

    await fake_ha.push_state_changed(
        "media_player.living_room",
        {"state": "playing", "attributes": {"media_title": "New"}},
        {"state": "playing", "attributes": {"media_title": "Old"}},
    )
    await asyncio.sleep(0.05)
    assert calls == 0


async def test_media_player_on_play(client: HAClient, fake_ha: FakeHA) -> None:
    player = client.media_player("living_room")
    captured: list[tuple[Any, Any]] = []

    @player.on_play
    def handler(old: Any, new: Any) -> None:
        captured.append((old, new))

    await fake_ha.push_state_changed(
        "media_player.living_room",
        {"state": "playing", "attributes": {}},
        {"state": "paused", "attributes": {}},
    )
    await asyncio.sleep(0.05)
    assert captured == [("paused", "playing")]


async def test_media_player_on_pause(client: HAClient, fake_ha: FakeHA) -> None:
    player = client.media_player("living_room")
    captured: list[tuple[Any, Any]] = []

    @player.on_pause
    def handler(old: Any, new: Any) -> None:
        captured.append((old, new))

    await fake_ha.push_state_changed(
        "media_player.living_room",
        {"state": "paused", "attributes": {}},
        {"state": "playing", "attributes": {}},
    )
    await asyncio.sleep(0.05)
    assert captured == [("playing", "paused")]


async def test_media_player_on_stop(client: HAClient, fake_ha: FakeHA) -> None:
    player = client.media_player("living_room")
    captured: list[tuple[Any, Any]] = []

    @player.on_stop
    def handler(old: Any, new: Any) -> None:
        captured.append((old, new))

    await fake_ha.push_state_changed(
        "media_player.living_room",
        {"state": "idle", "attributes": {}},
        {"state": "playing", "attributes": {}},
    )
    await asyncio.sleep(0.05)
    assert captured == [("playing", "idle")]


async def test_light_on_turn_on(client: HAClient, fake_ha: FakeHA) -> None:
    light = client.light("kitchen")
    captured: list[tuple[Any, Any]] = []

    @light.on_turn_on
    def handler(old: Any, new: Any) -> None:
        captured.append((old, new))

    await fake_ha.push_state_changed(
        "light.kitchen",
        {"state": "on", "attributes": {}},
        {"state": "off", "attributes": {}},
    )
    await asyncio.sleep(0.05)
    assert captured == [("off", "on")]


async def test_light_on_turn_off(client: HAClient, fake_ha: FakeHA) -> None:
    light = client.light("kitchen")
    captured: list[tuple[Any, Any]] = []

    @light.on_turn_off
    def handler(old: Any, new: Any) -> None:
        captured.append((old, new))

    await fake_ha.push_state_changed(
        "light.kitchen",
        {"state": "off", "attributes": {}},
        {"state": "on", "attributes": {}},
    )
    await asyncio.sleep(0.05)
    assert captured == [("on", "off")]


async def test_light_on_brightness_change(client: HAClient, fake_ha: FakeHA) -> None:
    light = client.light("kitchen")
    captured: list[tuple[Any, Any]] = []

    @light.on_brightness_change
    def handler(old: Any, new: Any) -> None:
        captured.append((old, new))

    await fake_ha.push_state_changed(
        "light.kitchen",
        {"state": "on", "attributes": {"brightness": 200}},
        {"state": "on", "attributes": {"brightness": 100}},
    )
    await asyncio.sleep(0.05)
    assert captured == [(100, 200)]


async def test_light_on_color_change(client: HAClient, fake_ha: FakeHA) -> None:
    light = client.light("kitchen")
    captured: list[tuple[Any, Any]] = []

    @light.on_color_change
    def handler(old: Any, new: Any) -> None:
        captured.append((old, new))

    await fake_ha.push_state_changed(
        "light.kitchen",
        {"state": "on", "attributes": {"rgb_color": [255, 0, 0]}},
        {"state": "on", "attributes": {"rgb_color": [0, 255, 0]}},
    )
    await asyncio.sleep(0.05)
    assert captured == [([0, 255, 0], [255, 0, 0])]


async def test_light_on_kelvin_change(client: HAClient, fake_ha: FakeHA) -> None:
    light = client.light("kitchen")
    captured: list[tuple[Any, Any]] = []

    @light.on_kelvin_change
    def handler(old: Any, new: Any) -> None:
        captured.append((old, new))

    await fake_ha.push_state_changed(
        "light.kitchen",
        {"state": "on", "attributes": {"color_temp_kelvin": 5000}},
        {"state": "on", "attributes": {"color_temp_kelvin": 3000}},
    )
    await asyncio.sleep(0.05)
    assert captured == [(3000, 5000)]


async def test_switch_on_turn_on(client: HAClient, fake_ha: FakeHA) -> None:
    switch = client.switch("pump")
    captured: list[tuple[Any, Any]] = []

    @switch.on_turn_on
    def handler(old: Any, new: Any) -> None:
        captured.append((old, new))

    await fake_ha.push_state_changed(
        "switch.pump",
        {"state": "on", "attributes": {}},
        {"state": "off", "attributes": {}},
    )
    await asyncio.sleep(0.05)
    assert captured == [("off", "on")]


async def test_switch_on_turn_off(client: HAClient, fake_ha: FakeHA) -> None:
    switch = client.switch("pump")
    captured: list[tuple[Any, Any]] = []

    @switch.on_turn_off
    def handler(old: Any, new: Any) -> None:
        captured.append((old, new))

    await fake_ha.push_state_changed(
        "switch.pump",
        {"state": "off", "attributes": {}},
        {"state": "on", "attributes": {}},
    )
    await asyncio.sleep(0.05)
    assert captured == [("on", "off")]


async def test_binary_sensor_on_activate(client: HAClient, fake_ha: FakeHA) -> None:
    sensor = client.binary_sensor("motion")
    captured: list[tuple[Any, Any]] = []

    @sensor.on_activate
    def handler(old: Any, new: Any) -> None:
        captured.append((old, new))

    await fake_ha.push_state_changed(
        "binary_sensor.motion",
        {"state": "on", "attributes": {}},
        {"state": "off", "attributes": {}},
    )
    await asyncio.sleep(0.05)
    assert captured == [("off", "on")]


async def test_binary_sensor_on_deactivate(client: HAClient, fake_ha: FakeHA) -> None:
    sensor = client.binary_sensor("motion")
    captured: list[tuple[Any, Any]] = []

    @sensor.on_deactivate
    def handler(old: Any, new: Any) -> None:
        captured.append((old, new))

    await fake_ha.push_state_changed(
        "binary_sensor.motion",
        {"state": "off", "attributes": {}},
        {"state": "on", "attributes": {}},
    )
    await asyncio.sleep(0.05)
    assert captured == [("on", "off")]


async def test_cover_on_open(client: HAClient, fake_ha: FakeHA) -> None:
    cover = client.cover("garage")
    captured: list[tuple[Any, Any]] = []

    @cover.on_open
    def handler(old: Any, new: Any) -> None:
        captured.append((old, new))

    await fake_ha.push_state_changed(
        "cover.garage",
        {"state": "open", "attributes": {}},
        {"state": "closed", "attributes": {}},
    )
    await asyncio.sleep(0.05)
    assert captured == [("closed", "open")]


async def test_cover_on_close(client: HAClient, fake_ha: FakeHA) -> None:
    cover = client.cover("garage")
    captured: list[tuple[Any, Any]] = []

    @cover.on_close
    def handler(old: Any, new: Any) -> None:
        captured.append((old, new))

    await fake_ha.push_state_changed(
        "cover.garage",
        {"state": "closed", "attributes": {}},
        {"state": "open", "attributes": {}},
    )
    await asyncio.sleep(0.05)
    assert captured == [("open", "closed")]


async def test_cover_on_position_change(client: HAClient, fake_ha: FakeHA) -> None:
    cover = client.cover("garage")
    captured: list[tuple[Any, Any]] = []

    @cover.on_position_change
    def handler(old: Any, new: Any) -> None:
        captured.append((old, new))

    await fake_ha.push_state_changed(
        "cover.garage",
        {"state": "open", "attributes": {"current_position": 75}},
        {"state": "open", "attributes": {"current_position": 50}},
    )
    await asyncio.sleep(0.05)
    assert captured == [(50, 75)]


async def test_climate_on_hvac_mode_change(client: HAClient, fake_ha: FakeHA) -> None:
    climate = client.climate("thermostat")
    captured: list[tuple[Any, Any]] = []

    @climate.on_hvac_mode_change
    def handler(old: Any, new: Any) -> None:
        captured.append((old, new))

    await fake_ha.push_state_changed(
        "climate.thermostat",
        {"state": "cool", "attributes": {}},
        {"state": "heat", "attributes": {}},
    )
    await asyncio.sleep(0.05)
    assert captured == [("heat", "cool")]


async def test_climate_on_hvac_mode_not_fired_when_same(client: HAClient, fake_ha: FakeHA) -> None:
    climate = client.climate("thermostat")
    captured: list[tuple[Any, Any]] = []

    @climate.on_hvac_mode_change
    def handler(old: Any, new: Any) -> None:
        captured.append((old, new))

    await fake_ha.push_state_changed(
        "climate.thermostat",
        {"state": "heat", "attributes": {"current_temperature": 22}},
        {"state": "heat", "attributes": {"current_temperature": 21}},
    )
    await asyncio.sleep(0.05)
    assert captured == []


async def test_climate_on_temperature_change(client: HAClient, fake_ha: FakeHA) -> None:
    climate = client.climate("thermostat")
    captured: list[tuple[Any, Any]] = []

    @climate.on_temperature_change
    def handler(old: Any, new: Any) -> None:
        captured.append((old, new))

    await fake_ha.push_state_changed(
        "climate.thermostat",
        {"state": "heat", "attributes": {"current_temperature": 22.5}},
        {"state": "heat", "attributes": {"current_temperature": 21.0}},
    )
    await asyncio.sleep(0.05)
    assert captured == [(21.0, 22.5)]


async def test_climate_on_target_temperature_change(client: HAClient, fake_ha: FakeHA) -> None:
    climate = client.climate("thermostat")
    captured: list[tuple[Any, Any]] = []

    @climate.on_target_temperature_change
    def handler(old: Any, new: Any) -> None:
        captured.append((old, new))

    await fake_ha.push_state_changed(
        "climate.thermostat",
        {"state": "heat", "attributes": {"temperature": 24.0}},
        {"state": "heat", "attributes": {"temperature": 22.0}},
    )
    await asyncio.sleep(0.05)
    assert captured == [(22.0, 24.0)]


async def test_sensor_on_value_change(client: HAClient, fake_ha: FakeHA) -> None:
    sensor = client.sensor("temperature")
    captured: list[tuple[Any, Any]] = []

    @sensor.on_value_change
    def handler(old: Any, new: Any) -> None:
        captured.append((old, new))

    await fake_ha.push_state_changed(
        "sensor.temperature",
        {"state": "23.5", "attributes": {}},
        {"state": "22.0", "attributes": {}},
    )
    await asyncio.sleep(0.05)
    assert captured == [("22.0", "23.5")]


async def test_sensor_on_value_change_not_fired_when_same(
    client: HAClient, fake_ha: FakeHA
) -> None:
    sensor = client.sensor("temperature")
    captured: list[tuple[Any, Any]] = []

    @sensor.on_value_change
    def handler(old: Any, new: Any) -> None:
        captured.append((old, new))

    await fake_ha.push_state_changed(
        "sensor.temperature",
        {"state": "22.0", "attributes": {"unit_of_measurement": "C"}},
        {"state": "22.0", "attributes": {}},
    )
    await asyncio.sleep(0.05)
    assert captured == []


async def test_async_granular_handler(client: HAClient, fake_ha: FakeHA) -> None:
    """Async handlers are properly scheduled."""
    player = client.media_player("living_room")
    event = asyncio.Event()
    captured: list[tuple[Any, Any]] = []

    @player.on_volume_change
    async def handler(old: Any, new: Any) -> None:
        captured.append((old, new))
        event.set()

    await fake_ha.push_state_changed(
        "media_player.living_room",
        {"state": "playing", "attributes": {"volume_level": 0.8}},
        {"state": "playing", "attributes": {"volume_level": 0.4}},
    )
    await asyncio.wait_for(event.wait(), timeout=2.0)
    assert captured == [(0.4, 0.8)]


async def test_multiple_granular_listeners(client: HAClient, fake_ha: FakeHA) -> None:
    """Multiple listeners on the same event all fire."""
    light = client.light("kitchen")
    counts = {"a": 0, "b": 0}

    @light.on_turn_on
    def a(old: Any, new: Any) -> None:
        counts["a"] += 1

    @light.on_turn_on
    def b(old: Any, new: Any) -> None:
        counts["b"] += 1

    await fake_ha.push_state_changed(
        "light.kitchen",
        {"state": "on", "attributes": {}},
        {"state": "off", "attributes": {}},
    )
    await asyncio.sleep(0.05)
    assert counts == {"a": 1, "b": 1}


async def test_remove_granular_listener(client: HAClient, fake_ha: FakeHA) -> None:
    """Removed listeners no longer fire."""
    light = client.light("kitchen")
    calls = 0

    def handler(old: Any, new: Any) -> None:
        nonlocal calls
        calls += 1

    light.on_brightness_change(handler)
    light.remove_granular_listener(handler)

    await fake_ha.push_state_changed(
        "light.kitchen",
        {"state": "on", "attributes": {"brightness": 200}},
        {"state": "on", "attributes": {"brightness": 100}},
    )
    await asyncio.sleep(0.05)
    assert calls == 0


async def test_remove_state_transition_listener(client: HAClient, fake_ha: FakeHA) -> None:
    """Removed state transition listeners no longer fire."""
    switch = client.switch("pump")
    calls = 0

    def handler(old: Any, new: Any) -> None:
        nonlocal calls
        calls += 1

    switch.on_turn_on(handler)
    switch.remove_granular_listener(handler)

    await fake_ha.push_state_changed(
        "switch.pump",
        {"state": "on", "attributes": {}},
        {"state": "off", "attributes": {}},
    )
    await asyncio.sleep(0.05)
    assert calls == 0


async def test_remove_state_value_listener(client: HAClient, fake_ha: FakeHA) -> None:
    """Removed state value listeners no longer fire."""
    sensor = client.sensor("temperature")
    calls = 0

    def handler(old: Any, new: Any) -> None:
        nonlocal calls
        calls += 1

    sensor.on_value_change(handler)
    sensor.remove_granular_listener(handler)

    await fake_ha.push_state_changed(
        "sensor.temperature",
        {"state": "25.0", "attributes": {}},
        {"state": "22.0", "attributes": {}},
    )
    await asyncio.sleep(0.05)
    assert calls == 0


async def test_granular_handler_exception_logged(client: HAClient, fake_ha: FakeHA) -> None:
    """A handler that raises does not break other handlers."""
    player = client.media_player("living_room")
    captured: list[Any] = []

    @player.on_volume_change
    def bad_handler(old: Any, new: Any) -> None:
        raise RuntimeError("boom")

    @player.on_volume_change
    def good_handler(old: Any, new: Any) -> None:
        captured.append(new)

    await fake_ha.push_state_changed(
        "media_player.living_room",
        {"state": "playing", "attributes": {"volume_level": 0.9}},
        {"state": "playing", "attributes": {"volume_level": 0.5}},
    )
    await asyncio.sleep(0.05)
    assert captured == [0.9]


async def test_state_transition_not_fired_on_same_state(client: HAClient, fake_ha: FakeHA) -> None:
    """State transition listener does not fire if state doesn't change."""
    light = client.light("kitchen")
    calls = 0

    @light.on_turn_on
    def handler(old: Any, new: Any) -> None:
        nonlocal calls
        calls += 1

    await fake_ha.push_state_changed(
        "light.kitchen",
        {"state": "on", "attributes": {"brightness": 200}},
        {"state": "on", "attributes": {"brightness": 100}},
    )
    await asyncio.sleep(0.05)
    assert calls == 0


async def test_null_old_state_handling(client: HAClient, fake_ha: FakeHA) -> None:
    """Events with None old_state still dispatch correctly."""
    light = client.light("kitchen")
    captured: list[tuple[Any, Any]] = []

    @light.on_turn_on
    def handler(old: Any, new: Any) -> None:
        captured.append((old, new))

    await fake_ha.push_state_changed(
        "light.kitchen",
        {"state": "on", "attributes": {}},
        None,
    )
    await asyncio.sleep(0.05)
    assert captured == [(None, "on")]


async def test_timer_on_start(client: HAClient, fake_ha: FakeHA) -> None:
    t = client.timer("my_timer")
    captured: list[tuple[Any, Any]] = []

    @t.on_start
    def handler(old: Any, new: Any) -> None:
        captured.append((old, new))

    await fake_ha.push_state_changed(
        "timer.my_timer",
        {"state": "active", "attributes": {}},
        {"state": "idle", "attributes": {}},
    )
    await asyncio.sleep(0.05)
    assert captured == [("idle", "active")]


async def test_timer_on_pause(client: HAClient, fake_ha: FakeHA) -> None:
    t = client.timer("my_timer")
    captured: list[tuple[Any, Any]] = []

    @t.on_pause
    def handler(old: Any, new: Any) -> None:
        captured.append((old, new))

    await fake_ha.push_state_changed(
        "timer.my_timer",
        {"state": "paused", "attributes": {}},
        {"state": "active", "attributes": {}},
    )
    await asyncio.sleep(0.05)
    assert captured == [("active", "paused")]


async def test_timer_on_idle(client: HAClient, fake_ha: FakeHA) -> None:
    t = client.timer("my_timer")
    captured: list[tuple[Any, Any]] = []

    @t.on_idle
    def handler(old: Any, new: Any) -> None:
        captured.append((old, new))

    await fake_ha.push_state_changed(
        "timer.my_timer",
        {"state": "idle", "attributes": {}},
        {"state": "active", "attributes": {}},
    )
    await asyncio.sleep(0.05)
    assert captured == [("active", "idle")]


async def test_timer_on_finished(client: HAClient, fake_ha: FakeHA) -> None:
    t = client.timer("my_timer")
    captured: list[tuple[Any, Any]] = []

    @t.on_finished
    def handler(entity_id: Any, data: Any) -> None:
        captured.append((entity_id, data))

    await fake_ha.push_event(
        "timer.finished",
        {"data": {"entity_id": "timer.my_timer"}},
    )
    await asyncio.sleep(0.05)
    assert len(captured) == 1
    assert captured[0][0] == "timer.my_timer"


async def test_timer_on_cancelled(client: HAClient, fake_ha: FakeHA) -> None:
    t = client.timer("my_timer")
    captured: list[tuple[Any, Any]] = []

    @t.on_cancelled
    def handler(entity_id: Any, data: Any) -> None:
        captured.append((entity_id, data))

    await fake_ha.push_event(
        "timer.cancelled",
        {"data": {"entity_id": "timer.my_timer"}},
    )
    await asyncio.sleep(0.05)
    assert len(captured) == 1
    assert captured[0][0] == "timer.my_timer"


async def test_timer_on_finished_ignores_other_entities(client: HAClient, fake_ha: FakeHA) -> None:
    t = client.timer("my_timer")
    captured: list[tuple[Any, Any]] = []

    @t.on_finished
    def handler(entity_id: Any, data: Any) -> None:
        captured.append((entity_id, data))

    # Fire event for a different timer entity
    await fake_ha.push_event(
        "timer.finished",
        {"data": {"entity_id": "timer.other_timer"}},
    )
    await asyncio.sleep(0.05)
    assert captured == []


async def test_timer_on_finished_does_not_fire_on_cancel(client: HAClient, fake_ha: FakeHA) -> None:
    t = client.timer("my_timer")
    finished: list[tuple[Any, Any]] = []
    cancelled: list[tuple[Any, Any]] = []

    @t.on_finished
    def on_fin(entity_id: Any, data: Any) -> None:
        finished.append((entity_id, data))

    @t.on_cancelled
    def on_can(entity_id: Any, data: Any) -> None:
        cancelled.append((entity_id, data))

    await fake_ha.push_event(
        "timer.cancelled",
        {"data": {"entity_id": "timer.my_timer"}},
    )
    await asyncio.sleep(0.05)
    assert finished == []
    assert len(cancelled) == 1
