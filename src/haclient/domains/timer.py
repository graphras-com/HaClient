"""``timer`` domain implementation."""

from __future__ import annotations

import datetime
import logging
import uuid
from typing import Any

from ..entity import Entity, ValueChangeHandler

_LOGGER = logging.getLogger(__name__)


def _generate_timer_id() -> str:
    """Generate a short unique object-id for an ephemeral timer.

    Returns
    -------
    str
        A string like ``"haclient_a1b2c3d4"``.
    """
    return f"haclient_{uuid.uuid4().hex[:8]}"


class Timer(Entity):
    """A Home Assistant timer entity.

    Timer states: ``idle``, ``active``, ``paused``.
    Actions use intent-specific names: ``start``, ``pause``, ``cancel``,
    ``finish``, ``change``.

    Timers are **ephemeral by default**: the HA helper is created
    automatically on the first action and deleted when the timer returns
    to idle (natural finish or cancellation).  The same ``Timer`` object
    can be restarted afterwards — the helper is transparently re-created.

    Pass ``persistent=True`` to keep the HA helper alive after the timer
    finishes.  Persistent timers require an explicit *name*; ephemeral
    timers auto-generate one when no name is provided.

    Timers that already exist in Home Assistant (e.g. created via the UI)
    are never auto-deleted, regardless of the ``persistent`` flag.  Only
    helpers created by the library are eligible for auto-cleanup.

    In addition to the generic ``on_idle`` listener (which fires for both
    natural expiry and explicit cancellation), the timer provides
    ``on_finished`` and ``on_cancelled`` listeners that fire only for the
    corresponding reason.  These are driven by Home Assistant's dedicated
    ``timer.finished`` and ``timer.cancelled`` event types.

    The ``time_remaining`` property computes the live seconds remaining
    from ``finishes_at`` when the timer is active, or parses the
    ``remaining`` attribute when paused.

    Parameters
    ----------
    entity_id : str
        Fully-qualified entity id (e.g. ``"timer.my_timer"``).
    client : HAClient
        The owning client instance.
    persistent : bool, optional
        If ``False`` (default), the HA helper is deleted automatically
        when the timer returns to idle.
    """

    domain = "timer"

    def __init__(self, entity_id: str, client: Any, *, persistent: bool = False) -> None:
        super().__init__(entity_id, client)
        self._finished_listeners: list[ValueChangeHandler] = []
        self._cancelled_listeners: list[ValueChangeHandler] = []
        self._ensured: bool = False
        self._persistent: bool = persistent
        self._created_by_us: bool = False

    @property
    def persistent(self) -> bool:
        """Whether this timer keeps its HA helper after returning to idle.

        Returns
        -------
        bool
            ``True`` if the timer is persistent.
        """
        return self._persistent

    # -- State properties --

    @property
    def is_active(self) -> bool:
        """Check whether the timer is currently running.

        Returns
        -------
        bool
            ``True`` if the timer is active.
        """
        return self.state == "active"

    @property
    def is_paused(self) -> bool:
        """Check whether the timer is paused.

        Returns
        -------
        bool
            ``True`` if paused.
        """
        return self.state == "paused"

    @property
    def is_idle(self) -> bool:
        """Check whether the timer is idle (not started or finished).

        Returns
        -------
        bool
            ``True`` if idle.
        """
        return self.state == "idle"

    @property
    def duration(self) -> str | None:
        """Configured duration (e.g. ``"0:05:00"``).

        Returns
        -------
        str or None
            The duration string.
        """
        val = self.attributes.get("duration")
        return str(val) if val is not None else None

    @property
    def remaining(self) -> str | None:
        """Time remaining (e.g. ``"0:04:30"``).

        Returns
        -------
        str or None
            The remaining time string.
        """
        val = self.attributes.get("remaining")
        return str(val) if val is not None else None

    @property
    def finishes_at(self) -> str | None:
        """ISO-8601 datetime when the timer will finish, if active.

        Returns
        -------
        str or None
            The finish datetime string.
        """
        val = self.attributes.get("finishes_at")
        return str(val) if val is not None else None

    @property
    def time_remaining(self) -> float | None:
        """Compute live seconds remaining on the timer.

        When the timer is **active**, this calculates the difference between
        ``finishes_at`` and the current UTC time.  When **paused**, it parses
        the ``remaining`` attribute.  Returns ``None`` when idle or when the
        required attributes are missing.

        Returns
        -------
        float or None
            Seconds remaining (clamped to ``>= 0``), or ``None`` if not
            applicable.
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

    # -- Lifecycle --

    def _handle_state_changed(
        self,
        old_state: dict[str, Any] | None,
        new_state: dict[str, Any] | None,
    ) -> None:
        """Update state, dispatch listeners, then auto-delete if ephemeral.

        For non-persistent timers **that were created by the library**, the
        HA helper is deleted when the timer transitions to ``idle``.  Timers
        that already existed in Home Assistant (e.g. created via the UI) are
        never auto-deleted, even when ``persistent`` is ``False``.

        The cleanup runs *after* all user listeners have been dispatched so
        that callbacks see the final state.

        Parameters
        ----------
        old_state : dict or None
            The previous state object.
        new_state : dict or None
            The new state object.
        """
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
        """Delete the HA helper and reset internal state for re-creation.

        This is scheduled as a task after user listeners have been invoked.
        """
        try:
            await self.delete()
        except Exception:  # noqa: BLE001
            _LOGGER.debug("Auto-cleanup of %s failed", self.entity_id, exc_info=True)
        self.state = "unknown"
        self._created_by_us = False

    async def _ensure_exists(self) -> None:
        """Create the timer helper in Home Assistant if it does not exist.

        Uses the ``timer/create`` WebSocket command.  The call is idempotent:
        once the helper has been confirmed (either via the initial state fetch
        or a prior ``_ensure_exists`` call), subsequent invocations are no-ops.

        The object-id is extracted from the ``entity_id`` (the part after
        ``timer.``).
        """
        if self._ensured or self.state != "unknown":
            return
        object_id = self.entity_id.split(".", 1)[1]
        await self._client.ws.send_command(
            {
                "type": "timer/create",
                "name": object_id,
                "duration": "00:01:00",
            }
        )
        self._ensured = True
        self._created_by_us = True

    async def delete(self) -> None:
        """Delete the timer helper from Home Assistant.

        Uses the ``timer/delete`` WebSocket command.  After deletion the
        entity's ``_ensured`` flag is reset so that a subsequent action
        will re-create the helper.

        Raises
        ------
        CommandError
            If the timer does not exist in Home Assistant.
        """
        object_id = self.entity_id.split(".", 1)[1]
        await self._client.ws.send_command(
            {
                "type": "timer/delete",
                "timer_id": object_id,
            }
        )
        self._ensured = False
        self._created_by_us = False

    # -- Actions --

    async def start(self, *, duration: str | None = None) -> None:
        """Start (or restart) the timer.

        Parameters
        ----------
        duration : str or None, optional
            Override duration (e.g. ``"00:05:00"``).
        """
        await self._ensure_exists()
        data: dict[str, Any] | None = {"duration": duration} if duration else None
        await self._call_service("start", data)

    async def pause(self) -> None:
        """Pause the timer."""
        await self._ensure_exists()
        await self._call_service("pause")

    async def cancel(self) -> None:
        """Cancel the timer (returns to idle)."""
        await self._ensure_exists()
        await self._call_service("cancel")

    async def finish(self) -> None:
        """Finish the timer immediately."""
        await self._ensure_exists()
        await self._call_service("finish")

    async def change(self, *, duration: str) -> None:
        """Add or subtract time from a running timer.

        Parameters
        ----------
        duration : str
            Duration to add/subtract (e.g. ``"00:01:00"`` or ``"-00:00:30"``).
        """
        await self._ensure_exists()
        await self._call_service("change", {"duration": duration})

    # -- Listener decorators --

    def on_start(self, func: Any) -> Any:
        """Register a listener for when the timer starts (becomes active).

        Parameters
        ----------
        func : callable
            Callback with signature ``(old_state, new_state)``.

        Returns
        -------
        callable
            The same *func*, for use as a decorator.
        """
        return self._register_state_transition_listener("active", func)

    def on_pause(self, func: Any) -> Any:
        """Register a listener for when the timer is paused.

        Parameters
        ----------
        func : callable
            Callback with signature ``(old_state, new_state)``.

        Returns
        -------
        callable
            The same *func*, for use as a decorator.
        """
        return self._register_state_transition_listener("paused", func)

    def on_idle(self, func: Any) -> Any:
        """Register a listener for when the timer becomes idle (finished or cancelled).

        Parameters
        ----------
        func : callable
            Callback with signature ``(old_state, new_state)``.

        Returns
        -------
        callable
            The same *func*, for use as a decorator.
        """
        return self._register_state_transition_listener("idle", func)

    def on_finished(self, func: Any) -> Any:
        """Register a listener for when the timer finishes naturally.

        Unlike ``on_idle``, this fires **only** when the timer expires or
        is finished explicitly -- not when it is cancelled.  Driven by the
        Home Assistant ``timer.finished`` event.

        Parameters
        ----------
        func : callable
            Callback with signature ``(entity_id: str, event_data: dict)``.

        Returns
        -------
        callable
            The same *func*, for use as a decorator.
        """
        self._finished_listeners.append(func)
        return func

    def on_cancelled(self, func: Any) -> Any:
        """Register a listener for when the timer is cancelled.

        Unlike ``on_idle``, this fires **only** on cancellation -- not on
        natural expiry.  Driven by the Home Assistant ``timer.cancelled``
        event.

        Parameters
        ----------
        func : callable
            Callback with signature ``(entity_id: str, event_data: dict)``.

        Returns
        -------
        callable
            The same *func*, for use as a decorator.
        """
        self._cancelled_listeners.append(func)
        return func

    def _handle_timer_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Dispatch a ``timer.finished`` or ``timer.cancelled`` event.

        Called by `HAClient` when a matching timer event arrives for this
        entity.

        Parameters
        ----------
        event_type : str
            Either ``"timer.finished"`` or ``"timer.cancelled"``.
        data : dict
            The event data payload from Home Assistant.
        """
        if event_type == "timer.finished":
            listeners = self._finished_listeners
        elif event_type == "timer.cancelled":
            listeners = self._cancelled_listeners
        else:
            return
        for listener in list(listeners):
            self._schedule_value(listener, self.entity_id, data)


def _parse_duration_to_seconds(value: str) -> float | None:
    """Parse a Home Assistant duration string to total seconds.

    Supports formats like ``"0:05:00"`` and ``"00:05:00"``.

    Parameters
    ----------
    value : str
        Duration string in ``H:MM:SS`` or ``HH:MM:SS`` format.

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
