"""``event`` domain implementation (read-only, stateless triggers).

Home Assistant's ``event`` domain (added in 2023.8) represents stateless
trigger entities such as button presses, doorbell rings, and remote
control actions. The entity's ``state`` is an ISO-8601 timestamp of the
most recent event, while ``event_type`` (the kind of event that just
fired) and ``event_types`` (all possible event types) live in the
attributes.

This module exposes those values as typed properties and provides a
single intent-driven listener decorator, `Event.on_event`, that can be
used either bare (``@button.on_event``) or with a filter
(``@button.on_event(event_type="double_press")``).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, overload

from haclient.core.plugins import DomainSpec, register_domain
from haclient.entity.base import Entity, ValueChangeHandler


class Event(Entity):
    """A read-only Home Assistant event entity.

    Event entities represent discrete, stateless triggers (e.g. a
    button press). Each fire updates the entity's ``state`` to the new
    event timestamp and populates the ``event_type`` attribute with the
    kind of event that occurred.

    Listener callbacks registered via `on_event` receive a single
    positional argument: the ``event_type`` string of the event that
    just fired (e.g. ``"single_press"``).
    """

    domain = "event"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # Listeners keyed by event_type filter. ``None`` is the
        # catch-all bucket that receives every event.
        self._event_listeners: dict[str | None, list[Callable[[str], Any]]] = {}

    # -- State properties ---------------------------------------------

    @property
    def event_type(self) -> str | None:
        """Type of the most recent event (e.g. ``"single_press"``).

        Returns
        -------
        str or None
            The event type from the entity's attributes, or ``None`` if
            the entity has not fired yet (or the attribute is missing).
        """
        value = self.attributes.get("event_type")
        return str(value) if value is not None else None

    @property
    def event_types(self) -> list[str] | None:
        """All event types this entity is capable of firing.

        Returns
        -------
        list of str or None
            The declared event-type catalogue, or ``None`` if the
            attribute is absent.
        """
        value = self.attributes.get("event_types")
        if value is None:
            return None
        if isinstance(value, list):
            return [str(item) for item in value]
        return None

    @property
    def device_class(self) -> str | None:
        """Device class (e.g. ``"button"``, ``"doorbell"``)."""
        value = self.attributes.get("device_class")
        return str(value) if value is not None else None

    # -- Listener decorator -------------------------------------------

    @overload
    def on_event(self, func: Callable[[str], Any]) -> Callable[[str], Any]: ...

    @overload
    def on_event(
        self, *, event_type: str
    ) -> Callable[[Callable[[str], Any]], Callable[[str], Any]]: ...

    def on_event(
        self,
        func: Callable[[str], Any] | None = None,
        *,
        event_type: str | None = None,
    ) -> Any:
        """Register a listener for events fired by this entity.

        May be used either as a bare decorator to receive every event,
        or as a parameterised decorator to filter by ``event_type``.

        Parameters
        ----------
        func : callable, optional
            Sync or async callable receiving a single positional
            argument: the event-type string that just fired. Supplied
            implicitly when used as ``@entity.on_event``.
        event_type : str or None, keyword-only
            Restrict the listener to a specific event-type. When
            ``None`` (the default), the listener receives every event.

        Returns
        -------
        callable
            When called as a bare decorator, returns *func*. When called
            with ``event_type=...``, returns a decorator that registers
            and then returns the wrapped function.

        Examples
        --------
        Listen to every event::

            @button.on_event
            async def any_press(event_type):
                ...

        Filter to a specific event type::

            @button.on_event(event_type="double_press")
            async def double(event_type):
                ...
        """
        if func is not None and event_type is not None:
            raise TypeError("on_event accepts either a function or event_type, not both")

        if func is not None:
            # Bare-decorator form: @entity.on_event
            self._event_listeners.setdefault(None, []).append(func)
            return func

        # Parameterised form: @entity.on_event(event_type="...")
        def decorator(inner: Callable[[str], Any]) -> Callable[[str], Any]:
            self._event_listeners.setdefault(event_type, []).append(inner)
            return inner

        return decorator

    def remove_event_listener(self, func: Callable[[str], Any]) -> None:
        """Remove a previously registered event listener.

        Searches all registered buckets (catch-all and per-event-type)
        and removes the first match. Unknown callables are silently
        ignored.

        Parameters
        ----------
        func : callable
            The exact callable previously registered via `on_event`.
        """
        for listeners in self._event_listeners.values():
            try:
                listeners.remove(func)
                return
            except ValueError:
                continue

    # -- Dispatch -----------------------------------------------------

    def _handle_state_changed(
        self,
        old_state: dict[str, Any] | None,
        new_state: dict[str, Any] | None,
    ) -> None:
        """Apply state, then dispatch typed event listeners.

        An event "fires" whenever the state timestamp changes. The
        ``event_type`` attribute on the *new* state describes what kind
        of event occurred and is the payload delivered to listeners.
        """
        old_ts = (old_state or {}).get("state")
        new_ts = (new_state or {}).get("state")
        super()._handle_state_changed(old_state, new_state)

        if new_state is None or new_ts == old_ts:
            return
        if new_ts in (None, "unknown", "unavailable"):
            return

        new_attrs = new_state.get("attributes") or {}
        event_type_raw = new_attrs.get("event_type")
        if event_type_raw is None:
            return
        event_type = str(event_type_raw)

        # Catch-all listeners always fire.
        for listener in list(self._event_listeners.get(None, [])):
            self._dispatch_event(listener, event_type)
        # Typed listeners only fire when the event_type matches.
        for listener in list(self._event_listeners.get(event_type, [])):
            self._dispatch_event(listener, event_type)

    def _dispatch_event(self, handler: Callable[[str], Any], event_type: str) -> None:
        """Invoke an event handler with the event_type payload.

        Reuses the base class's value-dispatch path so that async
        handlers are scheduled via the registered `Clock` while sync
        ones run immediately.
        """
        # The base ``_schedule_value`` helper passes ``(old, new)`` to
        # the callback; here we only have a single payload, so we adapt
        # via a thin lambda. Errors are caught inside ``_schedule_value``.
        adapter: ValueChangeHandler = lambda _old, new: handler(new)  # noqa: E731
        self._schedule_value(adapter, None, event_type)


SPEC: DomainSpec[Event] = register_domain(DomainSpec(name="event", entity_cls=Event))
"""The `DomainSpec` registered with the shared `DomainRegistry`."""
