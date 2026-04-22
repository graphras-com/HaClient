"""Thin async wrapper around the Home Assistant REST API.

Only the endpoints needed by :class:`ha_client.client.HAClient` are exposed:

* ``GET  /api/``              – ping / connectivity check
* ``GET  /api/states``        – fetch all states
* ``GET  /api/states/{id}``   – fetch a single state
* ``POST /api/services/{domain}/{service}`` – invoke a service

Internally we use :mod:`aiohttp` because the WebSocket layer already depends on
it, keeping the dependency surface minimal.
"""

from __future__ import annotations

import logging
from typing import Any

import aiohttp

from .exceptions import AuthenticationError, HAClientError
from .exceptions import TimeoutError as HATimeoutError

_LOGGER = logging.getLogger(__name__)


class RestClient:
    """Async client for the Home Assistant REST API."""

    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        session: aiohttp.ClientSession | None = None,
        timeout: float = 30.0,
        verify_ssl: bool = True,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._timeout = timeout
        self._verify_ssl = verify_ssl
        self._session = session
        self._owns_session = session is None

    # ------------------------------------------------------------- lifecycle
    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
            self._owns_session = True
        return self._session

    async def close(self) -> None:
        """Close the underlying HTTP session (if we own it)."""
        if self._owns_session and self._session is not None and not self._session.closed:
            await self._session.close()

    # --------------------------------------------------------------- helpers
    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return f"{self._base_url}{path}"

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: Any | None = None,
    ) -> Any:
        session = await self._ensure_session()
        url = self._url(path)
        try:
            async with session.request(
                method,
                url,
                headers=self._headers,
                json=json,
                ssl=self._verify_ssl,
                timeout=aiohttp.ClientTimeout(total=self._timeout),
            ) as resp:
                if resp.status == 401:
                    raise AuthenticationError("Invalid or expired access token")
                if resp.status >= 400:
                    body = await resp.text()
                    raise HAClientError(f"HTTP {resp.status} from {method} {path}: {body.strip()}")
                if resp.status == 200 and resp.content_type == "application/json":
                    return await resp.json()
                return await resp.text()
        except TimeoutError as err:
            raise HATimeoutError(f"Request to {path} timed out") from err
        except aiohttp.ClientError as err:
            raise HAClientError(f"HTTP request failed: {err}") from err

    # ---------------------------------------------------------------- public
    async def ping(self) -> bool:
        """Return ``True`` if the Home Assistant API is reachable."""
        await self._request("GET", "/api/")
        return True

    async def get_states(self) -> list[dict[str, Any]]:
        """Return all entity states currently known to Home Assistant."""
        data = await self._request("GET", "/api/states")
        if not isinstance(data, list):
            raise HAClientError("Unexpected response from /api/states")
        return data

    async def get_state(self, entity_id: str) -> dict[str, Any] | None:
        """Return the state object for ``entity_id`` or ``None`` if not found."""
        try:
            data = await self._request("GET", f"/api/states/{entity_id}")
        except HAClientError as err:
            # HA returns 404 for unknown entities
            if "HTTP 404" in str(err):
                return None
            raise
        if isinstance(data, dict):
            return data
        return None

    async def call_service(
        self,
        domain: str,
        service: str,
        data: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Invoke a Home Assistant service via REST.

        Returns the list of states that were changed (if any). Home Assistant
        returns this list directly in the response body.
        """
        payload = data or {}
        result = await self._request("POST", f"/api/services/{domain}/{service}", json=payload)
        if isinstance(result, list):
            return result
        return []
