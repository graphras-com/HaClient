"""Async-first, high-level Home Assistant client for Python.

The two main entry points are:

* `HAClient` -- the async client.
* `SyncHAClient` -- a blocking wrapper suitable for scripts / REPL use.

See the README for usage examples.
"""

from __future__ import annotations

from haclient.client import HAClient
from haclient.domains import (
    BinarySensor,
    Climate,
    Cover,
    FavoriteItem,
    Light,
    MediaPlayer,
    NowPlaying,
    Scene,
    Sensor,
    Switch,
    Timer,
)
from haclient.entity import Entity
from haclient.exceptions import (
    AuthenticationError,
    CommandError,
    ConnectionClosedError,
    EntityNotFoundError,
    HAClientError,
    TimeoutError,
)
from haclient.registry import EntityRegistry
from haclient.sync import SyncHAClient

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
    "Scene",
    "Sensor",
    "Switch",
    "SyncHAClient",
    "TimeoutError",
    "Timer",
]

__version__ = "0.1.0"
