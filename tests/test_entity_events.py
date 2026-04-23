"""Tests for state updates and the @on_state_change decorator."""

from __future__ import annotations

import asyncio
from typing import Any

from haclient import HAClient

from .fake_ha import FakeHA


async def test_state_change_decorator_sync(client: HAClient, fake_ha: FakeHA) -> None:
    light = client.light("kitchen")
    captured: list[tuple[Any, Any]] = []

    @light.on_state_change
    def handler(old: Any, new: Any) -> None:
        captured.append((old, new))

    await fake_ha.push_state_changed("light.kitchen", {"state": "on", "attributes": {}}, None)
    await asyncio.sleep(0.05)
    assert len(captured) == 1
    assert captured[0][1]["state"] == "on"


async def test_state_change_decorator_async(client: HAClient, fake_ha: FakeHA) -> None:
    light = client.light("kitchen")
    seen = asyncio.Event()
    payload: dict[str, Any] = {}

    @light.on_state_change
    async def handler(old: Any, new: Any) -> None:
        payload["new"] = new
        seen.set()

    await fake_ha.push_state_changed(
        "light.kitchen", {"state": "on", "attributes": {"brightness": 30}}, None
    )
    await asyncio.wait_for(seen.wait(), timeout=2.0)
    assert payload["new"]["attributes"]["brightness"] == 30


async def test_multiple_listeners(client: HAClient, fake_ha: FakeHA) -> None:
    light = client.light("kitchen")
    counts = {"a": 0, "b": 0}

    @light.on_state_change
    def a(old: Any, new: Any) -> None:
        counts["a"] += 1

    @light.on_state_change
    def b(old: Any, new: Any) -> None:
        counts["b"] += 1

    await fake_ha.push_state_changed("light.kitchen", {"state": "on", "attributes": {}})
    await asyncio.sleep(0.05)
    assert counts == {"a": 1, "b": 1}


async def test_remove_listener(client: HAClient, fake_ha: FakeHA) -> None:
    light = client.light("kitchen")
    calls = 0

    def handler(old: Any, new: Any) -> None:
        nonlocal calls
        calls += 1

    light.on_state_change(handler)
    light.remove_listener(handler)
    light.remove_listener(handler)
    await fake_ha.push_state_changed("light.kitchen", {"state": "on", "attributes": {}})
    await asyncio.sleep(0.05)
    assert calls == 0


async def test_unavailable_state(client: HAClient, fake_ha: FakeHA) -> None:
    light = client.light("kitchen")
    await fake_ha.push_state_changed("light.kitchen", None, None)
    await asyncio.sleep(0.05)
    assert light.state == "unavailable"
    assert not light.available


async def test_state_change_for_unknown_entity_is_ignored(
    client: HAClient, fake_ha: FakeHA
) -> None:
    await fake_ha.push_state_changed("switch.mystery", {"state": "on", "attributes": {}})
    await asyncio.sleep(0.05)
