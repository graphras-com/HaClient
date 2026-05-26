"""Tests for the `event` domain (stateless triggers)."""

from __future__ import annotations

import asyncio

from haclient import HAClient
from haclient.domains.event import Event

from .fake_ha import FakeHA


async def test_event_state_properties() -> None:
    """`event_type`, `event_types`, and `device_class` parse from attributes."""
    ha = HAClient.from_url("http://x", token="t", load_plugins=False)
    try:
        ev = ha.event("living_room_remote")
        assert isinstance(ev, Event)

        # Unseen entity: every property is None.
        assert ev.event_type is None
        assert ev.event_types is None
        assert ev.device_class is None

        ev._apply_state(
            {
                "state": "2024-01-01T00:00:00+00:00",
                "attributes": {
                    "event_type": "single_press",
                    "event_types": ["single_press", "double_press", "long_press"],
                    "device_class": "button",
                },
            }
        )
        assert ev.event_type == "single_press"
        assert ev.event_types == ["single_press", "double_press", "long_press"]
        assert ev.device_class == "button"

        # Non-list ``event_types`` degrades to None.
        ev._apply_state({"state": "2024-01-01T00:00:01+00:00", "attributes": {"event_types": 5}})
        assert ev.event_types is None
    finally:
        await ha.close()


async def test_event_on_event_bare_decorator(client: HAClient, fake_ha: FakeHA) -> None:
    """`@on_event` (no parens) fires for every event_type."""
    button = client.event("remote")
    captured: list[str] = []

    @button.on_event
    def handler(event_type: str) -> None:
        captured.append(event_type)

    await fake_ha.push_state_changed(
        "event.remote",
        {"state": "2024-01-01T00:00:00+00:00", "attributes": {"event_type": "single_press"}},
        None,
    )
    await fake_ha.push_state_changed(
        "event.remote",
        {"state": "2024-01-01T00:00:01+00:00", "attributes": {"event_type": "double_press"}},
        {"state": "2024-01-01T00:00:00+00:00", "attributes": {"event_type": "single_press"}},
    )
    await asyncio.sleep(0.05)
    assert captured == ["single_press", "double_press"]


async def test_event_on_event_filtered(client: HAClient, fake_ha: FakeHA) -> None:
    """`@on_event(event_type=...)` only fires for the matching type."""
    button = client.event("remote")
    doubles: list[str] = []
    singles: list[str] = []

    @button.on_event(event_type="double_press")
    def on_double(event_type: str) -> None:
        doubles.append(event_type)

    @button.on_event(event_type="single_press")
    async def on_single(event_type: str) -> None:
        singles.append(event_type)

    for i, et in enumerate(["single_press", "double_press", "single_press", "long_press"]):
        await fake_ha.push_state_changed(
            "event.remote",
            {"state": f"2024-01-01T00:00:0{i + 1}+00:00", "attributes": {"event_type": et}},
            {"state": f"2024-01-01T00:00:0{i}+00:00", "attributes": {"event_type": "x"}},
        )
    await asyncio.sleep(0.05)
    assert doubles == ["double_press"]
    assert singles == ["single_press", "single_press"]


async def test_event_no_dispatch_without_state_change(client: HAClient, fake_ha: FakeHA) -> None:
    """No event fires when the state timestamp is unchanged."""
    button = client.event("remote")
    captured: list[str] = []

    @button.on_event
    def handler(event_type: str) -> None:
        captured.append(event_type)

    same = {"state": "2024-01-01T00:00:00+00:00", "attributes": {"event_type": "single_press"}}
    await fake_ha.push_state_changed("event.remote", same, same)
    await asyncio.sleep(0.05)
    assert captured == []


async def test_event_no_dispatch_for_unknown_state(client: HAClient, fake_ha: FakeHA) -> None:
    """``unknown``/``unavailable`` and missing event_type do not dispatch."""
    button = client.event("remote")
    captured: list[str] = []

    @button.on_event
    def handler(event_type: str) -> None:
        captured.append(event_type)

    # unavailable transition
    await fake_ha.push_state_changed(
        "event.remote",
        {"state": "unavailable", "attributes": {}},
        {"state": "2024-01-01T00:00:00+00:00", "attributes": {"event_type": "single_press"}},
    )
    # state changed but no event_type attribute
    await fake_ha.push_state_changed(
        "event.remote",
        {"state": "2024-01-01T00:00:05+00:00", "attributes": {}},
        {"state": "unavailable", "attributes": {}},
    )
    await asyncio.sleep(0.05)
    assert captured == []


async def test_event_remove_listener() -> None:
    """Listeners can be removed via `remove_event_listener`."""
    ha = HAClient.from_url("http://x", token="t", load_plugins=False)
    try:
        ev = ha.event("remote")
        captured: list[str] = []

        def bare(event_type: str) -> None:
            captured.append(f"bare:{event_type}")

        def typed(event_type: str) -> None:
            captured.append(f"typed:{event_type}")

        ev.on_event(bare)
        ev.on_event(event_type="double_press")(typed)

        ev._handle_state_changed(
            None,
            {"state": "2024-01-01T00:00:00+00:00", "attributes": {"event_type": "double_press"}},
        )
        assert sorted(captured) == ["bare:double_press", "typed:double_press"]

        captured.clear()
        ev.remove_event_listener(typed)
        ev.remove_event_listener(lambda _et: None)  # unknown: silently ignored

        ev._handle_state_changed(
            {"state": "2024-01-01T00:00:00+00:00", "attributes": {"event_type": "double_press"}},
            {"state": "2024-01-01T00:00:01+00:00", "attributes": {"event_type": "double_press"}},
        )
        assert captured == ["bare:double_press"]
    finally:
        await ha.close()


async def test_event_on_event_rejects_func_and_event_type() -> None:
    """Passing both *func* and *event_type* is a programmer error."""
    ha = HAClient.from_url("http://x", token="t", load_plugins=False)
    try:
        ev = ha.event("remote")
        try:
            ev.on_event(lambda _et: None, event_type="x")  # type: ignore[call-overload]
        except TypeError:
            pass
        else:  # pragma: no cover - explicit failure
            raise AssertionError("Expected TypeError")
    finally:
        await ha.close()
