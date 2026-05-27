"""aiohttp-based implementation of `RestPort`.

Only the endpoints actually used by the core are exposed. The adapter
optionally accepts an externally-owned `aiohttp.ClientSession`; when no
session is provided one is created and managed internally.
"""

from __future__ import annotations

import logging
from typing import Any

import aiohttp

from haclient.exceptions import AuthenticationError, HAClientError, HTTPError
from haclient.exceptions import TimeoutError as HATimeoutError

_LOGGER = logging.getLogger(__name__)


class AiohttpRestAdapter:
    """Async REST client backed by ``aiohttp``.

    Parameters
    ----------
    base_url : str
        Home Assistant base URL (without trailing slash).
    token : str
        Long-lived access token.
    session : aiohttp.ClientSession or None, optional
        Externally-owned session to reuse. When ``None`` the adapter
        creates its own session and closes it on `close`.
    timeout : float, optional
        Request timeout in seconds.
    verify_ssl : bool, optional
        Verify TLS certificates.
    """

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

    @property
    def base_url(self) -> str:
        """Return the configured base URL."""
        return self._base_url

    async def _ensure_session(self) -> aiohttp.ClientSession:
        """Return the current session, creating one if necessary."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
            self._owns_session = True
        return self._session

    async def close(self) -> None:
        """Close the underlying HTTP session if we own it."""
        if self._owns_session and self._session is not None and not self._session.closed:
            await self._session.close()

    @property
    def _headers(self) -> dict[str, str]:
        """Return authorization and content-type headers."""
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    def _url(self, path: str) -> str:
        """Build a full URL from a relative API path."""
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
        """Perform an HTTP request and return the parsed response.

        Parameters
        ----------
        method : str
            HTTP method (e.g. ``"GET"``).
        path : str
            Relative API path.
        json : Any or None, optional
            JSON-serialisable body.

        Returns
        -------
        Any
            Parsed JSON response, or raw text for non-JSON responses.

        Raises
        ------
        AuthenticationError
            On HTTP 401.
        HTTPError
            On any other HTTP error (status >= 400).
        HAClientError
            On connection failure.
        TimeoutError
            On request timeout.
        """
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
                    raise HTTPError(resp.status, method, path, body)
                if resp.status == 200 and resp.content_type == "application/json":
                    return await resp.json()
                return await resp.text()
        except TimeoutError as err:
            raise HATimeoutError(f"Request to {path} timed out") from err
        except aiohttp.ClientError as err:
            raise HAClientError(f"HTTP request failed: {err}") from err

    async def ping(self) -> bool:
        """Verify Home Assistant is reachable.

        Returns
        -------
        bool
            ``True`` if the ``/api/`` endpoint responded successfully.
            Failures surface as exceptions from `_request`; this method
            never returns ``False``.
        """
        await self._request("GET", "/api/")
        return True

    async def get_states(self) -> list[dict[str, Any]]:
        """Return all entity states currently known to Home Assistant.

        Returns
        -------
        list of dict
            The state objects.

        Raises
        ------
        HAClientError
            If the response is not a list.
        """
        data = await self._request("GET", "/api/states")
        if not isinstance(data, list):
            raise HAClientError("Unexpected response from /api/states")
        return data

    async def get_state(self, entity_id: str) -> dict[str, Any] | None:
        """Return the state object for *entity_id*, or ``None`` if missing.

        Parameters
        ----------
        entity_id : str
            Fully-qualified entity id.

        Returns
        -------
        dict or None
            The state object, or ``None`` on HTTP 404.

        Raises
        ------
        HTTPError
            On any HTTP error other than 404.
        AuthenticationError
            On HTTP 401.
        """
        try:
            data = await self._request("GET", f"/api/states/{entity_id}")
        except HTTPError as err:
            if err.status == 404:
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
        """Invoke a service via REST.

        Parameters
        ----------
        domain : str
            The service domain.
        service : str
            The service name.
        data : dict or None, optional
            Service data payload.

        Returns
        -------
        list of dict
            The list of states changed by the service call.
        """
        payload = data or {}
        result = await self._request("POST", f"/api/services/{domain}/{service}", json=payload)
        if isinstance(result, list):
            return result
        return []
