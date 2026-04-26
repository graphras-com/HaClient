"""``cover`` domain implementation."""

from __future__ import annotations

from typing import Any

from ..entity import Entity


class Cover(Entity):
    """A Home Assistant cover (blind/garage/shade) entity.

    Uses intent-specific names (``open``, ``close``, ``stop``,
    ``set_position``) rather than raw HA service names.
    """

    domain = "cover"

    # -- Listener decorators --

    def on_open(self, func: Any) -> Any:
        """Register a listener for when the cover opens.

        Parameters
        ----------
        func : callable
            Callback with signature ``(old_state, new_state)``.

        Returns
        -------
        callable
            The same *func*, for use as a decorator.
        """
        return self._register_state_transition_listener("open", func)

    def on_close(self, func: Any) -> Any:
        """Register a listener for when the cover closes.

        Parameters
        ----------
        func : callable
            Callback with signature ``(old_state, new_state)``.

        Returns
        -------
        callable
            The same *func*, for use as a decorator.
        """
        return self._register_state_transition_listener("closed", func)

    def on_position_change(self, func: Any) -> Any:
        """Register a listener for position changes.

        Parameters
        ----------
        func : callable
            Callback with signature ``(old_position, new_position)``.

        Returns
        -------
        callable
            The same *func*, for use as a decorator.
        """
        return self._register_attr_listener("current_position", func)

    # -- State properties --

    @property
    def is_open(self) -> bool:
        """Check whether the cover is currently open.

        Returns
        -------
        bool
            ``True`` if the cover is open.
        """
        return self.state == "open"

    @property
    def is_closed(self) -> bool:
        """Check whether the cover is currently closed.

        Returns
        -------
        bool
            ``True`` if the cover is closed.
        """
        return self.state == "closed"

    @property
    def current_position(self) -> int | None:
        """Current position (0--100) or ``None`` if unsupported.

        Returns
        -------
        int or None
            The position value (0 = closed, 100 = open).
        """
        value = self.attributes.get("current_position")
        return int(value) if isinstance(value, (int, float)) else None

    # -- Actions --

    async def open(self) -> None:
        """Open the cover fully."""
        await self._call_service("open_cover")

    async def close(self) -> None:
        """Close the cover fully."""
        await self._call_service("close_cover")

    async def stop(self) -> None:
        """Stop movement of the cover."""
        await self._call_service("stop_cover")

    async def set_position(self, position: int) -> None:
        """Set the cover position.

        Parameters
        ----------
        position : int
            Target position (0 = closed, 100 = open).
        """
        await self._call_service("set_cover_position", {"position": int(position)})

    async def toggle(self) -> None:
        """Toggle open/close state."""
        await self._call_service("toggle")
