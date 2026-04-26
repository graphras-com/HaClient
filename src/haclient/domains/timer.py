"""``timer`` domain implementation."""

from __future__ import annotations

from typing import Any

from ..entity import Entity


class Timer(Entity):
    """A Home Assistant timer entity.

    Timer states: ``idle``, ``active``, ``paused``.
    Actions use intent-specific names: ``start``, ``pause``, ``cancel``,
    ``finish``, ``change``.
    """

    domain = "timer"

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
