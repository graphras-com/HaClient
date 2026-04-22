"""Tests for the SyncHAClient wrapper."""

from __future__ import annotations

import asyncio
import threading

import pytest
import pytest_asyncio

from ha_client import SyncHAClient

from .fake_ha import FakeHA


@pytest_asyncio.fixture
async def running_fake_ha() -> FakeHA:
    """A fake HA started by pytest-asyncio; used from a background thread."""
    # Intentionally not async-yielding here – the SyncHAClient needs a
    # stand-alone background server it can talk to.
    raise RuntimeError("Use fake_ha fixture instead")


def _run_sync_in_thread(fake_ha: FakeHA) -> dict[str, object]:
    """Exercise SyncHAClient in a plain thread (no asyncio loop)."""
    results: dict[str, object] = {}

    def run() -> None:
        with SyncHAClient(
            fake_ha.base_url, fake_ha.token, ping_interval=0, request_timeout=3.0
        ) as client:
            mp = client.media_player("livingroom")
            mp.play()
            mp.set_volume(0.4)
            results["calls"] = list(fake_ha.ws_service_calls)

    t = threading.Thread(target=run)
    t.start()
    t.join(timeout=15)
    assert not t.is_alive(), "sync thread hung"
    return results


async def test_sync_client_basic_operations(fake_ha: FakeHA) -> None:
    # Run the sync client in a thread while the fake server runs on the
    # main asyncio loop.
    results = await asyncio.get_running_loop().run_in_executor(None, _run_sync_in_thread, fake_ha)
    calls = results["calls"]
    assert isinstance(calls, list)
    services = [c["service"] for c in calls]
    assert services == ["media_play", "volume_set"]


async def test_sync_client_call_service(fake_ha: FakeHA) -> None:
    def run() -> None:
        client = SyncHAClient(fake_ha.base_url, fake_ha.token, ping_interval=0)
        try:
            client.connect()
            client.call_service("light", "turn_on", {"entity_id": "light.kitchen"})
            client.refresh_all()
        finally:
            client.close()

    await asyncio.get_running_loop().run_in_executor(None, run)
    assert any(c["service"] == "turn_on" for c in fake_ha.ws_service_calls)


async def test_sync_proxy_passes_non_coroutine_attrs(fake_ha: FakeHA) -> None:
    def run() -> str:
        client = SyncHAClient(fake_ha.base_url, fake_ha.token, ping_interval=0)
        try:
            client.connect()
            light = client.light("kitchen")
            # entity_id is a plain attribute – should pass through.
            eid = light.entity_id
            # repr should mention the wrapped entity.
            r = repr(light)
            return f"{eid}|{r}"
        finally:
            client.close()

    result = await asyncio.get_running_loop().run_in_executor(None, run)
    assert "light.kitchen" in result
    assert "Sync" in result


def test_sync_client_rejects_non_awaitable_submit() -> None:
    """_LoopThread.submit should reject plain values."""
    from ha_client.sync import _LoopThread

    lt = _LoopThread()
    try:
        with pytest.raises(TypeError):
            lt.submit(123)  # type: ignore[arg-type]
    finally:
        lt.stop()


async def test_sync_client_all_accessors(fake_ha: FakeHA) -> None:
    def run() -> dict[str, str]:
        client = SyncHAClient(fake_ha.base_url, fake_ha.token, ping_interval=0)
        try:
            client.connect()
            names = {
                "media_player": client.media_player("m").entity_id,
                "light": client.light("l").entity_id,
                "switch": client.switch("s").entity_id,
                "climate": client.climate("c").entity_id,
                "cover": client.cover("v").entity_id,
                "sensor": client.sensor("t").entity_id,
                "binary_sensor": client.binary_sensor("b").entity_id,
            }
            # exercise _SyncProxy __setattr__
            light = client.light("l")
            light.state = "on"
            assert light.state == "on"
            # .client property is available
            assert client.client is not None
            return names
        finally:
            client.close()

    names = await asyncio.get_running_loop().run_in_executor(None, run)
    assert names["media_player"] == "media_player.m"
    assert names["light"] == "light.l"
    assert names["switch"] == "switch.s"
    assert names["climate"] == "climate.c"
    assert names["cover"] == "cover.v"
    assert names["sensor"] == "sensor.t"
    assert names["binary_sensor"] == "binary_sensor.b"
