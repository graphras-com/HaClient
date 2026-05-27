"""Exception hierarchy for the Home Assistant client.

All library-specific exceptions derive from `HAClientError` so callers
can catch a single base type if they do not care about the specific failure.
"""

from __future__ import annotations


class HAClientError(Exception):
    """Base class for all exceptions raised by ``haclient``."""


class AuthenticationError(HAClientError):
    """Raised when authentication with Home Assistant fails."""


class ConnectionClosedError(HAClientError):
    """Raised when the WebSocket connection is unexpectedly closed."""


class CommandError(HAClientError):
    """Raised when Home Assistant returns an error for a WebSocket command.

    Attributes
    ----------
    code : str
        The error code from Home Assistant.
    message : str
        The human-readable error message.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


class HTTPError(HAClientError):
    """Raised when Home Assistant returns an HTTP error response.

    Parameters
    ----------
    status : int
        The HTTP status code (e.g. 404, 500).
    method : str
        The HTTP method used (e.g. ``"GET"``).
    path : str
        The relative API path that was requested.
    body : str
        The response body text.

    Attributes
    ----------
    status : int
        The HTTP status code.
    method : str
        The HTTP method.
    path : str
        The relative API path.
    body : str
        The response body text.

    Examples
    --------
    >>> raise HTTPError(404, "GET", "/api/states/light.missing", "not found")
    """

    def __init__(self, status: int, method: str, path: str, body: str) -> None:
        super().__init__(f"HTTP {status} from {method} {path}: {body.strip()}")
        self.status = status
        self.method = method
        self.path = path
        self.body = body


class TimeoutError(HAClientError):  # noqa: A001
    """Raised when a request to Home Assistant does not complete in time."""


class EntityNotFoundError(HAClientError):
    """Raised when a requested entity cannot be resolved."""
