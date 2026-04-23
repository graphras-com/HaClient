"""``binary_sensor`` domain implementation (read-only)."""

from __future__ import annotations

from typing import Any

from ..entity import Entity


class BinarySensor(Entity):
    """A read-only Home Assistant binary sensor entity."""

    domain = "binary_sensor"

    def on_turn_on(self, func: Any) -> Any:
        """Register a listener for when the sensor activates.

        Callback: ``(old_state, new_state)``.
        """
        return self._register_state_transition_listener("on", func)

    def on_turn_off(self, func: Any) -> Any:
        """Register a listener for when the sensor deactivates.

        Callback: ``(old_state, new_state)``.
        """
        return self._register_state_transition_listener("off", func)

    @property
    def is_on(self) -> bool:
        """``True`` if the binary sensor is in the ``on`` state."""
        return self.state == "on"

    @property
    def device_class(self) -> str | None:
        """The device class (e.g. ``"motion"``, ``"door"``)."""
        value = self.attributes.get("device_class")
        return str(value) if value is not None else None
