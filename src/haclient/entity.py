"""Base `Entity` implementation.

Entities are bound to an `HAClient` instance and automatically receive
state updates from WebSocket ``state_changed`` events.
"""

from __future__ import annotations

import asyncio
import contextlib
import inspect
import logging
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from .client import HAClient

_LOGGER = logging.getLogger(__name__)

StateChangeHandler = Callable[[dict[str, Any] | None, dict[str, Any] | None], Any]
ValueChangeHandler = Callable[[Any, Any], Any]
F = TypeVar("F", bound=StateChangeHandler)
V = TypeVar("V", bound=ValueChangeHandler)


class Entity:
    """Represent a single Home Assistant entity.

    Subclasses map to specific domains (``media_player``, ``light``, ...) and
    should override `domain` and add domain-specific methods.

    The `state` string and `attributes` dictionary reflect the most recent
    state known to the client. They are refreshed automatically when the
    client receives ``state_changed`` events for this entity.

    .. note::

        Users should obtain entities via the domain accessors on
        `HAClient` (e.g. ``client.light("kitchen")``) which accept a
        **short object-id** and prefix it automatically.  Direct
        construction of ``Entity`` (or its subclasses) requires a
        fully-qualified ``entity_id`` because the base class has no
        domain context of its own.

    Parameters
    ----------
    entity_id : str
        Fully-qualified entity id (e.g. ``"light.kitchen"``).
        When using domain accessors the prefix is added automatically;
        direct construction must supply the full id.
    client : HAClient
        The owning client instance.

    Attributes
    ----------
    entity_id : str
        The fully-qualified entity id.
    state : str
        Current state string (e.g. ``"on"``, ``"off"``, ``"unavailable"``).
    attributes : dict
        Current entity attributes from Home Assistant.
    """

    domain: str = ""

    def __init__(self, entity_id: str, client: HAClient) -> None:
        if "." not in entity_id:
            raise ValueError(
                f"entity_id must be fully qualified (e.g. 'light.kitchen'), got: {entity_id!r}"
            )
        self.entity_id: str = entity_id
        self._client: HAClient = client
        self.state: str = "unknown"
        self.attributes: dict[str, Any] = {}
        self._listeners: list[StateChangeHandler] = []
        self._attr_listeners: dict[str, list[ValueChangeHandler]] = {}
        self._state_transition_listeners: dict[str, list[ValueChangeHandler]] = {}
        self._state_value_listeners: list[ValueChangeHandler] = []
        client.registry.register(self)

    def _apply_state(self, state_obj: dict[str, Any] | None) -> None:
        """Apply a raw state object (as returned by Home Assistant).

        Parameters
        ----------
        state_obj : dict or None
            The state dictionary from Home Assistant, or ``None`` to mark
            the entity as unavailable.
        """
        if state_obj is None:
            self.state = "unavailable"
            self.attributes = {}
            return
        self.state = str(state_obj.get("state", "unknown"))
        attrs = state_obj.get("attributes")
        self.attributes = dict(attrs) if isinstance(attrs, dict) else {}

    def _handle_state_changed(
        self,
        old_state: dict[str, Any] | None,
        new_state: dict[str, Any] | None,
    ) -> None:
        """Update local state and dispatch listeners.

        Parameters
        ----------
        old_state : dict or None
            The previous state object.
        new_state : dict or None
            The new state object.
        """
        self._apply_state(new_state)
        for listener in list(self._listeners):
            self._schedule(listener, old_state, new_state)
        self._dispatch_granular_events(old_state, new_state)

    def _dispatch_granular_events(
        self,
        old_state: dict[str, Any] | None,
        new_state: dict[str, Any] | None,
    ) -> None:
        """Dispatch attribute-level and state-transition events.

        Parameters
        ----------
        old_state : dict or None
            The previous state object.
        new_state : dict or None
            The new state object.
        """
        old_state_str = (old_state or {}).get("state")
        new_state_str = (new_state or {}).get("state")
        old_attrs = (old_state or {}).get("attributes") or {}
        new_attrs = (new_state or {}).get("attributes") or {}

        if old_state_str != new_state_str:
            for listener in list(self._state_value_listeners):
                self._schedule_value(listener, old_state_str, new_state_str)

        if old_state_str != new_state_str and new_state_str is not None:
            for listener in list(self._state_transition_listeners.get(new_state_str, [])):
                self._schedule_value(listener, old_state_str, new_state_str)

        for attr_key, listeners in self._attr_listeners.items():
            old_val = old_attrs.get(attr_key)
            new_val = new_attrs.get(attr_key)
            if old_val != new_val:
                for listener in list(listeners):
                    self._schedule_value(listener, old_val, new_val)

    def _schedule(
        self,
        handler: StateChangeHandler,
        old_state: dict[str, Any] | None,
        new_state: dict[str, Any] | None,
    ) -> None:
        """Invoke a state-change handler, scheduling coroutines on the loop."""
        try:
            result = handler(old_state, new_state)
        except Exception:  # pragma: no cover - defensive
            _LOGGER.exception("State change handler raised synchronously")
            return
        if inspect.isawaitable(result):
            awaitable: Awaitable[Any] = result
            loop = self._client.loop
            if loop is not None and loop.is_running():
                loop.create_task(_await_and_log(awaitable))
            else:  # pragma: no cover - only reached without running loop
                asyncio.ensure_future(awaitable)

    def _schedule_value(
        self,
        handler: ValueChangeHandler,
        old_value: Any,
        new_value: Any,
    ) -> None:
        """Schedule a value-change handler with (old, new) signature."""
        try:
            result = handler(old_value, new_value)
        except Exception:
            _LOGGER.exception("Value change handler raised synchronously")
            return
        if inspect.isawaitable(result):
            awaitable: Awaitable[Any] = result
            loop = self._client.loop
            if loop is not None and loop.is_running():
                loop.create_task(_await_and_log(awaitable))
            else:  # pragma: no cover - only reached without running loop
                asyncio.ensure_future(awaitable)

    def _register_attr_listener(self, attr_key: str, func: V) -> V:
        """Register a listener for changes to a specific attribute.

        The callback receives ``(old_value, new_value)`` and is only called
        when the attribute value actually changes between events.

        Parameters
        ----------
        attr_key : str
            The attribute key to watch.
        func : callable
            Callback with signature ``(old_value, new_value)``.

        Returns
        -------
        callable
            The same *func*, for use as a decorator.
        """
        self._attr_listeners.setdefault(attr_key, []).append(func)
        return func

    def _register_state_transition_listener(self, to_state: str, func: V) -> V:
        """Register a listener for transitions *to* a specific state.

        The callback receives ``(old_state_str, new_state_str)`` and is only
        called when the entity's state string transitions to *to_state*.

        Parameters
        ----------
        to_state : str
            The target state to listen for.
        func : callable
            Callback with signature ``(old_state_str, new_state_str)``.

        Returns
        -------
        callable
            The same *func*, for use as a decorator.
        """
        self._state_transition_listeners.setdefault(to_state, []).append(func)
        return func

    def _register_state_value_listener(self, func: V) -> V:
        """Register a listener for any state string change.

        The callback receives ``(old_state_str, new_state_str)`` and fires
        whenever the state string changes (regardless of target value).

        Parameters
        ----------
        func : callable
            Callback with signature ``(old_state_str, new_state_str)``.

        Returns
        -------
        callable
            The same *func*, for use as a decorator.
        """
        self._state_value_listeners.append(func)
        return func

    def remove_granular_listener(self, func: ValueChangeHandler) -> None:
        """Remove a previously registered granular (attribute/state) listener.

        Parameters
        ----------
        func : callable
            The listener function to remove.
        """
        for listeners in self._attr_listeners.values():
            with contextlib.suppress(ValueError):
                listeners.remove(func)
                return
        for listeners in self._state_transition_listeners.values():
            with contextlib.suppress(ValueError):
                listeners.remove(func)
                return
        with contextlib.suppress(ValueError):
            self._state_value_listeners.remove(func)

    def on_state_change(self, func: F) -> F:
        """Register *func* as a listener for state changes on this entity.

        May be used as a decorator. The callback receives the previous and new
        raw state objects (``dict`` or ``None``). Coroutine functions are fully
        supported and will be scheduled on the client's event loop without
        blocking the dispatcher.

        Parameters
        ----------
        func : callable
            Callback with signature ``(old_state, new_state)``.

        Returns
        -------
        callable
            The same *func*, for use as a decorator.
        """
        self._listeners.append(func)
        return func

    def remove_listener(self, func: StateChangeHandler) -> None:
        """Remove a previously registered state change listener.

        Parameters
        ----------
        func : callable
            The listener function to remove.
        """
        with contextlib.suppress(ValueError):
            self._listeners.remove(func)

    @property
    def available(self) -> bool:
        """Return ``True`` if the entity is currently available.

        Returns
        -------
        bool
            ``True`` if the entity state is not ``"unavailable"`` or ``"unknown"``.
        """
        return self.state not in {"unavailable", "unknown"}

    async def async_refresh(self) -> None:
        """Fetch the latest state for this entity from the REST API."""
        state = await self._client.rest.get_state(self.entity_id)
        self._apply_state(state)

    async def _call_service(
        self,
        service: str,
        data: dict[str, Any] | None = None,
        *,
        domain: str | None = None,
    ) -> Any:
        """Call a Home Assistant service targeting this entity.

        The ``entity_id`` is injected automatically into the service data.
        This is a private helper -- domain subclasses should expose
        intent-specific public methods rather than raw service calls.

        Parameters
        ----------
        service : str
            Service name within the domain.
        data : dict or None, optional
            Additional service data.
        domain : str or None, optional
            Override domain (defaults to this entity's domain).

        Returns
        -------
        Any
            The result from Home Assistant.
        """
        payload: dict[str, Any] = {"entity_id": self.entity_id}
        if data:
            payload.update(data)
        return await self._client._call_service(domain or self.domain, service, payload)

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self.entity_id} state={self.state!r}>"


async def _await_and_log(awaitable: Awaitable[Any]) -> None:
    """Await ``awaitable`` and log any exception raised by the handler."""
    try:
        await awaitable
    except Exception:  # pragma: no cover - defensive
        _LOGGER.exception("Async state change handler raised")
