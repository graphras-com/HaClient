"""Configuration objects for `HAClient`.

The connection settings, URL handling, and aiohttp session ownership are
captured in `ConnectionConfig`. This isolates configuration parsing from
the rest of the package and keeps `HAClient.__init__` boring.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlparse, urlunparse

import aiohttp

ServicePolicy = Literal["ws", "rest", "auto"]
"""How `ServiceCaller` should choose between WebSocket and REST.

* ``"ws"``   — always use the WebSocket. Fails if the WS is not connected.
* ``"rest"`` — always use REST.
* ``"auto"`` — prefer WebSocket when connected, otherwise fall back to REST.
"""


def derive_ws_url(base_url: str) -> str:
    """Derive the Home Assistant WebSocket URL from a base HTTP URL.

    Parameters
    ----------
    base_url : str
        Base URL such as ``http://homeassistant.local:8123`` (with or
        without a trailing slash, optionally with a path prefix).

    Returns
    -------
    str
        The fully-qualified WebSocket URL ending with ``/api/websocket``.
    """
    parsed = urlparse(base_url)
    scheme_map = {"http": "ws", "https": "wss", "ws": "ws", "wss": "wss"}
    scheme = scheme_map.get(parsed.scheme, "ws")
    path = parsed.path.rstrip("/") + "/api/websocket"
    return urlunparse((scheme, parsed.netloc, path, "", "", ""))


@dataclass(frozen=True)
class ConnectionConfig:
    """Immutable bundle of settings consumed by infrastructure adapters.

    Attributes
    ----------
    base_url : str
        Home Assistant base URL (without trailing slash).
    token : str
        Long-lived access token.
    ws_url : str
        Fully-qualified WebSocket URL.
    reconnect : bool
        Whether the WebSocket should reconnect automatically.
    ping_interval : float
        Seconds between WebSocket keepalive pings (``0`` disables them).
    request_timeout : float
        Default timeout for individual REST and WS requests.
    verify_ssl : bool
        Verify TLS certificates.
    service_policy : ServicePolicy
        Default routing policy used by `ServiceCaller`.
    """

    base_url: str
    token: str
    ws_url: str
    reconnect: bool = True
    ping_interval: float = 30.0
    request_timeout: float = 30.0
    verify_ssl: bool = True
    service_policy: ServicePolicy = "auto"

    @classmethod
    def from_url(
        cls,
        base_url: str,
        token: str,
        *,
        ws_url: str | None = None,
        reconnect: bool = True,
        ping_interval: float = 30.0,
        request_timeout: float = 30.0,
        verify_ssl: bool = True,
        service_policy: ServicePolicy = "auto",
    ) -> ConnectionConfig:
        """Build a `ConnectionConfig` from a base URL.

        Parameters
        ----------
        base_url : str
            Home Assistant base URL (e.g. ``http://localhost:8123``).
        token : str
            Long-lived access token.
        ws_url : str or None, optional
            Explicit WebSocket URL. Derived from *base_url* when omitted.
        reconnect : bool, optional
            Whether the WebSocket should reconnect automatically.
        ping_interval : float, optional
            Seconds between keepalive pings.
        request_timeout : float, optional
            Default timeout for WebSocket / REST operations.
        verify_ssl : bool, optional
            Verify TLS certificates.
        service_policy : ServicePolicy, optional
            How service calls choose between WebSocket and REST.

        Returns
        -------
        ConnectionConfig
            The fully-resolved configuration object.
        """
        normalised = base_url.rstrip("/")
        return cls(
            base_url=normalised,
            token=token,
            ws_url=ws_url or derive_ws_url(normalised),
            reconnect=reconnect,
            ping_interval=ping_interval,
            request_timeout=request_timeout,
            verify_ssl=verify_ssl,
            service_policy=service_policy,
        )


class SharedSession:
    """Holder for an optional shared `aiohttp.ClientSession`.

    Both REST and WebSocket adapters can use the same session instance,
    which is the recommended pattern for users who already manage their
    own ``aiohttp.ClientSession``. When no session is provided here, each
    adapter creates and owns its own.
    """

    def __init__(self, session: aiohttp.ClientSession | None = None) -> None:
        """Wrap *session* and record whether it was externally owned.

        Parameters
        ----------
        session : aiohttp.ClientSession or None, optional
            Pre-existing session to share between transports. ``None``
            leaves each adapter to manage its own session.
        """
        self.session = session
        self.shared = session is not None
