"""Tests for the core `EventBus`."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from haclient.core.events import EventBus

from .fake_ha import FakeHA


class _FakeWS:
    """Minimal `WebSocketPort` stub for unit-testing the bus.

    Records subscribe/unsubscribe calls and lets tests push events to the
    handler that the bus registered.
    """

    def __init__(self) -> None:
        """Initialise empty subscription / listener tracking state."""
        self.connected_flag: bool = True
        self.subscriptions: dict[int, tuple[str | None, Any]] = {}
        self.next_id = 0
        self.subscribe_failure: Exception | None = None
        self.unsubscribed: list[int] = []
        self.disconnect_listeners: list[Any] = []
        self.reconnect_listeners: list[Any] = []

    @property
    def connected(self) -> bool:
        """Return ``True`` while the simulated socket is open."""
        return self.connected_flag

    async def connect(self) -> None:
        """Stub: no-op connect to satisfy the `WebSocketPort` protocol."""

    async def close(self) -> None:
        """Stub: no-op close to satisfy the `WebSocketPort` protocol."""

    async def send_command(self, payload: dict[str, Any], *, timeout: float | None = None) -> Any:
        """Stub: ignore commands and return ``None``."""
        return None

    async def subscribe_events(self, handler: Any, event_type: str | None = None) -> int:
        """Record a subscription and return a fresh id.

        Setting `subscribe_failure` causes this to raise; tests use that
        to exercise error paths.
        """
        if self.subscribe_failure is not None:
            raise self.subscribe_failure
        self.next_id += 1
        self.subscriptions[self.next_id] = (event_type, handler)
        return self.next_id

    async def unsubscribe(self, subscription_id: int) -> None:
        """Forget a subscription and record the id for assertions."""
        self.unsubscribed.append(subscription_id)
        self.subscriptions.pop(subscription_id, None)

    def on_disconnect(self, handler: Any) -> Any:
        """Record a disconnect listener and return it."""
        self.disconnect_listeners.append(handler)
        return handler

    def on_reconnect(self, handler: Any) -> Any:
        """Record a reconnect listener and return it."""
        self.reconnect_listeners.append(handler)
        return handler

    async def push(self, event_type: str, event: dict[str, Any]) -> None:
        """Deliver *event* to every handler subscribed to *event_type*.

        Used by tests to drive `EventBus` from outside without a real
        WebSocket transport. Awaitable handlers are awaited.

        Parameters
        ----------
        event_type : str
            Event type whose subscribers should receive *event*.
        event : dict
            The event payload as it would arrive over the WS.
        """
        for et, handler in self.subscriptions.values():
            if et == event_type:
                result = handler(event)
                if asyncio.iscoroutine(result):
                    await result


async def test_subscribe_before_start_batches() -> None:
    ws = _FakeWS()
    bus = EventBus(ws)  # type: ignore[arg-type]
    captured: list[dict[str, Any]] = []
    bus.subscribe("ev", lambda e: captured.append(e))
    assert ws.subscriptions == {}
    await bus.start()
    assert len(ws.subscriptions) == 1
    await ws.push("ev", {"a": 1})
    assert captured == [{"a": 1}]


async def test_subscribe_after_start_subscribes_immediately() -> None:
    ws = _FakeWS()
    bus = EventBus(ws)  # type: ignore[arg-type]
    await bus.start()
    captured: list[dict[str, Any]] = []
    bus.subscribe("ev", lambda e: captured.append(e))
    # The lazy subscribe is scheduled; wait one loop iteration.
    await asyncio.sleep(0)
    await ws.push("ev", {"k": "v"})
    assert captured == [{"k": "v"}]


async def test_unsubscribe_removes_handler() -> None:
    ws = _FakeWS()
    bus = EventBus(ws)  # type: ignore[arg-type]
    handler_calls: list[Any] = []

    def handler(e: dict[str, Any]) -> None:
        handler_calls.append(e)

    bus.subscribe("ev", handler)
    await bus.start()
    bus.unsubscribe("ev", handler)
    # Allow scheduled unsubscribe to run.
    await asyncio.sleep(0)
    assert ws.unsubscribed == [1]
    await ws.push("ev", {"x": 1})
    assert handler_calls == []


async def test_unsubscribe_unknown_handler_is_noop() -> None:
    ws = _FakeWS()
    bus = EventBus(ws)  # type: ignore[arg-type]
    bus.unsubscribe("ev", lambda e: None)  # never registered
    bus.subscribe("ev", lambda e: None)
    bus.unsubscribe("ev", lambda e: None)  # different func instance


async def test_buffering_captures_then_drains() -> None:
    ws = _FakeWS()
    bus = EventBus(ws)  # type: ignore[arg-type]
    captured: list[dict[str, Any]] = []
    bus.subscribe("ev", lambda e: captured.append(e))
    bus.enable_buffering("ev")
    await bus.start()
    await ws.push("ev", {"n": 1})
    await ws.push("ev", {"n": 2})
    assert captured == []
    await bus.drain_buffer("ev")
    assert captured == [{"n": 1}, {"n": 2}]


async def test_discard_buffer_drops_events() -> None:
    ws = _FakeWS()
    bus = EventBus(ws)  # type: ignore[arg-type]
    captured: list[dict[str, Any]] = []
    bus.subscribe("ev", lambda e: captured.append(e))
    bus.enable_buffering("ev")
    await bus.start()
    await ws.push("ev", {"n": 1})
    bus.discard_buffer("ev")
    await bus.drain_buffer("ev")  # no-op, buffer already discarded
    assert captured == []


async def test_drain_buffer_unknown_event_type() -> None:
    ws = _FakeWS()
    bus = EventBus(ws)  # type: ignore[arg-type]
    await bus.drain_buffer("nothing")  # should not raise


async def test_double_start_is_noop() -> None:
    ws = _FakeWS()
    bus = EventBus(ws)  # type: ignore[arg-type]
    bus.subscribe("ev", lambda e: None)
    await bus.start()
    await bus.start()
    assert len(ws.subscriptions) == 1


async def test_subscribe_failure_during_start_is_recorded() -> None:
    """Pre-start subscriptions failing during `start` must be observable.

    The historical contract is that `start` does not raise so a single
    flaky event type cannot abort the whole client. The new contract is
    that the failure is recorded on the bus so callers can inspect it.
    """
    ws = _FakeWS()
    ws.subscribe_failure = RuntimeError("boom")
    bus = EventBus(ws)  # type: ignore[arg-type]
    bus.subscribe("ev", lambda e: None)
    await bus.start()  # must not raise
    # No id recorded because the WS subscribe raised.
    assert ws.subscriptions == {}
    failure = bus.subscription_failure("ev")
    assert isinstance(failure, RuntimeError)
    assert str(failure) == "boom"


async def test_subscribe_post_start_failure_is_observable() -> None:
    """A post-start `subscribe` that fails must surface via the API."""
    ws = _FakeWS()
    bus = EventBus(ws)  # type: ignore[arg-type]
    await bus.start()
    ws.subscribe_failure = RuntimeError("nope")
    bus.subscribe("ev", lambda e: None)
    pending = bus.pending_subscription("ev")
    assert pending is not None
    # The task completes with the transport error and the failure is
    # exposed via `subscription_failure`.
    with pytest.raises(RuntimeError, match="nope"):
        await pending
    failure = bus.subscription_failure("ev")
    assert isinstance(failure, RuntimeError)
    assert ws.subscriptions == {}


async def test_subscribe_post_start_recovers_on_retry() -> None:
    """A successful subsequent attempt clears the recorded failure."""
    ws = _FakeWS()
    bus = EventBus(ws)  # type: ignore[arg-type]
    await bus.start()
    ws.subscribe_failure = RuntimeError("transient")

    def handler(_e: dict[str, Any]) -> None:
        return None

    bus.subscribe("ev", handler)
    pending = bus.pending_subscription("ev")
    assert pending is not None
    with pytest.raises(RuntimeError):
        await pending
    assert bus.subscription_failure("ev") is not None

    # Drop and retry with the transport healthy.
    bus.unsubscribe("ev", handler)
    ws.subscribe_failure = None
    bus.subscribe("ev", handler)
    retry = bus.pending_subscription("ev")
    assert retry is not None
    await retry
    assert bus.subscription_failure("ev") is None
    assert len(ws.subscriptions) == 1


async def test_subscribe_async_propagates_failure_and_rolls_back() -> None:
    """`subscribe_async` raises and leaves no dangling handler."""
    ws = _FakeWS()
    bus = EventBus(ws)  # type: ignore[arg-type]
    await bus.start()
    ws.subscribe_failure = RuntimeError("denied")

    def handler(_e: dict[str, Any]) -> None:
        return None

    with pytest.raises(RuntimeError, match="denied"):
        await bus.subscribe_async("ev", handler)

    # Handler must NOT remain registered after a failed first subscribe,
    # otherwise the caller's view diverges from the transport state.
    assert ws.subscriptions == {}
    ws.subscribe_failure = None
    # A subsequent subscribe is treated as a fresh "first handler" and
    # actually performs the WS call.
    await bus.subscribe_async("ev", handler)
    assert len(ws.subscriptions) == 1


async def test_subscribe_async_before_start_is_batched() -> None:
    """`subscribe_async` registered before `start` does not hit the WS."""
    ws = _FakeWS()
    bus = EventBus(ws)  # type: ignore[arg-type]
    await bus.subscribe_async("ev", lambda _e: None)
    assert ws.subscriptions == {}
    await bus.start()
    assert len(ws.subscriptions) == 1


async def test_subscribe_async_additional_handler_skips_ws_call() -> None:
    """Adding a second handler for an event type re-uses the subscription."""
    ws = _FakeWS()
    bus = EventBus(ws)  # type: ignore[arg-type]
    await bus.start()
    await bus.subscribe_async("ev", lambda _e: None)
    assert len(ws.subscriptions) == 1
    # A second handler must succeed without raising even if a fresh
    # subscribe would now fail; it should not call the WS at all.
    ws.subscribe_failure = RuntimeError("would fail if called")
    await bus.subscribe_async("ev", lambda _e: None)
    assert len(ws.subscriptions) == 1


async def test_unsubscribe_async_propagates_transport_errors() -> None:
    """`unsubscribe_async` raises if the WS rejects the call."""
    ws = _FakeWS()
    bus = EventBus(ws)  # type: ignore[arg-type]

    def handler(_e: dict[str, Any]) -> None:
        return None

    bus.subscribe("ev", handler)
    await bus.start()

    original = ws.unsubscribe

    async def failing_unsubscribe(sub_id: int) -> None:
        raise RuntimeError("nope")

    ws.unsubscribe = failing_unsubscribe  # type: ignore[method-assign]
    try:
        with pytest.raises(RuntimeError, match="nope"):
            await bus.unsubscribe_async("ev", handler)
    finally:
        ws.unsubscribe = original  # type: ignore[method-assign]


async def test_unsubscribe_async_unknown_handler_is_noop() -> None:
    ws = _FakeWS()
    bus = EventBus(ws)  # type: ignore[arg-type]
    await bus.unsubscribe_async("ev", lambda _e: None)  # never registered
    bus.subscribe("ev", lambda _e: None)
    await bus.unsubscribe_async("ev", lambda _e: None)  # different instance


async def test_pending_subscription_none_when_idle() -> None:
    ws = _FakeWS()
    bus = EventBus(ws)  # type: ignore[arg-type]
    assert bus.pending_subscription("ev") is None
    bus.subscribe("ev", lambda _e: None)
    await bus.start()
    # Subscribe was done synchronously inside start(), no pending task.
    assert bus.pending_subscription("ev") is None


async def test_unsubscribe_async_does_not_release_ws_when_handlers_remain() -> None:
    """Removing one of several handlers must not tear down the WS subscription."""
    ws = _FakeWS()
    bus = EventBus(ws)  # type: ignore[arg-type]

    def h1(_e: dict[str, Any]) -> None:
        return None

    def h2(_e: dict[str, Any]) -> None:
        return None

    bus.subscribe("ev", h1)
    bus.subscribe("ev", h2)
    await bus.start()
    await bus.unsubscribe_async("ev", h1)
    assert ws.unsubscribed == []  # WS subscription still active for h2
    assert len(ws.subscriptions) == 1


async def test_cancelled_subscription_task_clears_pending() -> None:
    """A cancelled post-start subscribe task is forgotten cleanly."""
    ws = _FakeWS()
    bus = EventBus(ws)  # type: ignore[arg-type]

    # Slow down the WS so we can cancel the in-flight task.
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow_subscribe(handler: Any, event_type: str | None = None) -> int:
        started.set()
        await release.wait()
        return 1

    ws.subscribe_events = slow_subscribe  # type: ignore[method-assign]
    await bus.start()
    bus.subscribe("ev", lambda _e: None)
    task = bus.pending_subscription("ev")
    assert task is not None
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    # No failure recorded for a cancellation; the slot is cleared.
    assert bus.subscription_failure("ev") is None
    assert bus.pending_subscription("ev") is None
    release.set()


async def test_install_reconnect_hook_invokes_callback() -> None:
    ws = _FakeWS()
    bus = EventBus(ws)  # type: ignore[arg-type]
    fired = asyncio.Event()

    async def callback(_event: dict[str, Any]) -> None:
        fired.set()

    bus.install_reconnect_hook(callback)
    assert ws.reconnect_listeners
    # Trigger the registered hook.
    hook = ws.reconnect_listeners[0]
    await hook()
    assert fired.is_set()


async def test_install_reconnect_hook_none() -> None:
    ws = _FakeWS()
    bus = EventBus(ws)  # type: ignore[arg-type]
    bus.install_reconnect_hook(None)
    assert ws.reconnect_listeners == []


async def test_async_handler_is_awaited() -> None:
    ws = _FakeWS()
    bus = EventBus(ws)  # type: ignore[arg-type]
    captured: list[Any] = []

    async def handler(event: dict[str, Any]) -> None:
        captured.append(event)

    bus.subscribe("ev", handler)
    await bus.start()
    await ws.push("ev", {"y": True})
    assert captured == [{"y": True}]


async def test_handler_exception_is_swallowed() -> None:
    ws = _FakeWS()
    bus = EventBus(ws)  # type: ignore[arg-type]

    def boom(_event: dict[str, Any]) -> None:
        raise RuntimeError("nope")

    bus.subscribe("ev", boom)
    await bus.start()
    await ws.push("ev", {})  # should not raise


async def test_state_priming_race_via_real_ws(fake_ha: FakeHA) -> None:
    """Integration test: events that arrive between subscribe and snapshot
    are buffered and applied after the REST snapshot."""
    fake_ha.states = [
        {"entity_id": "light.kitchen", "state": "off", "attributes": {}},
    ]
    # Configure the fake to push a state_changed event right after
    # subscribe, before the REST snapshot completes. We piggy-back on
    # the subscribe handler to push the event mid-flight.
    from aiohttp import web

    pushed = asyncio.Event()

    async def subscribe_then_push(
        server: FakeHA, ws: web.WebSocketResponse, msg: dict[str, Any]
    ) -> None:
        event_type = msg.get("event_type", "*")
        sub_id = msg["id"]
        server.subscriptions.setdefault(event_type, []).append(sub_id)
        await ws.send_json({"id": sub_id, "type": "result", "success": True, "result": None})
        if event_type == "state_changed" and not pushed.is_set():
            pushed.set()
            # Push an event that should be buffered.
            await ws.send_json(
                {
                    "id": sub_id,
                    "type": "event",
                    "event": {
                        "event_type": "state_changed",
                        "data": {
                            "entity_id": "light.kitchen",
                            "old_state": {"state": "off", "attributes": {}},
                            "new_state": {"state": "on", "attributes": {"brightness": 222}},
                        },
                    },
                }
            )

    fake_ha.handlers["subscribe_events"] = subscribe_then_push

    from haclient import HAClient

    ha = HAClient.from_url(fake_ha.base_url, token=fake_ha.token, ping_interval=0)
    light = ha.light("kitchen")
    try:
        await ha.connect()
        # The buffered event should have been drained, so the brightness
        # reflects the post-event value, not the snapshot.
        assert light.state == "on"
        assert light.brightness == 222
    finally:
        await ha.close()


# Re-use the autouse fake_ha fixture from conftest in the integration test.
@pytest.fixture(autouse=False)
def _placeholder() -> None:  # pragma: no cover - just keeps imports tidy
    return None
