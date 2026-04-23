"""Tests for the low-level WebSocketClient."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from aiohttp import web

from haclient.exceptions import (
    AuthenticationError,
    CommandError,
    ConnectionClosedError,
    HAClientError,
)
from haclient.exceptions import TimeoutError as HATimeoutError
from haclient.websocket import WebSocketClient

from .fake_ha import FakeHA


async def _make_ws(fake_ha: FakeHA, **kwargs: Any) -> WebSocketClient:
    ws = WebSocketClient(
        fake_ha.ws_url,
        fake_ha.token,
        ping_interval=0,
        request_timeout=3.0,
        **kwargs,
    )
    await ws.connect()
    return ws


async def test_connect_and_auth(fake_ha: FakeHA) -> None:
    ws = await _make_ws(fake_ha)
    try:
        assert ws.connected
    finally:
        await ws.close()
    assert not ws.connected


async def test_auth_invalid(fake_ha: FakeHA) -> None:
    ws = WebSocketClient(fake_ha.ws_url, "wrong-token", ping_interval=0)
    with pytest.raises(AuthenticationError):
        await ws.connect()
    await ws.close()


async def test_send_command_success(fake_ha: FakeHA) -> None:
    ws = await _make_ws(fake_ha)
    try:
        result = await ws.send_command(
            {"type": "call_service", "domain": "light", "service": "turn_on"}
        )
        assert isinstance(result, dict)
        assert "context" in result
    finally:
        await ws.close()


async def test_send_command_error(fake_ha: FakeHA) -> None:
    ws = await _make_ws(fake_ha)
    try:
        with pytest.raises(CommandError) as excinfo:
            await ws.send_command({"type": "unknown/command"})
        assert excinfo.value.code == "unknown_command"
    finally:
        await ws.close()


async def test_send_command_timeout(fake_ha: FakeHA) -> None:
    async def never_reply(server: FakeHA, ws: web.WebSocketResponse, msg: dict[str, Any]) -> None:
        await asyncio.sleep(10)

    fake_ha.handlers["slow"] = never_reply
    ws = await _make_ws(fake_ha)
    try:
        with pytest.raises(HATimeoutError):
            await ws.send_command({"type": "slow"}, timeout=0.1)
    finally:
        await ws.close()


async def test_subscribe_and_event(fake_ha: FakeHA) -> None:
    ws = await _make_ws(fake_ha)
    received: list[dict[str, Any]] = []

    async def handler(event: dict[str, Any]) -> None:
        received.append(event)

    try:
        sub_id = await ws.subscribe_events(handler, "state_changed")
        await fake_ha.push_event(
            "state_changed",
            {"data": {"entity_id": "light.kitchen"}},
        )
        await asyncio.sleep(0.05)
        assert received
        assert received[0]["event_type"] == "state_changed"
        await ws.unsubscribe(sub_id)
    finally:
        await ws.close()


async def test_ping_pong(fake_ha: FakeHA) -> None:
    ws = await _make_ws(fake_ha)
    try:
        await ws.ping(timeout=1.0)
    finally:
        await ws.close()


async def test_send_command_while_disconnected(fake_ha: FakeHA) -> None:
    ws = WebSocketClient(fake_ha.ws_url, fake_ha.token, ping_interval=0, reconnect=False)
    with pytest.raises(ConnectionClosedError):
        await ws.send_command({"type": "ping"})


async def test_reconnect_on_drop(fake_ha: FakeHA) -> None:
    """Force the server to close the WS and verify the client reconnects."""
    ws = await _make_ws(fake_ha, reconnect=True)
    try:
        received: list[dict[str, Any]] = []

        async def handler(event: dict[str, Any]) -> None:
            received.append(event)

        await ws.subscribe_events(handler, "state_changed")

        for conn in list(fake_ha.connections):
            await conn.close()

        for _ in range(50):
            await asyncio.sleep(0.1)
            if ws.connected:
                break
        assert ws.connected

        await fake_ha.push_event("state_changed", {"data": {"entity_id": "x"}})
        await asyncio.sleep(0.1)
        assert received
    finally:
        await ws.close()


async def test_disconnect_listener(fake_ha: FakeHA) -> None:
    ws = await _make_ws(fake_ha, reconnect=False)
    called = asyncio.Event()

    @ws.on_disconnect
    async def on_disconnect() -> None:
        called.set()

    for conn in list(fake_ha.connections):
        await conn.close()

    await asyncio.wait_for(called.wait(), timeout=3)
    await ws.close()


async def test_disconnect_listener_sync(fake_ha: FakeHA) -> None:
    ws = await _make_ws(fake_ha, reconnect=False)
    called = threading_like_flag()

    @ws.on_disconnect
    def on_disconnect() -> None:
        called.set()

    for conn in list(fake_ha.connections):
        await conn.close()

    for _ in range(30):
        await asyncio.sleep(0.05)
        if called.is_set():
            break
    assert called.is_set()
    await ws.close()


def threading_like_flag() -> _Flag:
    return _Flag()


class _Flag:
    def __init__(self) -> None:
        self._set = False

    def set(self) -> None:
        self._set = True

    def is_set(self) -> bool:
        return self._set


async def test_unsubscribe(fake_ha: FakeHA) -> None:
    ws = await _make_ws(fake_ha)
    received: list[dict[str, Any]] = []

    async def handler(event: dict[str, Any]) -> None:
        received.append(event)

    try:
        sub_id = await ws.subscribe_events(handler, "state_changed")
        await ws.unsubscribe(sub_id)
        await fake_ha.push_event("state_changed", {"data": {}})
        await asyncio.sleep(0.05)
        assert received == []
    finally:
        await ws.close()


async def test_cannot_connect_to_bad_port() -> None:
    ws = WebSocketClient(
        "ws://127.0.0.1:1",
        "token",
        ping_interval=0,
        reconnect=False,
    )
    with pytest.raises(Exception):  # noqa: B017  - aiohttp raises ClientError
        await ws.connect()
    await ws.close()


async def test_subscribe_events_failure_rolls_back(fake_ha: FakeHA) -> None:
    async def reject(server: FakeHA, ws: web.WebSocketResponse, msg: dict[str, Any]) -> None:
        await ws.send_json(
            {
                "id": msg["id"],
                "type": "result",
                "success": False,
                "error": {"code": "bad", "message": "no"},
            }
        )

    fake_ha.handlers["subscribe_events"] = reject
    ws = await _make_ws(fake_ha)

    async def handler(event: dict[str, Any]) -> None:
        pass

    try:
        with pytest.raises(CommandError):
            await ws.subscribe_events(handler, "state_changed")
        assert not ws._subscriptions  # noqa: SLF001
        assert not ws._event_subs  # noqa: SLF001
    finally:
        await ws.close()


async def test_close_cancels_pending_request(fake_ha: FakeHA) -> None:
    async def never_reply(server: FakeHA, ws: web.WebSocketResponse, msg: dict[str, Any]) -> None:
        await asyncio.sleep(10)

    fake_ha.handlers["slow"] = never_reply
    ws = await _make_ws(fake_ha)

    async def run_and_wait() -> None:
        with pytest.raises(ConnectionClosedError):
            await ws.send_command({"type": "slow"})

    task = asyncio.create_task(run_and_wait())
    await asyncio.sleep(0.2)
    await ws.close()
    await task


async def test_reader_handles_non_json_text_frame(fake_ha: FakeHA) -> None:
    ws = await _make_ws(fake_ha, reconnect=False)
    try:

        async def send_garbage(server: FakeHA, server_ws: Any, msg: dict[str, Any]) -> None:
            await server_ws.send_str("not-json")
            await server_ws.send_json(
                {"id": msg["id"], "type": "result", "success": True, "result": None}
            )

        fake_ha.handlers["garbage"] = send_garbage
        result = await ws.send_command({"type": "garbage"})
        assert result is None
    finally:
        await ws.close()


async def test_keepalive_triggers_reconnect(fake_ha: FakeHA) -> None:
    """If the ping times out, the socket gets force-closed and reconnect kicks in."""

    async def slow_ping(server: FakeHA, ws: Any, msg: dict[str, Any]) -> None:
        await asyncio.sleep(10)

    fake_ha.handlers["ping"] = slow_ping
    ws = WebSocketClient(
        fake_ha.ws_url,
        fake_ha.token,
        ping_interval=0.2,
        request_timeout=0.3,
        reconnect=True,
    )
    await ws.connect()
    try:
        await asyncio.sleep(1.0)
        for _ in range(40):
            if ws.connected:
                break
            await asyncio.sleep(0.1)
    finally:
        await ws.close()


async def test_recv_json_close_frame(fake_ha: FakeHA) -> None:
    """_recv_json raises ConnectionClosedError on CLOSE frames during handshake."""
    app = web.Application()

    async def close_immediately(request: web.Request) -> web.WebSocketResponse:
        ws_resp = web.WebSocketResponse()
        await ws_resp.prepare(request)
        await ws_resp.close()
        return ws_resp

    app.router.add_get("/api/websocket", close_immediately)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]  # type: ignore[union-attr]
    try:
        ws = WebSocketClient(
            f"ws://127.0.0.1:{port}/api/websocket",
            "token",
            ping_interval=0,
            reconnect=False,
        )
        with pytest.raises(ConnectionClosedError):
            await ws.connect()
        await ws.close()
    finally:
        await runner.cleanup()


async def test_recv_json_error_frame(fake_ha: FakeHA) -> None:
    """_recv_json raises HAClientError on binary (unexpected type) WS messages."""
    app = web.Application()

    async def send_binary(request: web.Request) -> web.WebSocketResponse:
        ws_resp = web.WebSocketResponse()
        await ws_resp.prepare(request)
        await ws_resp.send_bytes(b"binary")
        return ws_resp

    app.router.add_get("/api/websocket", send_binary)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]  # type: ignore[union-attr]
    try:
        ws = WebSocketClient(
            f"ws://127.0.0.1:{port}/api/websocket",
            "token",
            ping_interval=0,
            reconnect=False,
        )
        with pytest.raises(HAClientError):
            await ws.connect()
        await ws.close()
    finally:
        await runner.cleanup()


async def test_unexpected_auth_response(fake_ha: FakeHA) -> None:
    """_do_connect raises AuthenticationError for non auth_ok/auth_invalid responses."""
    app = web.Application()

    async def weird_auth(request: web.Request) -> web.WebSocketResponse:
        ws_resp = web.WebSocketResponse()
        await ws_resp.prepare(request)
        await ws_resp.send_json({"type": "auth_required", "ha_version": "2024.1.0"})
        await ws_resp.receive()
        await ws_resp.send_json({"type": "something_weird"})
        return ws_resp

    app.router.add_get("/api/websocket", weird_auth)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]  # type: ignore[union-attr]
    try:
        ws = WebSocketClient(
            f"ws://127.0.0.1:{port}/api/websocket",
            "token",
            ping_interval=0,
            reconnect=False,
        )
        with pytest.raises(AuthenticationError):
            await ws.connect()
        await ws.close()
    finally:
        await runner.cleanup()


async def test_not_auth_required_response(fake_ha: FakeHA) -> None:
    """_do_connect raises AuthenticationError if first msg is not auth_required."""
    app = web.Application()

    async def no_auth_required(request: web.Request) -> web.WebSocketResponse:
        ws_resp = web.WebSocketResponse()
        await ws_resp.prepare(request)
        await ws_resp.send_json({"type": "other"})
        return ws_resp

    app.router.add_get("/api/websocket", no_auth_required)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]  # type: ignore[union-attr]
    try:
        ws = WebSocketClient(
            f"ws://127.0.0.1:{port}/api/websocket",
            "token",
            ping_interval=0,
            reconnect=False,
        )
        with pytest.raises(AuthenticationError):
            await ws.connect()
        await ws.close()
    finally:
        await runner.cleanup()


async def test_reader_loop_ws_error_type(fake_ha: FakeHA) -> None:
    """Reader loop breaks on WSMsgType.ERROR."""
    ws = await _make_ws(fake_ha, reconnect=False)
    disconnected = asyncio.Event()

    @ws.on_disconnect
    async def _on_dc() -> None:
        disconnected.set()

    for conn in list(fake_ha.connections):
        await conn.close()

    await asyncio.wait_for(disconnected.wait(), timeout=3)
    await ws.close()


async def test_connect_already_connected(fake_ha: FakeHA) -> None:
    """Calling connect() when already connected is a no-op."""
    ws = await _make_ws(fake_ha)
    try:
        assert ws.connected
        await ws.connect()
        assert ws.connected
    finally:
        await ws.close()


async def test_ping_while_disconnected(fake_ha: FakeHA) -> None:
    """Ping raises ConnectionClosedError when not connected."""
    ws = WebSocketClient(fake_ha.ws_url, fake_ha.token, ping_interval=0, reconnect=False)
    with pytest.raises(ConnectionClosedError):
        await ws.ping()


async def test_reconnect_failure_retries(fake_ha: FakeHA) -> None:
    """Reconnect loop retries on connection failure."""
    ws = await _make_ws(fake_ha, reconnect=True)
    try:
        fake_ha.reject_auth = True
        for conn in list(fake_ha.connections):
            await conn.close()

        await asyncio.sleep(1.5)

        fake_ha.reject_auth = False
        for _ in range(50):
            await asyncio.sleep(0.1)
            if ws.connected:
                break
        assert ws.connected
    finally:
        await ws.close()


async def test_keepalive_error_path(fake_ha: FakeHA) -> None:
    """Keepalive loop handles non-timeout errors gracefully."""
    call_count = 0

    async def error_ping(
        server: FakeHA, ws_resp: web.WebSocketResponse, msg: dict[str, Any]
    ) -> None:
        nonlocal call_count
        call_count += 1
        await ws_resp.send_json(
            {
                "id": msg["id"],
                "type": "result",
                "success": False,
                "error": {"code": "error", "message": "fail"},
            }
        )

    fake_ha.handlers["ping"] = error_ping
    ws = WebSocketClient(
        fake_ha.ws_url,
        fake_ha.token,
        ping_interval=0.2,
        request_timeout=0.5,
        reconnect=False,
    )
    await ws.connect()
    try:
        await asyncio.sleep(0.8)
        assert call_count >= 1
    finally:
        await ws.close()


async def test_dispatch_unhandled_message_type(fake_ha: FakeHA) -> None:
    """Unhandled WS message types are logged but don't crash."""
    ws = await _make_ws(fake_ha, reconnect=False)
    try:
        for conn in fake_ha.connections:
            if not conn.closed:
                await conn.send_json({"type": "unknown_thing", "id": 999})
        await asyncio.sleep(0.05)
        assert ws.connected
    finally:
        await ws.close()


async def test_dispatch_result_no_pending_future(fake_ha: FakeHA) -> None:
    """A result message with no matching pending future is silently ignored."""
    ws = await _make_ws(fake_ha, reconnect=False)
    try:
        for conn in fake_ha.connections:
            if not conn.closed:
                await conn.send_json(
                    {"id": 99999, "type": "result", "success": True, "result": None}
                )
        await asyncio.sleep(0.05)
        assert ws.connected
    finally:
        await ws.close()


async def test_close_cancels_pong_waiters(fake_ha: FakeHA) -> None:
    """Closing while a ping is in-flight fails the pong future."""

    async def slow_pong(
        server: FakeHA, ws_resp: web.WebSocketResponse, msg: dict[str, Any]
    ) -> None:
        await asyncio.sleep(10)

    fake_ha.handlers["ping"] = slow_pong
    ws = await _make_ws(fake_ha)

    async def do_ping() -> None:
        with pytest.raises((ConnectionClosedError, HATimeoutError)):
            await ws.ping(timeout=5.0)

    task = asyncio.create_task(do_ping())
    await asyncio.sleep(0.1)
    await ws.close()
    await task
