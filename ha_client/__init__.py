"""Async-first, high-level Home Assistant client for Python.

The two main entry points are:

* :class:`HAClient` – the async client.
* :class:`SyncHAClient` – a blocking wrapper suitable for scripts / REPL use.

See the README for usage examples.
"""

from __future__ import annotations

from .client import HAClient
from .domains import (
    BinarySensor,
    Climate,
    Cover,
    FavoriteItem,
    Light,
    MediaPlayer,
    NowPlaying,
    Sensor,
    Switch,
)
from .entity import Entity
from .exceptions import (
    AuthenticationError,
    CommandError,
    ConnectionClosedError,
    EntityNotFoundError,
    HAClientError,
    TimeoutError,
    UnsupportedOperationError,
)
from .registry import EntityRegistry
from .sync import SyncHAClient

__all__ = [
    "AuthenticationError",
    "BinarySensor",
    "Climate",
    "CommandError",
    "ConnectionClosedError",
    "Cover",
    "Entity",
    "EntityNotFoundError",
    "EntityRegistry",
    "FavoriteItem",
    "HAClient",
    "HAClientError",
    "Light",
    "MediaPlayer",
    "NowPlaying",
    "Sensor",
    "Switch",
    "SyncHAClient",
    "TimeoutError",
    "UnsupportedOperationError",
]

__version__ = "0.1.0"
