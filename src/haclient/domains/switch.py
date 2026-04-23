"""``switch`` domain implementation."""

from __future__ import annotations

from typing import Any

from ..entity import Entity


class Switch(Entity):
    """A Home Assistant switch entity."""

    domain = "switch"

    def on_turn_on(self, func: Any) -> Any:
        """Register a listener for when the switch turns on.

        Callback: ``(old_state, new_state)``.
        """
        return self._register_state_transition_listener("on", func)

    def on_turn_off(self, func: Any) -> Any:
        """Register a listener for when the switch turns off.

        Callback: ``(old_state, new_state)``.
        """
        return self._register_state_transition_listener("off", func)

    @property
    def is_on(self) -> bool:
        """``True`` if the switch is currently on."""
        return self.state == "on"

    async def turn_on(self) -> None:
        """Turn the switch on."""
        await self.call_service("turn_on")

    async def turn_off(self) -> None:
        """Turn the switch off."""
        await self.call_service("turn_off")

    async def toggle(self) -> None:
        """Toggle the switch state."""
        await self.call_service("toggle")
