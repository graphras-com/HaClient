"""A minimal in-process fake of the Home Assistant HTTP + WebSocket API.

The fake is implemented with ``aiohttp`` so the production client exercises
its real code paths (TCP sockets, JSON framing, auth handshake, etc.) against
a deterministic server, without requiring a running Home Assistant instance.

Only the surface area actually used by ``haclient`` is implemented. The
fake is intentionally explicit -- test cases can set ``server.handler`` to
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
    """Run an aiohttp server exposing a subset of the HA HTTP + WS API.

    The server binds to ``127.0.0.1`` on a free OS-assigned port. Tests
    interact with it as a black box via `base_url` / `ws_url` and may
    customise behaviour by mutating the public attributes below.

    Attributes
    ----------
    token : str
        Bearer token accepted on REST requests and the WS auth
        handshake.
    require_auth : bool
        When ``False``, REST endpoints skip the token check.
    states : list of dict
        State dicts returned by ``GET /api/states`` and
        ``GET /api/states/<entity_id>``. Tests may mutate this list at
        any time.
    handlers : dict
        Optional per-command-type overrides. When set, the handler is
        invoked instead of the built-in dispatch logic.
    rest_service_calls : list of tuple
        Recorded ``(domain, service, payload)`` triples for every
        ``POST /api/services/...`` call.
    ws_service_calls : list of dict
        Recorded payloads for every ``call_service`` WS command.
    subscriptions : dict
        Map of event type to subscription ids per current connection.
    reject_auth : bool
        When ``True``, the WS auth handshake responds with
        ``auth_invalid`` regardless of the supplied token.
    drop_on_command : str or None
        When set, the WS connection is closed without responding the
        first time a command of this ``type`` arrives. Useful to
        simulate mid-flight disconnects.
    port : int
        Bound TCP port (set by `start`).
    """

    def __init__(
        self,
        *,
        token: str = "test-token",
        require_auth: bool = True,
        states: list[dict[str, Any]] | None = None,
    ) -> None:
        """Initialise the fake server.

        Parameters
        ----------
        token : str, optional
            Bearer token accepted by the server.
        require_auth : bool, optional
            When ``False``, REST endpoints skip the token check.
        states : list of dict or None, optional
            Initial state objects returned by the ``/api/states``
            endpoints.
        """
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
        """Bind to a free port and start serving.

        Returns
        -------
        str
            The base URL (``http://127.0.0.1:<port>``).
        """
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, "127.0.0.1", 0)
        await self._site.start()
        server = self._site._server  # type: ignore[attr-defined]
        assert server is not None
        self.port = server.sockets[0].getsockname()[1]
        return f"http://127.0.0.1:{self.port}"

    async def stop(self) -> None:
        """Close all open WS connections and shut down the HTTP runner."""
        for ws in list(self.connections):
            if not ws.closed:
                await ws.close()
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None
            self._site = None

    @property
    def base_url(self) -> str:
        """Return the bound HTTP base URL."""
        return f"http://127.0.0.1:{self.port}"

    @property
    def ws_url(self) -> str:
        """Return the bound WebSocket URL."""
        return f"ws://127.0.0.1:{self.port}/api/websocket"

    def _check_token(self, request: web.Request) -> web.Response | None:
        """Validate the bearer token on a REST request.

        Returns
        -------
        web.Response or None
            A 401 response when the token is missing or wrong; ``None``
            when the request is authorised (or auth is disabled).
        """
        if not self.require_auth:
            return None
        header = request.headers.get("Authorization", "")
        if header != f"Bearer {self.token}":
            return web.Response(status=401, text="unauthorized")
        return None

    async def _handle_ping(self, request: web.Request) -> web.Response:
        """Handle ``GET /api/`` (the HA reachability probe)."""
        denial = self._check_token(request)
        if denial is not None:
            return denial
        return web.json_response({"message": "API running."})

    async def _handle_states(self, request: web.Request) -> web.Response:
        """Handle ``GET /api/states`` by returning every known state."""
        denial = self._check_token(request)
        if denial is not None:
            return denial
        return web.json_response(self.states)

    async def _handle_state(self, request: web.Request) -> web.Response:
        """Handle ``GET /api/states/<entity_id>``.

        Returns 404 when the entity is not in `states`.
        """
        denial = self._check_token(request)
        if denial is not None:
            return denial
        eid = request.match_info["entity_id"]
        for state in self.states:
            if state.get("entity_id") == eid:
                return web.json_response(state)
        return web.Response(status=404, text="not found")

    async def _handle_service(self, request: web.Request) -> web.Response:
        """Handle ``POST /api/services/<domain>/<service>``.

        Records the call into `rest_service_calls` and returns an empty
        list, matching HA's "no states changed" response shape.
        """
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
        """Drive the full WebSocket lifecycle for a single connection.

        Performs the HA auth handshake (``auth_required`` →
        ``auth_invalid``/``auth_ok``) and then dispatches every
        subsequent text frame through `_dispatch` until the peer closes.
        """
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
        """Route an incoming WS command to the appropriate handler.

        Resolution order:

        1. If `drop_on_command` matches, close the socket and return.
        2. If a per-type handler is registered in `handlers`, invoke it.
        3. Otherwise, fall through to the built-in handlers for the
           commands actually exercised by the test suite (``ping``,
           ``subscribe_events``, ``unsubscribe_events``, ``call_service``,
           ``media_player/browse_media``, ``timer/create``,
           ``timer/delete``).
        4. Unknown command types receive an ``unknown_command`` error
           response.

        Parameters
        ----------
        ws : web.WebSocketResponse
            The connection to reply on.
        msg : dict
            The decoded command frame.
        """
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
        if mtype == "timer/create":
            name = msg.get("name", "")
            duration = msg.get("duration", "00:01:00")
            await ws.send_json(
                {
                    "id": mid,
                    "type": "result",
                    "success": True,
                    "result": {
                        "id": name,
                        "name": name,
                        "duration": duration,
                        "restore": False,
                    },
                }
            )
            return
        if mtype == "timer/delete":
            await ws.send_json(
                {
                    "id": mid,
                    "type": "result",
                    "success": True,
                    "result": None,
                }
            )
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
        """Push an event to every WS currently subscribed to *event_type*.

        Each event is wrapped in the standard ``{"type": "event", "event": ...}``
        envelope expected by `WebSocketClient`.

        Parameters
        ----------
        event_type : str
            The event type string (e.g. ``"state_changed"``).
        event : dict
            The event payload.
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
        """Push a ``state_changed`` event.

        Parameters
        ----------
        entity_id : str
            The entity whose state changed.
        new_state : dict or None
            The new state object.
        old_state : dict or None, optional
            The previous state object.
        """
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
