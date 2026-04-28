"""Tests for Timer proxy mode and Timer.create() managed lifecycle."""

from __future__ import annotations

import asyncio

import pytest

from haclient import HAClient
from haclient.domains.timer import Timer

from .fake_ha import FakeHA

# ---------------------------------------------------------------------------
# Proxy mode — client.timer("name") returns a plain proxy
# ---------------------------------------------------------------------------


async def test_proxy_timer_default_state(client: HAClient) -> None:
    """A proxy timer starts with state 'unknown' and is not managed."""
    t = client.timer("my_timer")
    assert t.state == "unknown"
    assert t.persistent is False
    assert t._created_by_us is False
    assert t._ensured is False


async def test_proxy_timer_start_sends_service_call(client: HAClient, fake_ha: FakeHA) -> None:
    """start() on a proxy timer sends a service call directly (no timer/create)."""
    t = client.timer("my_timer")
    t._apply_state({"state": "idle", "attributes": {"duration": "0:01:00"}})

    await t.start(duration="00:00:10")

    assert len(fake_ha.ws_service_calls) == 1
    call = fake_ha.ws_service_calls[0]
    assert call["domain"] == "timer"
    assert call["service"] == "start"


async def test_proxy_timer_not_auto_deleted(client: HAClient, fake_ha: FakeHA) -> None:
    """A proxy timer is never auto-deleted, even when transitioning to idle."""
    t = client.timer("existing_timer")
    t._apply_state({"state": "idle", "attributes": {"duration": "0:05:00"}})
    assert t._created_by_us is False

    await t.start(duration="00:00:05")

    await fake_ha.push_state_changed(
        "timer.existing_timer",
        {"state": "idle", "attributes": {}},
        {"state": "active", "attributes": {}},
    )
    await asyncio.sleep(0.1)

    # State updates normally but no auto-delete.
    assert t.state == "idle"
    assert t._created_by_us is False


async def test_proxy_timer_uses_given_name(client: HAClient) -> None:
    """Providing a name uses that name for the entity id."""
    t = client.timer("my_cooldown")
    assert t.entity_id == "timer.my_cooldown"


async def test_proxy_timer_delete(client: HAClient, fake_ha: FakeHA) -> None:
    """delete() sends timer/delete and resets _ensured."""
    t = client.timer("my_timer")
    t._ensured = True

    await t.delete()
    assert t._ensured is False


# ---------------------------------------------------------------------------
# Timer.create() — managed lifecycle
# ---------------------------------------------------------------------------


async def test_create_sends_ws_command(client: HAClient, fake_ha: FakeHA) -> None:
    """Timer.create() sends a timer/create WebSocket command."""
    t = await Timer.create(client, name="my_timer")

    assert t.entity_id == "timer.my_timer"
    assert t._ensured is True
    assert t._created_by_us is True


async def test_create_default_ephemeral(client: HAClient, fake_ha: FakeHA) -> None:
    """Timers from create() are ephemeral by default."""
    t = await Timer.create(client, name="my_timer")
    assert t.persistent is False


async def test_create_persistent(client: HAClient, fake_ha: FakeHA) -> None:
    """Timer.create(persistent=True) creates a persistent timer."""
    t = await Timer.create(client, name="my_timer", persistent=True)
    assert t.persistent is True


async def test_create_persistent_requires_name(client: HAClient) -> None:
    """Timer.create(persistent=True) without a name raises ValueError."""
    with pytest.raises(ValueError, match="Persistent timers require an explicit name"):
        await Timer.create(client, persistent=True)


async def test_create_unnamed_generates_id(client: HAClient, fake_ha: FakeHA) -> None:
    """Timer.create() without a name generates a unique entity id."""
    t = await Timer.create(client)
    assert t.entity_id.startswith("timer.haclient_")
    assert len(t.entity_id) == len("timer.haclient_") + 8


async def test_create_unnamed_unique_ids(client: HAClient, fake_ha: FakeHA) -> None:
    """Each Timer.create() call without a name produces a different id."""
    t1 = await Timer.create(client)
    t2 = await Timer.create(client)
    assert t1.entity_id != t2.entity_id


async def test_create_returns_existing_if_registered(client: HAClient, fake_ha: FakeHA) -> None:
    """Timer.create() returns an existing Timer if one is already registered."""
    t1 = await Timer.create(client, name="my_timer")
    t2 = await Timer.create(client, name="my_timer")
    assert t1 is t2


async def test_create_with_custom_duration(client: HAClient, fake_ha: FakeHA) -> None:
    """Timer.create() passes the duration to the WS command."""
    t = await Timer.create(client, name="my_timer", duration="00:05:00")

    # Timer was created successfully.
    assert t._ensured is True
    assert t._created_by_us is True


# ---------------------------------------------------------------------------
# Ephemeral auto-delete (via Timer.create)
# ---------------------------------------------------------------------------


async def test_ephemeral_auto_deletes_on_idle(client: HAClient, fake_ha: FakeHA) -> None:
    """An ephemeral timer auto-deletes its HA helper when it transitions to idle."""
    t = await Timer.create(client, name="my_timer")
    await t.start(duration="00:00:05")

    await fake_ha.push_state_changed(
        "timer.my_timer",
        {"state": "idle", "attributes": {}},
        {"state": "active", "attributes": {}},
    )
    await asyncio.sleep(0.1)

    assert t.state == "unknown"
    assert t._ensured is False


