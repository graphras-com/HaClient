"""``timer`` domain implementation."""

from __future__ import annotations

import datetime
import logging
from typing import Any

from ..entity import Entity, ValueChangeHandler

_LOGGER = logging.getLogger(__name__)


class Timer(Entity):
    """A Home Assistant timer entity.

    Timer states: ``idle``, ``active``, ``paused``.
    Actions use intent-specific names: ``start``, ``pause``, ``cancel``,
    ``finish``, ``change``.

    In addition to the generic ``on_idle`` listener (which fires for both
    natural expiry and explicit cancellation), the timer provides
    ``on_finished`` and ``on_cancelled`` listeners that fire only for the
    corresponding reason.  These are driven by Home Assistant's dedicated
    ``timer.finished`` and ``timer.cancelled`` event types.

    The ``time_remaining`` property computes the live seconds remaining
    from ``finishes_at`` when the timer is active, or parses the
    ``remaining`` attribute when paused.
    """

    domain = "timer"

    def __init__(self, entity_id: str, client: Any) -> None:
        super().__init__(entity_id, client)
        self._finished_listeners: list[ValueChangeHandler] = []
        self._cancelled_listeners: list[ValueChangeHandler] = []

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

    # -- Actions --

    async def start(self, *, duration: str | None = None) -> None:
        """Start (or restart) the timer.

        Parameters
        ----------
        duration : str or None, optional
            Override duration (e.g. ``"00:05:00"``).
        """
        data: dict[str, Any] | None = {"duration": duration} if duration else None
        await self._call_service("start", data)

    async def pause(self) -> None:
        """Pause the timer."""
        await self._call_service("pause")

    async def cancel(self) -> None:
        """Cancel the timer (returns to idle)."""
        await self._call_service("cancel")

    async def finish(self) -> None:
        """Finish the timer immediately."""
        await self._call_service("finish")

    async def change(self, *, duration: str) -> None:
        """Add or subtract time from a running timer.

        Parameters
        ----------
        duration : str
            Duration to add/subtract (e.g. ``"00:01:00"`` or ``"-00:00:30"``).
        """
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
