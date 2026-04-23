"""``sensor`` domain implementation (read-only)."""

from __future__ import annotations

from typing import Any

from ..entity import Entity


class Sensor(Entity):
    """A read-only Home Assistant sensor entity."""

    domain = "sensor"

    def on_value_change(self, func: Any) -> Any:
        """Register a listener for sensor value changes. Callback: ``(old_state, new_state)``."""
        return self._register_state_value_listener(func)

    @property
    def unit_of_measurement(self) -> str | None:
        """The unit of the sensor value, if provided by Home Assistant."""
        value = self.attributes.get("unit_of_measurement")
        return str(value) if value is not None else None

    @property
    def device_class(self) -> str | None:
        """The device class (e.g. ``"temperature"``)."""
        value = self.attributes.get("device_class")
        return str(value) if value is not None else None

    @property
    def value(self) -> float | str | None:
        """Return the sensor value coerced to ``float`` if numeric."""
        if self.state in ("unknown", "unavailable"):
            return None
        try:
            return float(self.state)
        except (TypeError, ValueError):
            return self.state
