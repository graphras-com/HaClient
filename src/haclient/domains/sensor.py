"""``sensor`` domain implementation (read-only)."""

from __future__ import annotations

from typing import Any

from ..entity import Entity


class Sensor(Entity):
    """A read-only Home Assistant sensor entity.

    Exposes the sensor's value, unit of measurement, and device class.
    The ``value`` property automatically coerces numeric state strings
    to ``float``.
    """

    domain = "sensor"

    # -- Listener decorators --

    def on_value_change(self, func: Any) -> Any:
        """Register a listener for sensor value changes.

        The callback receives the **state strings** directly (e.g.
        ``"21.5"``, ``"22.0"``) — not the full HA state dictionaries.
        This fires whenever the state string changes between events.

        Use this instead of :meth:`~haclient.entity.Entity.on_state_change`
        when you only care about the sensor's value and not the full state
        object (attributes, timestamps, etc.).

        Parameters
        ----------
        func : callable
            Callback with signature ``(old_state_str: str | None,
            new_state_str: str | None)``. Both arguments are raw state
            strings (e.g. ``"22.5"``, ``"on"``), or ``None`` if the
            previous/new state is absent.

        Returns
        -------
        callable
            The same *func*, for use as a decorator.
        """
        return self._register_state_value_listener(func)

    # -- State properties --

    @property
    def unit_of_measurement(self) -> str | None:
        """The unit of the sensor value, if provided by Home Assistant.

        Returns
        -------
        str or None
            The unit string (e.g. ``"°C"``).
        """
        value = self.attributes.get("unit_of_measurement")
        return str(value) if value is not None else None

    @property
    def device_class(self) -> str | None:
        """The device class (e.g. ``"temperature"``).

        Returns
        -------
        str or None
            The device class string, or ``None`` if not set.
        """
        value = self.attributes.get("device_class")
        return str(value) if value is not None else None

    @property
    def value(self) -> float | str | None:
        """Return the sensor value coerced to ``float`` if numeric.

        Returns
        -------
        float or str or None
            ``None`` if the state is ``"unknown"`` or ``"unavailable"``,
            a ``float`` if the state is numeric, otherwise the raw string.
        """
        if self.state in ("unknown", "unavailable"):
            return None
        try:
            return float(self.state)
        except (TypeError, ValueError):
            return self.state
