"""Tests for Timer auto-create, delete, ephemeral and persistent lifecycle."""

from __future__ import annotations

import asyncio

import pytest

from haclient import HAClient

from .fake_ha import FakeHA

# ---------------------------------------------------------------------------
# Auto-create (unchanged behaviour)
# ---------------------------------------------------------------------------


async def test_timer_start_auto_creates_when_unknown(client: HAClient, fake_ha: FakeHA) -> None:
    """Calling start() on a timer with state 'unknown' should send timer/create first."""
    t = client.timer("my_timer")
    assert t.state == "unknown"

    await t.start(duration="00:00:10")

    assert len(fake_ha.ws_service_calls) == 1
    call = fake_ha.ws_service_calls[0]
    assert call["domain"] == "timer"
    assert call["service"] == "start"
    assert t._ensured is True


async def test_timer_start_skips_create_when_state_known(client: HAClient, fake_ha: FakeHA) -> None:
    """If the timer already has a state from HA, _ensure_exists is a no-op."""
    t = client.timer("my_timer")
    t._apply_state({"state": "idle", "attributes": {"duration": "0:01:00"}})
    assert t.state == "idle"

    await t.start(duration="00:00:10")

    assert len(fake_ha.ws_service_calls) == 1
    call = fake_ha.ws_service_calls[0]
    assert call["domain"] == "timer"
    assert call["service"] == "start"


async def test_timer_ensure_exists_only_called_once(client: HAClient, fake_ha: FakeHA) -> None:
    """After the first _ensure_exists succeeds, subsequent calls are no-ops."""
    t = client.timer("my_timer")
    assert t.state == "unknown"

    await t.start(duration="00:00:10")
    await t.pause()

    assert len(fake_ha.ws_service_calls) == 2
    assert t._ensured is True


async def test_timer_pause_auto_creates(client: HAClient, fake_ha: FakeHA) -> None:
    """pause() should also trigger auto-create."""
    t = client.timer("my_timer")
    await t.pause()
    assert t._ensured is True
    assert len(fake_ha.ws_service_calls) == 1


async def test_timer_cancel_auto_creates(client: HAClient, fake_ha: FakeHA) -> None:
    """cancel() should also trigger auto-create."""
    t = client.timer("my_timer")
    await t.cancel()
    assert t._ensured is True


async def test_timer_finish_auto_creates(client: HAClient, fake_ha: FakeHA) -> None:
    """finish() should also trigger auto-create."""
    t = client.timer("my_timer")
    await t.finish()
    assert t._ensured is True


async def test_timer_change_auto_creates(client: HAClient, fake_ha: FakeHA) -> None:
    """change() should also trigger auto-create."""
    t = client.timer("my_timer")
    await t.change(duration="00:00:30")
    assert t._ensured is True


async def test_timer_delete(client: HAClient, fake_ha: FakeHA) -> None:
    """delete() sends timer/delete and resets _ensured."""
    t = client.timer("my_timer")
    await t.start()
    assert t._ensured is True

    await t.delete()
    assert t._ensured is False


async def test_timer_delete_then_start_recreates(client: HAClient, fake_ha: FakeHA) -> None:
    """After delete(), the next action should re-create the timer."""
    t = client.timer("my_timer")
    await t.start()
    assert t._ensured is True

    await t.delete()
    assert t._ensured is False

    t.state = "unknown"
    await t.start()
    assert t._ensured is True


# ---------------------------------------------------------------------------
# Ephemeral timers (default)
# ---------------------------------------------------------------------------


async def test_ephemeral_timer_is_default(client: HAClient) -> None:
    """Timers are ephemeral by default."""
    t = client.timer("my_timer")
    assert t.persistent is False


async def test_ephemeral_auto_deletes_on_idle(client: HAClient, fake_ha: FakeHA) -> None:
    """An ephemeral timer auto-deletes its HA helper when it transitions to idle."""
    t = client.timer("my_timer")
    await t.start(duration="00:00:05")

    # Simulate HA reporting active -> idle (timer finished).
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
    t = client.timer("my_timer")
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
    """After auto-delete, calling start() re-creates the timer transparently."""
    t = client.timer("my_timer")
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

    # Restart — should re-create.
    await t.start(duration="00:00:10")
    assert t._ensured is True