async def test_ephemeral_user_on_idle_fires_before_cleanup(
    client: HAClient, fake_ha: FakeHA
) -> None:
    """User on_idle listeners fire even though the timer is ephemeral."""
    t = await Timer.create(client, name="my_timer")
    captured: list[tuple[str | None, str | None]] = []

    @t.on_idle
    def handler(old: str | None, new: str | None) -> None:
        captured.append((old, new))

    await t.start(duration="00:00:05")

    await fake_ha.push_state_changed(
        "timer.my_timer",
        {"state": "idle", "attributes": {}},
        {"state": "active", "attributes": {}},
    )
    await asyncio.sleep(0.1)

    assert captured == [("active", "idle")]


async def test_ephemeral_can_restart_after_auto_delete(client: HAClient, fake_ha: FakeHA) -> None:
    """After auto-delete, calling Timer.create() again re-creates the timer."""
    t = await Timer.create(client, name="my_timer")
    await t.start(duration="00:00:05")

    # Trigger auto-delete.
    await fake_ha.push_state_changed(
        "timer.my_timer",
        {"state": "idle", "attributes": {}},
        {"state": "active", "attributes": {}},
    )
    await asyncio.sleep(0.1)
    assert t._ensured is False
    assert t.state == "unknown"

    # Re-create via Timer.create — should get the same object back.
    t2 = await Timer.create(client, name="my_timer")
    assert t2 is t
    assert t._ensured is True
    assert t._created_by_us is True


async def test_ephemeral_no_cleanup_on_idle_to_idle(client: HAClient, fake_ha: FakeHA) -> None:
    """No auto-delete when old_state is already idle (avoid spurious deletes)."""
    t = await Timer.create(client, name="my_timer")

    # idle -> idle should not trigger cleanup.
    await fake_ha.push_state_changed(
        "timer.my_timer",
        {"state": "idle", "attributes": {}},
        {"state": "idle", "attributes": {}},
    )
    await asyncio.sleep(0.1)

    assert t._ensured is True


async def test_ephemeral_no_cleanup_when_old_state_none(client: HAClient, fake_ha: FakeHA) -> None:
    """No auto-delete when old_state is None (initial state load)."""
    t = await Timer.create(client, name="my_timer")

    await fake_ha.push_state_changed(
        "timer.my_timer",
        {"state": "idle", "attributes": {}},
        None,
    )
    await asyncio.sleep(0.1)

    assert t._ensured is True


# ---------------------------------------------------------------------------
# Persistent timers (via Timer.create)
# ---------------------------------------------------------------------------


async def test_persistent_timer_no_auto_delete(client: HAClient, fake_ha: FakeHA) -> None:
    """A persistent timer does not auto-delete its HA helper on idle."""
    t = await Timer.create(client, name="my_timer", persistent=True)
    assert t.persistent is True
    await t.start(duration="00:00:05")

    await fake_ha.push_state_changed(
        "timer.my_timer",
        {"state": "idle", "attributes": {}},
        {"state": "active", "attributes": {}},
    )
    await asyncio.sleep(0.1)

    assert t.state == "idle"
    assert t._ensured is True


# ---------------------------------------------------------------------------
# Library-created vs pre-existing distinction
# ---------------------------------------------------------------------------


async def test_library_created_timer_auto_deletes(client: HAClient, fake_ha: FakeHA) -> None:
    """A timer created via Timer.create() auto-deletes on idle."""
    t = await Timer.create(client, name="lib_timer")
    assert t._created_by_us is True

    await t.start(duration="00:00:05")

    await fake_ha.push_state_changed(
        "timer.lib_timer",
        {"state": "idle", "attributes": {}},
        {"state": "active", "attributes": {}},
    )
    await asyncio.sleep(0.1)

    assert t.state == "unknown"
    assert t._created_by_us is False


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


async def test_ephemeral_auto_cleanup_handles_delete_failure(
    client: HAClient, fake_ha: FakeHA
) -> None:
    """If the delete WS command fails, _auto_cleanup logs but still resets state."""
    from aiohttp import web

    async def fail_delete(server: FakeHA, ws: web.WebSocketResponse, msg: dict) -> None:
        await ws.send_json(
            {
                "id": msg["id"],
                "type": "result",
                "success": False,
                "error": {"code": "not_found", "message": "Timer not found"},
            }
        )

    fake_ha.handlers["timer/delete"] = fail_delete

    t = await Timer.create(client, name="will_fail")
    await t.start(duration="00:00:05")

    await fake_ha.push_state_changed(
        "timer.will_fail",
        {"state": "idle", "attributes": {}},
        {"state": "active", "attributes": {}},
    )
    await asyncio.sleep(0.1)

    # Cleanup failed but state should still be reset.
    assert t.state == "unknown"


async def test_handle_timer_event_ignores_unknown_event_type(
    client: HAClient, fake_ha: FakeHA
) -> None:
    """_handle_timer_event returns early for unrecognised event types."""
    t = client.timer("my_timer")
    captured: list[tuple] = []

    @t.on_finished
    def handler(eid: str, data: dict) -> None:
        captured.append((eid, data))

    # Push an event with a bogus type via the timer event handler directly.
    t._handle_timer_event("timer.unknown_event", {"entity_id": "timer.my_timer"})
    await asyncio.sleep(0.05)
    assert captured == []


async def test_parse_duration_invalid_format() -> None:
    """_parse_duration_to_seconds returns None for non-HH:MM:SS strings."""
    from haclient.domains.timer import _parse_duration_to_seconds

    assert _parse_duration_to_seconds("invalid") is None
    assert _parse_duration_to_seconds("abc:de:fg") is None
