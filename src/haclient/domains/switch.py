"""``switch`` domain implementation."""

from __future__ import annotations

from typing import Any

from ..entity import Entity


class Switch(Entity):
    """A Home Assistant switch entity.

    Switches are binary devices that can be turned on or off. The public
    API uses ``on()`` / ``off()`` / ``toggle()`` as intent-specific names
    rather than the raw HA ``turn_on`` / ``turn_off`` service names.
    """

    domain = "switch"

    # -- Listener decorators --

    def on_turn_on(self, func: Any) -> Any:
        """Register a listener for when the switch turns on.

        Parameters
        ----------
        func : callable
            Callback with signature ``(old_state, new_state)``.

        Returns
        -------
        callable
            The same *func*, for use as a decorator.
        """
        return self._register_state_transition_listener("on", func)

    def on_turn_off(self, func: Any) -> Any:
        """Register a listener for when the switch turns off.

        Parameters
        ----------
        func : callable
            Callback with signature ``(old_state, new_state)``.

        Returns
        -------
        callable
            The same *func*, for use as a decorator.
        """
        return self._register_state_transition_listener("off", func)

    # -- State properties --

    @property
    def is_on(self) -> bool:
        """Check whether the switch is currently on.

        Returns
        -------
        bool
            ``True`` if the switch is on.
        """
        return self.state == "on"

    # -- Actions --

    async def on(self) -> None:
        """Activate the switch."""
        await self._call_service("turn_on")

    async def off(self) -> None:
        """Deactivate the switch."""
        await self._call_service("turn_off")

    async def toggle(self) -> None:
        """Toggle the switch state."""
        await self._call_service("toggle")
