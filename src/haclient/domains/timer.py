"""``timer`` domain implementation.

Beyond the per-entity actions, the timer domain exposes a
collection-level ``create`` operation on the `DomainAccessor`:

    timer = await ha.timer.create(name="cooldown", duration="00:01:00")

The accessor also subscribes to the ``timer.finished`` and
``timer.cancelled`` HA events so that ``Timer.on_finished`` and
``Timer.on_cancelled`` listeners fire correctly.
"""

from __future__ import annotations

import datetime
import logging
import uuid
from typing import TYPE_CHECKING, Any

from haclient.core.plugins import DomainAccessor, DomainSpec, register_domain
from haclient.entity.base import Entity, ValueChangeHandler

if TYPE_CHECKING:
    from haclient.core.services import ServiceCaller
    from haclient.core.state import StateStore
    from haclient.ports import Clock

_LOGGER = logging.getLogger(__name__)


def _generate_timer_id() -> str:
    """Generate a short unique object-id for an ephemeral timer."""
    return f"haclient_{uuid.uuid4().hex[:8]}"


class Timer(Entity):
    """A Home Assistant timer entity.

    Timer states: ``idle``, ``active``, ``paused``.
    Actions use intent-specific names: ``start``, ``pause``, ``cancel``,
    ``finish``, ``change``.

    Obtain a proxy to an existing timer via ``ha.timer("name")``. To
    create a library-managed helper, use ``await ha.timer.create(...)``.

    Ephemeral timers (the default) are deleted automatically when they
    return to idle. Pass ``persistent=True`` to keep the helper alive.
    Timers obtained via the accessor are never auto-deleted, regardless
    of how they were originally created in HA.

    Notes
    -----
    The ``time_remaining`` property computes live seconds remaining from
    ``finishes_at`` when active, or parses ``remaining`` when paused.
    """

    domain = "timer"

    def __init__(
        self,
        entity_id: str,
        services: ServiceCaller,
        store: StateStore,
        clock: Clock,
    ) -> None:
        """Initialise the timer and its event-driven listener lists.

        Beyond the base `Entity` setup, this also primes the persistence
        flags used by the auto-cleanup logic in `_handle_state_changed`.

        Parameters
        ----------
        entity_id : str
            Fully-qualified entity id (e.g. ``"timer.cooldown"``).
        services : ServiceCaller
            Service-call port used to invoke HA services.
        store : StateStore
            State store the entity registers itself with.
        clock : Clock
            Scheduler used to dispatch async listeners.
        """
        super().__init__(entity_id, services, store, clock)
        self._finished_listeners: list[ValueChangeHandler] = []
        self._cancelled_listeners: list[ValueChangeHandler] = []
        self._ensured: bool = False
        self._persistent: bool = False
        self._created_by_us: bool = False

    @property
    def persistent(self) -> bool:
        """Whether this timer keeps its HA helper after returning to idle.

        Returns
        -------
        bool
            ``True`` for timers created via `TimerAccessor.create` with
            ``persistent=True``; ``False`` for ephemeral helpers and
            for any timer whose helper was not created by this client.
            Only meaningful for timers managed by this library — proxies
            for pre-existing HA helpers default to ``False`` but are
            never auto-deleted.
        """
        return self._persistent

    # -- State properties ---------------------------------------------

    @property
    def is_active(self) -> bool:
        """Whether the timer is currently running."""
        return self.state == "active"

    @property
    def is_paused(self) -> bool:
        """Whether the timer is paused."""
        return self.state == "paused"

    @property
    def is_idle(self) -> bool:
        """Whether the timer is idle."""
        return self.state == "idle"

    @property
    def duration(self) -> str | None:
        """Configured duration as a raw HA duration string.

        Returns
        -------
        str or None
            The HA ``duration`` attribute (e.g. ``"0:05:00"``), or
            ``None`` when not reported. The string is **not** parsed
            into a :class:`datetime.timedelta`; use `time_remaining`
            for a numeric value.
        """
        val = self.attributes.get("duration")
        return str(val) if val is not None else None

    @property
    def remaining(self) -> str | None:
        """Time remaining as a raw HA duration string.

        Returns
        -------
        str or None
            The HA ``remaining`` attribute (e.g. ``"0:04:30"``), or
            ``None`` when not reported. The string is **not** parsed
            into seconds; use `time_remaining` for a numeric value.
        """
        val = self.attributes.get("remaining")
        return str(val) if val is not None else None

    @property
    def finishes_at(self) -> str | None:
        """ISO-8601 datetime when the timer will finish.

        Returns
        -------
        str or None
            The raw HA ``finishes_at`` attribute, populated only while
            the timer is ``active``. ``None`` for idle or paused
            timers, and when the device does not report a finish time.
        """
        val = self.attributes.get("finishes_at")
        return str(val) if val is not None else None

    @property
    def time_remaining(self) -> float | None:
        """Live seconds remaining on the timer.

        Returns
        -------
        float or None
            Computed live on every access:

            * When the timer is ``active``, parses ``finishes_at`` as
              an ISO-8601 datetime and returns
              ``max(0.0, finishes_at - now_utc)``.
            * When the timer is ``paused``, parses the ``remaining``
              duration string.
            * Otherwise (``idle``, unavailable, unknown) returns
              ``None``.

            ``None`` is also returned when the underlying attribute is
            absent or malformed.

        Notes
        -----
        The value is not cached; each call may produce a slightly
        different result for active timers. No I/O is performed.
        """
        if self.state == "active":
            raw = self.attributes.get("finishes_at")
            if raw is None:
                return None
            try:
                finish_dt = datetime.datetime.fromisoformat(str(raw))
                now = datetime.datetime.now(datetime.UTC)
                delta = (finish_dt - now).total_seconds()
                return max(delta, 0.0)
            except (ValueError, TypeError):
                _LOGGER.debug("Could not parse finishes_at: %r", raw)
                return None
        if self.state == "paused":
            raw = self.attributes.get("remaining")
            if raw is None:
                return None
            return _parse_duration_to_seconds(str(raw))
        return None

    # -- Lifecycle ----------------------------------------------------

    def _handle_state_changed(
        self,
        old_state: dict[str, Any] | None,
        new_state: dict[str, Any] | None,
    ) -> None:
        """Update state, dispatch listeners, then auto-delete if ephemeral."""
        old_state_str = (old_state or {}).get("state")
        super()._handle_state_changed(old_state, new_state)

        if (
            not self._persistent
            and self._created_by_us
            and self.state == "idle"
            and old_state_str is not None
            and old_state_str != "idle"
        ):
            self._schedule_value(self._auto_cleanup, old_state_str, self.state)

    async def _auto_cleanup(self, _old: Any, _new: Any) -> None:
        """Delete the HA helper and reset internal state for re-creation."""
        try:
            await self.delete()
        except Exception:  # noqa: BLE001
            _LOGGER.debug("Auto-cleanup of %s failed", self.entity_id, exc_info=True)
        self.state = "unknown"
        self._created_by_us = False

    async def delete(self) -> None:
        """Delete the timer helper from Home Assistant.

        Sends ``timer/delete``. After deletion the entity's ``_ensured``
        flag is reset so a subsequent action will re-create the helper.
        """
        object_id = self.entity_id.split(".", 1)[1]
        await self._services.ws.send_command({"type": "timer/delete", "timer_id": object_id})
        self._ensured = False
        self._created_by_us = False

    # -- Actions ------------------------------------------------------

    async def start(self, *, duration: str | None = None) -> None:
        """Start (or restart) the timer.

        Parameters
        ----------
        duration : str or None, optional
            Optional override duration in HA format (e.g. ``"00:05:00"``).
            ``None`` keeps the helper's configured duration.
        """
        data: dict[str, Any] | None = {"duration": duration} if duration else None
        await self._call_service("start", data)

    async def pause(self) -> None:
        """Pause the timer.

        Invokes the ``timer.pause`` Home Assistant service.

        Raises
        ------
        CommandError
            If Home Assistant rejects the service call (for example,
            the timer is not currently active).
        HTTPError
            If the REST call returns a non-2xx response.
        TimeoutError
            If the call exceeds the configured request timeout.
        ConnectionClosedError
            If the WebSocket disconnects mid-call.
        """
        await self._call_service("pause")

    async def cancel(self) -> None:
        """Cancel the timer, returning it to idle.

        Invokes the ``timer.cancel`` Home Assistant service.

        Notes
        -----
        Returning to idle from a non-idle state triggers the standard
        timer state-change listeners. For ephemeral timers created via
        `TimerAccessor.create` with ``persistent=False`` (the default),
        this transition also schedules an auto-cleanup that deletes the
        HA helper, after which the entity's ``state`` is reset to
        ``"unknown"`` and the proxy can be re-ensured by the next
        action.

        Raises
        ------
        CommandError
            If Home Assistant rejects the service call.
        HTTPError
            If the REST call returns a non-2xx response.
        TimeoutError
            If the call exceeds the configured request timeout.
        ConnectionClosedError
            If the WebSocket disconnects mid-call.
        """
        await self._call_service("cancel")

    async def finish(self) -> None:
        """Finish the timer immediately.

        Invokes the ``timer.finish`` Home Assistant service. Behaves as
        if the configured duration had elapsed: a ``timer.finished``
        event fires and the timer returns to idle.

        Notes
        -----
        For ephemeral timers (see `cancel`) the transition to idle
        also schedules auto-cleanup of the HA helper.

        Raises
        ------
        CommandError
            If Home Assistant rejects the service call.
        HTTPError
            If the REST call returns a non-2xx response.
        TimeoutError
            If the call exceeds the configured request timeout.
        ConnectionClosedError
            If the WebSocket disconnects mid-call.
        """
        await self._call_service("finish")

    async def change(self, *, duration: str) -> None:
        """Add or subtract time from a running timer.

        Parameters
        ----------
        duration : str
            Signed HA duration string (e.g. ``"00:01:00"`` to add a
            minute, ``"-00:00:30"`` to subtract 30 seconds).
        """
        await self._call_service("change", {"duration": duration})

    # -- Listener decorators ------------------------------------------

    def on_start(self, func: ValueChangeHandler) -> ValueChangeHandler:
        """Register a listener for when the timer starts (becomes active).

        Parameters
        ----------
        func : callable
            Sync or async callable invoked with ``(old_state, new_state)``
            on every transition into the ``active`` state.

        Returns
        -------
        callable
            The same *func*, returned for decorator use.
        """
        return self._register_state_transition_listener("active", func)

    def on_pause(self, func: ValueChangeHandler) -> ValueChangeHandler:
        """Register a listener for when the timer is paused.

        Parameters
        ----------
        func : callable
            Sync or async callable invoked with ``(old_state, new_state)``
            on every transition into the ``paused`` state.

        Returns
        -------
        callable
            The same *func*, returned for decorator use.
        """
        return self._register_state_transition_listener("paused", func)

    def on_idle(self, func: ValueChangeHandler) -> ValueChangeHandler:
        """Register a listener for when the timer becomes idle.

        Parameters
        ----------
        func : callable
            Sync or async callable invoked with ``(old_state, new_state)``
            on every transition into the ``idle`` state.

        Returns
        -------
        callable
            The same *func*, returned for decorator use.
        """
        return self._register_state_transition_listener("idle", func)

    def on_finished(self, func: ValueChangeHandler) -> ValueChangeHandler:
        """Register a listener for natural timer expiry.

        Driven by the HA ``timer.finished`` event (not state changes).

        Parameters
        ----------
        func : callable
            Sync or async callable invoked with ``(entity_id, event_data)``
            when the timer expires.

        Returns
        -------
        callable
            The same *func*, returned for decorator use.
        """
        self._finished_listeners.append(func)
        return func

    def on_cancelled(self, func: ValueChangeHandler) -> ValueChangeHandler:
        """Register a listener for explicit timer cancellation.

        Driven by the HA ``timer.cancelled`` event (not state changes).

        Parameters
        ----------
        func : callable
            Callable invoked with ``(entity_id, event_data)`` when the
            timer is cancelled.

        Returns
        -------
        callable
            The same *func*, returned for decorator use.
        """
        self._cancelled_listeners.append(func)
        return func

    def _handle_timer_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Dispatch a ``timer.finished`` or ``timer.cancelled`` event."""
        if event_type == "timer.finished":
            listeners = self._finished_listeners
        elif event_type == "timer.cancelled":
            listeners = self._cancelled_listeners
        else:
            return
        for listener in list(listeners):
            self._schedule_value(listener, self.entity_id, data)


# -- Typed domain accessor & event handler ----------------------------


class TimerAccessor(DomainAccessor[Timer]):
    """Typed domain accessor for the ``timer`` domain.

    Returned by ``ha.timer``. Provides a statically-typed
    :meth:`create` method in addition to the standard entity lookup
    methods inherited from `DomainAccessor`.
    """

    async def create(
        self,
        *,
        name: str | None = None,
        duration: str = "00:01:00",
        persistent: bool = False,
    ) -> Timer:
        """Create a library-managed timer helper in Home Assistant.

        Sends a ``timer/create`` WebSocket command and returns a `Timer`.

        Parameters
        ----------
        name : str or None, optional
            Short object-id; auto-generated when omitted (only allowed for
            ephemeral timers).
        duration : str, optional
            Initial duration for the helper in HA format (e.g.
            ``"00:01:00"``).
        persistent : bool, optional
            If ``True``, the HA helper is **not** deleted on idle.
            Requires an explicit *name*.

        Returns
        -------
        Timer
            The newly created (or already-ensured) timer entity.

        Raises
        ------
        ValueError
            If ``persistent=True`` and *name* is ``None``.
        """
        from haclient.core.factory import EntityFactory

        if name is None:
            if persistent:
                raise ValueError("Persistent timers require an explicit name")
            name = _generate_timer_id()

        factory = self.factory
        assert isinstance(factory, EntityFactory)
        services = factory.services
        state = factory.state
        entity_id = state.registry.resolve("timer", name)
        existing = state.registry.get(entity_id)
        timer: Timer
        if existing is not None and isinstance(existing, Timer):
            timer = existing
            if timer._ensured:
                return timer
        else:
            timer = self[name]

        timer._persistent = persistent
        object_id = entity_id.split(".", 1)[1]
        await services.ws.send_command(
            {"type": "timer/create", "name": object_id, "duration": duration}
        )
        timer._ensured = True
        timer._created_by_us = True
        return timer


def _on_timer_event(entity: Entity, event_type: str, data: dict[str, Any]) -> None:
    """Per-domain event handler for ``timer.finished`` / ``timer.cancelled``.

    Routes the event to `Timer._handle_timer_event` if the entity is a
    `Timer` instance.
    """
    if isinstance(entity, Timer):
        entity._handle_timer_event(event_type, data)


SPEC: DomainSpec[Timer] = register_domain(
    DomainSpec(
        name="timer",
        entity_cls=Timer,
        event_subscriptions=("timer.finished", "timer.cancelled"),
        on_event=_on_timer_event,
        accessor_cls=TimerAccessor,
    )
)
"""The `DomainSpec` registered with the shared `DomainRegistry`."""


def _parse_duration_to_seconds(value: str) -> float | None:
    """Parse a Home Assistant duration string to total seconds.

    Supports formats like ``"0:05:00"`` and ``"00:05:00"``.

    Parameters
    ----------
    value : str
        Duration string in ``"H:MM:SS"`` or ``"HH:MM:SS"`` form. Seconds
        may include a fractional component.

    Returns
    -------
    float or None
        Total seconds, or ``None`` if parsing fails.
    """
    parts = value.split(":")
    if len(parts) != 3:  # noqa: PLR2004
        return None
    try:
        hours, minutes, seconds = int(parts[0]), int(parts[1]), float(parts[2])
    except (ValueError, TypeError):
        return None
    return hours * 3600.0 + minutes * 60.0 + seconds
