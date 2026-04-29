"""Async-first, high-level Home Assistant client for Python.

The two main entry points are:

* `HAClient` — the async client.
* `SyncHAClient` — a blocking wrapper suitable for scripts / REPL use.

Custom domains can be added by registering a `DomainSpec` via
`register_domain` (or by exposing an entry point under
``haclient.domains``).
"""

from __future__ import annotations

from haclient.api import HAClient
from haclient.config import ConnectionConfig, ServicePolicy
from haclient.core.connection import Connection
from haclient.core.events import EventBus
from haclient.core.factory import EntityFactory
from haclient.core.plugins import (
    DomainAccessor,
    DomainRegistry,
    DomainSpec,
    register_domain,
)
from haclient.core.registry import EntityRegistry
from haclient.core.services import ServiceCaller
from haclient.core.state import StateStore
from haclient.entity.base import Entity
from haclient.exceptions import (
    AuthenticationError,
    CommandError,
    ConnectionClosedError,
    EntityNotFoundError,
    HAClientError,
    TimeoutError,
)
from haclient.ports import Clock, RestPort, WebSocketPort
from haclient.sync import SyncHAClient

__all__ = [
    "AuthenticationError",
    "Clock",
    "CommandError",
    "Connection",
    "ConnectionClosedError",
    "ConnectionConfig",
    "DomainAccessor",
    "DomainRegistry",
    "DomainSpec",
    "Entity",
    "EntityFactory",
    "EntityNotFoundError",
    "EntityRegistry",
    "EventBus",
    "HAClient",
    "HAClientError",
    "RestPort",
    "ServiceCaller",
    "ServicePolicy",
    "StateStore",
    "SyncHAClient",
    "TimeoutError",
    "WebSocketPort",
    "register_domain",
]

__version__ = "0.2.0"