async def test_ephemeral_no_cleanup_on_idle_to_idle(client: HAClient, fake_ha: FakeHA) -> None:
    """No auto-delete when old_state is already idle (avoid spurious deletes)."""
    t = client.timer("my_timer")
    t._ensured = True

    # idle -> idle should not trigger cleanup.
    await fake_ha.push_state_changed(
        "timer.my_timer",
        {"state": "idle", "attributes": {}},
        {"state": "idle", "attributes": {}},
    )
    await asyncio.sleep(0.1)

    # _ensured should remain True — no cleanup was triggered.
    assert t._ensured is True


async def test_ephemeral_no_cleanup_when_old_state_none(client: HAClient, fake_ha: FakeHA) -> None:
    """No auto-delete when old_state is None (initial state load)."""
    t = client.timer("my_timer")
    t._ensured = True

    await fake_ha.push_state_changed(
        "timer.my_timer",
        {"state": "idle", "attributes": {}},
        None,
    )
    await asyncio.sleep(0.1)

    assert t._ensured is True


# ---------------------------------------------------------------------------
# Persistent timers
# ---------------------------------------------------------------------------


async def test_persistent_timer_no_auto_delete(client: HAClient, fake_ha: FakeHA) -> None:
    """A persistent timer does not auto-delete its HA helper on idle."""
    t = client.timer("my_timer", persistent=True)
    assert t.persistent is True
    await t.start(duration="00:00:05")

    await fake_ha.push_state_changed(
        "timer.my_timer",
        {"state": "idle", "attributes": {}},
        {"state": "active", "attributes": {}},
    )
    await asyncio.sleep(0.1)

    # State updated but _ensured not reset, state not reverted to unknown.
    assert t.state == "idle"
    assert t._ensured is True


async def test_persistent_requires_name(client: HAClient) -> None:
    """persistent=True without a name should raise ValueError."""
    with pytest.raises(ValueError, match="Persistent timers require an explicit name"):
        client.timer(persistent=True)


# ---------------------------------------------------------------------------
# Pre-existing HA timers (not created by us)
# ---------------------------------------------------------------------------


async def test_preexisting_timer_not_auto_deleted(client: HAClient, fake_ha: FakeHA) -> None:
    """A timer that already exists in HA must not be auto-deleted on idle."""
    t = client.timer("existing_timer")
    # Simulate HA reporting the timer during initial state fetch.
    t._apply_state({"state": "idle", "attributes": {"duration": "0:05:00"}})
    assert t.state == "idle"
    assert t._created_by_us is False

    # Start it (no timer/create because state is already known).
    await t.start(duration="00:00:05")

    # Simulate active -> idle.
    await fake_ha.push_state_changed(
        "timer.existing_timer",
        {"state": "idle", "attributes": {}},
        {"state": "active", "attributes": {}},
    )
    await asyncio.sleep(0.1)

    # State should update normally but no auto-delete.
    assert t.state == "idle"
    assert t._created_by_us is False


async def test_library_created_timer_auto_deletes(client: HAClient, fake_ha: FakeHA) -> None:
    """A timer created by the library (via _ensure_exists) does auto-delete."""
    t = client.timer("lib_timer")
    assert t.state == "unknown"

    await t.start(duration="00:00:05")
    assert t._created_by_us is True

    await fake_ha.push_state_changed(
        "timer.lib_timer",
        {"state": "idle", "attributes": {}},
        {"state": "active", "attributes": {}},
    )
    await asyncio.sleep(0.1)

    assert t.state == "unknown"
    assert t._created_by_us is False


# ---------------------------------------------------------------------------
# Auto-generated names (unnamed ephemeral timers)
# ---------------------------------------------------------------------------


async def test_unnamed_ephemeral_generates_id(client: HAClient) -> None:
    """Calling timer() without a name generates a unique entity id."""
    t = client.timer()
    assert t.entity_id.startswith("timer.haclient_")
    assert len(t.entity_id) == len("timer.haclient_") + 8


async def test_unnamed_ephemeral_unique_ids(client: HAClient) -> None:
    """Each unnamed timer() call produces a different id."""
    t1 = client.timer()
    t2 = client.timer()
    assert t1.entity_id != t2.entity_id


async def test_named_ephemeral_uses_given_name(client: HAClient) -> None:
    """Providing a name uses that name, not a generated one."""
    t = client.timer("my_cooldown")
    assert t.entity_id == "timer.my_cooldown"


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

    t = client.timer("will_fail")
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
