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


class TimeoutError(HAClientError):  # noqa: A001
    """Raised when a request to Home Assistant does not complete in time."""


class EntityNotFoundError(HAClientError):
    """Raised when a requested entity cannot be resolved."""
