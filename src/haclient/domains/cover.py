"""``cover`` domain implementation."""

from __future__ import annotations

from typing import Any

from ..entity import Entity


class Cover(Entity):
    """A Home Assistant cover (blind/garage/shade) entity."""

    domain = "cover"

    def on_open(self, func: Any) -> Any:
        """Register a listener for when the cover opens. Callback: ``(old_state, new_state)``."""
        return self._register_state_transition_listener("open", func)

    def on_close(self, func: Any) -> Any:
        """Register a listener for when the cover closes. Callback: ``(old_state, new_state)``."""
        return self._register_state_transition_listener("closed", func)

    def on_position_change(self, func: Any) -> Any:
        """Register a listener for position changes. Callback: ``(old, new)``."""
        return self._register_attr_listener("current_position", func)

    @property
    def is_open(self) -> bool:
        """``True`` if the cover is currently open."""
        return self.state == "open"

    @property
    def is_closed(self) -> bool:
        """``True`` if the cover is currently closed."""
        return self.state == "closed"

    @property
    def current_position(self) -> int | None:
        """Current position (0–100) or ``None`` if unsupported."""
        value = self.attributes.get("current_position")
        return int(value) if isinstance(value, (int, float)) else None

    async def open(self) -> None:
        """Open the cover fully."""
        await self.call_service("open_cover")

    async def close(self) -> None:
        """Close the cover fully."""
        await self.call_service("close_cover")

    async def stop(self) -> None:
        """Stop movement of the cover."""
        await self.call_service("stop_cover")

    async def set_position(self, position: int) -> None:
        """Set the cover position (0 closed, 100 open)."""
        await self.call_service("set_cover_position", {"position": int(position)})

    async def toggle(self) -> None:
        """Toggle open/close state."""
        await self.call_service("toggle")
