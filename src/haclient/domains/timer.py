"""``timer`` domain implementation."""

from __future__ import annotations

from typing import Any

from ..entity import Entity


class Timer(Entity):
    """A Home Assistant timer entity.

    Timer states: ``idle``, ``active``, ``paused``.
    """

    domain = "timer"

    # -- State properties --

    @property
    def is_active(self) -> bool:
        """``True`` if the timer is currently running."""
        return self.state == "active"

    @property
    def is_paused(self) -> bool:
        """``True`` if the timer is paused."""
        return self.state == "paused"

    @property
    def is_idle(self) -> bool:
        """``True`` if the timer is idle (not started or finished)."""
        return self.state == "idle"

    @property
    def duration(self) -> str | None:
        """Configured duration (e.g. ``"0:05:00"``)."""
        val = self.attributes.get("duration")
        return str(val) if val is not None else None

    @property
    def remaining(self) -> str | None:
        """Time remaining (e.g. ``"0:04:30"``)."""
        val = self.attributes.get("remaining")
        return str(val) if val is not None else None

    @property
    def finishes_at(self) -> str | None:
        """ISO-8601 datetime when the timer will finish, if active."""
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
        await self.call_service("start", data)

    async def pause(self) -> None:
        """Pause the timer."""
        await self.call_service("pause")

    async def cancel(self) -> None:
        """Cancel the timer (returns to idle)."""
        await self.call_service("cancel")

    async def finish(self) -> None:
        """Finish the timer immediately."""
        await self.call_service("finish")

    async def change(self, *, duration: str) -> None:
        """Add or subtract time from a running timer.

        Parameters
        ----------
        duration : str
            Duration to add/subtract (e.g. ``"00:01:00"`` or ``"-00:00:30"``).
        """
        await self.call_service("change", {"duration": duration})

    # -- Listener decorators --

    def on_start(self, func: Any) -> Any:
        """Register a listener for when the timer starts (becomes active).

        Callback: ``(old_state, new_state)``.
        """
        return self._register_state_transition_listener("active", func)

    def on_pause(self, func: Any) -> Any:
        """Register a listener for when the timer is paused.

        Callback: ``(old_state, new_state)``.
        """
        return self._register_state_transition_listener("paused", func)

    def on_idle(self, func: Any) -> Any:
        """Register a listener for when the timer becomes idle (finished or cancelled).

        Callback: ``(old_state, new_state)``.
        """
        return self._register_state_transition_listener("idle", func)
