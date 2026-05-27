"""``sensor`` domain implementation (read-only)."""

from __future__ import annotations

from haclient.core.plugins import DomainSpec, register_domain
from haclient.entity.base import Entity, ValueChangeHandler


class Sensor(Entity):
    """A read-only Home Assistant sensor entity.

    Exposes the sensor's value, unit of measurement, and device class.
    The ``value`` property automatically coerces numeric state strings
    to ``float``.
    """

    domain = "sensor"

    # -- Listener decorators ------------------------------------------

    def on_value_change(self, func: ValueChangeHandler) -> ValueChangeHandler:
        """Register a listener for sensor value changes.

        Parameters
        ----------
        func : callable
            Sync or async callable invoked with the previous and current
            sensor **state strings** as ``(old_value, new_value)``
            (e.g. ``("21.5", "22.0")``).

        Returns
        -------
        callable
            The same *func*, returned for decorator use.
        """
        return self._register_state_value_listener(func)

    # -- State properties ---------------------------------------------

    @property
    def unit_of_measurement(self) -> str | None:
        """Unit of the sensor value, if provided."""
        value = self.attributes.get("unit_of_measurement")
        return str(value) if value is not None else None

    @property
    def device_class(self) -> str | None:
        """Device class (e.g. ``"temperature"``)."""
        value = self.attributes.get("device_class")
        return str(value) if value is not None else None

    @property
    def value(self) -> float | str | None:
        """Sensor value coerced to ``float`` if numeric.

        Returns
        -------
        float or str or None
            ``None`` if the state is ``"unknown"``/``"unavailable"``,
            a ``float`` when numeric, otherwise the raw string.
        """
        if self.state in ("unknown", "unavailable"):
            return None
        try:
            return float(self.state)
        except (TypeError, ValueError):
            return self.state


SPEC: DomainSpec[Sensor] = register_domain(DomainSpec(name="sensor", entity_cls=Sensor))
"""The `DomainSpec` registered with the shared `DomainRegistry`."""
