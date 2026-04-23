"""A minimal in-process fake of the Home Assistant HTTP + WebSocket API.

The fake is implemented with :mod:`aiohttp` so the production client exercises
its real code paths (TCP sockets, JSON framing, auth handshake, etc.) against
a deterministic server, without requiring a running Home Assistant instance.

Only the surface area actually used by :mod:`haclient` is implemented. The
fake is intentionally explicit – test cases can set ``server.handler`` to
override command behaviour or push arbitrary events.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any

from aiohttp import WSMsgType, web

CommandHandler = Callable[["FakeHA", web.WebSocketResponse, dict[str, Any]], Awaitable[None]]


class FakeHA:
    """Run an aiohttp server exposing a subset of the HA HTTP + WS API."""

    def __init__(
        self,
        *,
        token: str = "test-token",
        require_auth: bool = True,
        states: list[dict[str, Any]] | None = None,
    ) -> None:
        self.token = token
        self.require_auth = require_auth
        self.states: list[dict[str, Any]] = states or []

        self._app = web.Application()
        self._app.router.add_get("/api/", self._handle_ping)
        self._app.router.add_get("/api/states", self._handle_states)
        self._app.router.add_get("/api/states/{entity_id}", self._handle_state)
        self._app.router.add_post("/api/services/{domain}/{service}", self._handle_service)
        self._app.router.add_get("/api/websocket", self._handle_ws)
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None
        self.port: int = 0

        self.rest_service_calls: list[tuple[str, str, dict[str, Any]]] = []
        self.ws_service_calls: list[dict[str, Any]] = []
        self.connections: list[web.WebSocketResponse] = []
        self.subscriptions: dict[str, list[int]] = {}

        self.handlers: dict[str, CommandHandler] = {}

        self.reject_auth: bool = False
        self.drop_on_command: str | None = None

    async def start(self) -> str:
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, "127.0.0.1", 0)
        await self._site.start()
        server = self._site._server  # type: ignore[attr-defined]
        assert server is not None
        self.port = server.sockets[0].getsockname()[1]
        return f"http://127.0.0.1:{self.port}"

    async def stop(self) -> None:
        for ws in list(self.connections):
            if not ws.closed:
                await ws.close()
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None
            self._site = None

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    @property
    def ws_url(self) -> str:
        return f"ws://127.0.0.1:{self.port}/api/websocket"

    def _check_token(self, request: web.Request) -> web.Response | None:
        if not self.require_auth:
            return None
        header = request.headers.get("Authorization", "")
        if header != f"Bearer {self.token}":
            return web.Response(status=401, text="unauthorized")
        return None

    async def _handle_ping(self, request: web.Request) -> web.Response:
        denial = self._check_token(request)
        if denial is not None:
            return denial
        return web.json_response({"message": "API running."})

    async def _handle_states(self, request: web.Request) -> web.Response:
        denial = self._check_token(request)
        if denial is not None:
            return denial
        return web.json_response(self.states)

    async def _handle_state(self, request: web.Request) -> web.Response:
        denial = self._check_token(request)
        if denial is not None:
            return denial
        eid = request.match_info["entity_id"]
        for state in self.states:
            if state.get("entity_id") == eid:
                return web.json_response(state)
        return web.Response(status=404, text="not found")

    async def _handle_service(self, request: web.Request) -> web.Response:
        denial = self._check_token(request)
        if denial is not None:
            return denial
        domain = request.match_info["domain"]
        service = request.match_info["service"]
        try:
            payload = await request.json()
        except json.JSONDecodeError:
            payload = {}
        self.rest_service_calls.append((domain, service, payload))
        return web.json_response([])

    async def _handle_ws(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        self.connections.append(ws)
        try:
            await ws.send_json({"type": "auth_required", "ha_version": "2024.1.0"})
            msg = await ws.receive()
            if msg.type != WSMsgType.TEXT:
                await ws.close()
                return ws
            auth = json.loads(msg.data)
            if self.reject_auth or auth.get("access_token") != self.token:
                await ws.send_json({"type": "auth_invalid", "message": "invalid token"})
                await ws.close()
                return ws
            await ws.send_json({"type": "auth_ok", "ha_version": "2024.1.0"})

            async for msg in ws:
                if msg.type != WSMsgType.TEXT:
                    continue
                data = json.loads(msg.data)
                await self._dispatch(ws, data)
        finally:
            if ws in self.connections:
                self.connections.remove(ws)
        return ws

    async def _dispatch(self, ws: web.WebSocketResponse, msg: dict[str, Any]) -> None:
        mtype = msg.get("type", "")
        mid = msg.get("id")

        if self.drop_on_command == mtype:
            await ws.close()
            return

        handler = self.handlers.get(mtype)
        if handler is not None:
            await handler(self, ws, msg)
            return

        if mtype == "ping":
            await ws.send_json({"id": mid, "type": "pong"})
            return
        if mtype == "subscribe_events":
            event_type = msg.get("event_type", "*")
            assert isinstance(mid, int)
            self.subscriptions.setdefault(event_type, []).append(mid)
            await ws.send_json({"id": mid, "type": "result", "success": True, "result": None})
            return
        if mtype == "unsubscribe_events":
            sub_id = msg.get("subscription")
            for _, ids in list(self.subscriptions.items()):
                if isinstance(sub_id, int) and sub_id in ids:
                    ids.remove(sub_id)
            await ws.send_json({"id": mid, "type": "result", "success": True, "result": None})
            return
        if mtype == "call_service":
            self.ws_service_calls.append(msg)
            await ws.send_json(
                {"id": mid, "type": "result", "success": True, "result": {"context": {"id": "x"}}}
            )
            return
        if mtype == "media_player/browse_media":
            await ws.send_json({"id": mid, "type": "result", "success": True, "result": {}})
            return

        await ws.send_json(
            {
                "id": mid,
                "type": "result",
                "success": False,
                "error": {"code": "unknown_command", "message": f"Unknown type {mtype}"},
            }
        )

    async def push_event(self, event_type: str, event: dict[str, Any]) -> None:
        """Push an ``event`` to every WS currently subscribed to ``event_type``.

        Each event is wrapped in the standard ``{"type": "event", "event": ...}``
        envelope expected by :class:`haclient.websocket.WebSocketClient`.
        """
        for ws in self.connections:
            if ws.closed:
                continue
            for sub_id in self.subscriptions.get(event_type, []):
                await ws.send_json(
                    {
                        "id": sub_id,
                        "type": "event",
                        "event": {"event_type": event_type, **event},
                    }
                )
        await asyncio.sleep(0)

    async def push_state_changed(
        self,
        entity_id: str,
        new_state: dict[str, Any] | None,
        old_state: dict[str, Any] | None = None,
    ) -> None:
        """Convenience helper for pushing a ``state_changed`` event."""
        await self.push_event(
            "state_changed",
            {
                "data": {
                    "entity_id": entity_id,
                    "old_state": old_state,
                    "new_state": new_state,
                }
            },
        )
