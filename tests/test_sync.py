"""Tests for the SyncHAClient wrapper."""

from __future__ import annotations

import asyncio
import threading

import pytest
import pytest_asyncio

from haclient import SyncHAClient

from .fake_ha import FakeHA


@pytest_asyncio.fixture
async def running_fake_ha() -> FakeHA:
    """Placeholder for an unused fixture.

    Kept so that legacy ``running_fake_ha`` references in this file fail
    loudly with a clear error rather than silently using a stale server.
    Tests should depend on the standard ``fake_ha`` fixture from
    `tests.conftest` instead.

    Raises
    ------
    RuntimeError
        Always — this fixture must not be used.
    """
    raise RuntimeError("Use fake_ha fixture instead")


def _run_sync_in_thread(fake_ha: FakeHA) -> dict[str, object]:
    """Exercise `SyncHAClient` in a plain thread (no asyncio loop).

    Parameters
    ----------
    fake_ha : FakeHA
        Active fake server reachable from the thread.

    Returns
    -------
    dict
        Captured artefacts from the run; currently a single ``"calls"``
        key with the recorded WS service-call payloads.
    """
    results: dict[str, object] = {}

    def run() -> None:
        with SyncHAClient.from_url(
            fake_ha.base_url, token=fake_ha.token, ping_interval=0, request_timeout=3.0
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
    results = await asyncio.get_running_loop().run_in_executor(None, _run_sync_in_thread, fake_ha)
    calls = results["calls"]
    assert isinstance(calls, list)
    services = [c["service"] for c in calls]
    assert services == ["media_play", "volume_set"]


async def test_sync_client_refresh(fake_ha: FakeHA) -> None:
    def run() -> None:
        client = SyncHAClient.from_url(fake_ha.base_url, token=fake_ha.token, ping_interval=0)
        try:
            client.connect()
            client.refresh_all()
        finally:
            client.close()

    await asyncio.get_running_loop().run_in_executor(None, run)


async def test_sync_proxy_passes_non_coroutine_attrs(fake_ha: FakeHA) -> None:
    def run() -> str:
        client = SyncHAClient.from_url(fake_ha.base_url, token=fake_ha.token, ping_interval=0)
        try:
            client.connect()
            light = client.light("kitchen")
            eid = light.entity_id
            r = repr(light)
            return f"{eid}|{r}"
        finally:
            client.close()

    result = await asyncio.get_running_loop().run_in_executor(None, run)
    assert "light.kitchen" in result
    assert "Sync" in result


def test_sync_client_rejects_non_awaitable_submit() -> None:
    """_LoopThread.submit should reject plain values."""
    from haclient.sync import _LoopThread

    lt = _LoopThread()
    try:
        with pytest.raises(TypeError):
            lt.submit(123)  # type: ignore[arg-type]
    finally:
        lt.stop()


async def test_sync_client_all_accessors(fake_ha: FakeHA) -> None:
    def run() -> dict[str, str]:
        client = SyncHAClient.from_url(fake_ha.base_url, token=fake_ha.token, ping_interval=0)
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
                "scene": client.scene("sc").entity_id,
                "timer": client.timer("tm").entity_id,
            }
            light = client.light("l")
            light.state = "on"
            assert light.state == "on"
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
    assert names["scene"] == "scene.sc"
    assert names["timer"] == "timer.tm"


async def test_sync_create_scene(fake_ha: FakeHA) -> None:
    def run() -> str:
        client = SyncHAClient.from_url(fake_ha.base_url, token=fake_ha.token, ping_interval=0)
        try:
            client.connect()
            scene = client.scene.create(
                "romantic",
                {"light.ceiling": {"state": "on", "brightness": 80}},
            )
            return scene.entity_id  # type: ignore[no-any-return]
        finally:
            client.close()

    eid = await asyncio.get_running_loop().run_in_executor(None, run)
    assert eid == "scene.romantic"


async def test_sync_apply_scene(fake_ha: FakeHA) -> None:
    def run() -> None:
        client = SyncHAClient.from_url(fake_ha.base_url, token=fake_ha.token, ping_interval=0)
        try:
            client.connect()
            client.scene.apply({"light.ceiling": {"state": "on"}})
        finally:
            client.close()

    await asyncio.get_running_loop().run_in_executor(None, run)


async def test_sync_listeners_and_generic_domain(fake_ha: FakeHA) -> None:
    """Cover SyncHAClient.on_reconnect / on_disconnect / domain()."""

    def run() -> None:
        client = SyncHAClient.from_url(fake_ha.base_url, token=fake_ha.token, ping_interval=0)
        try:
            client.connect()
            client.on_reconnect(lambda: None)
            client.on_disconnect(lambda: None)
            generic = client.domain("light")
            assert generic("kitchen").entity_id == "light.kitchen"
            assert generic["kitchen"].entity_id == "light.kitchen"
            # Property accessor that returns a non-callable (e.g. spec).
            assert generic.spec.name == "light"
            # Sync timer accessor delegates to the timer domain.
            t = client.timer("countdown")
            assert t.entity_id == "timer.countdown"
        finally:
            client.close()

    await asyncio.get_running_loop().run_in_executor(None, run)
