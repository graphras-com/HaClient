"""``air_quality`` domain implementation (read-only)."""

from __future__ import annotations

from typing import Any

from haclient.core.plugins import DomainSpec, register_domain
from haclient.entity.base import Entity


def _coerce_numeric(value: Any) -> float | int | None:
    """Coerce an air-quality attribute value to a number.

    Parameters
    ----------
    value : Any
        Raw attribute value from Home Assistant.

    Returns
    -------
    float, int, or None
        ``int`` when the value is an integer literal, ``float`` for any
        other numeric value (including numeric strings), and ``None``
        when the value is missing, non-numeric, or one of HA's sentinel
        unavailability strings.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        # bool is a subclass of int; treat it as not a real measurement.
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value
    if isinstance(value, str):
        if value in ("unknown", "unavailable", ""):
            return None
        try:
            return float(value)
        except ValueError:
            return None
    return None


class AirQuality(Entity):
    """A read-only Home Assistant air quality entity.

    Exposes typed properties for the pollutant metrics the underlying
    integration chooses to report. Every metric returns ``None`` when
    the sensor does not provide that reading, so unsupported metrics
    degrade silently rather than raising. The entity is read-only; the
    HA ``air_quality`` domain exposes no service actions.

    The Home Assistant ``air_quality`` platform reports its overall Air
    Quality Index (AQI) as the entity *state* and individual pollutants
    as attributes. `air_quality_index` therefore prefers an explicit
    ``air_quality_index`` attribute when present and falls back to the
    state string. All other metrics are read directly from attributes.
    """

    domain = "air_quality"

    # -- Listener decorators ------------------------------------------

    def on_aqi_change(self, func: Any) -> Any:
        """Register a listener for Air Quality Index changes.

        Fires whenever the entity *state* string changes, which mirrors
        the HA convention of reporting the AQI as the entity state.

        Parameters
        ----------
        func : callable
            Sync or async callable receiving ``(old_state, new_state)``.

        Returns
        -------
        callable
            The same *func*, returned for decorator use.
        """
        return self._register_state_value_listener(func)

    def on_pm25_change(self, func: Any) -> Any:
        """Register a listener for PM2.5 attribute changes.

        Parameters
        ----------
        func : callable
            Callable receiving ``(old_value, new_value)`` for the
            ``particulate_matter_2_5`` attribute.

        Returns
        -------
        callable
            The same *func*, returned for decorator use.
        """
        return self._register_attr_listener("particulate_matter_2_5", func)

    def on_co2_change(self, func: Any) -> Any:
        """Register a listener for CO2 attribute changes.

        Parameters
        ----------
        func : callable
            Callable receiving ``(old_value, new_value)`` for the
            ``carbon_dioxide`` attribute.

        Returns
        -------
        callable
            The same *func*, returned for decorator use.
        """
        return self._register_attr_listener("carbon_dioxide", func)

    # -- State properties ---------------------------------------------

    @property
    def air_quality_index(self) -> float | int | None:
        """Overall Air Quality Index, if reported.

        Returns
        -------
        float, int, or None
            The explicit ``air_quality_index`` attribute when present,
            otherwise the numeric coercion of the entity state, or
            ``None`` when neither yields a number.
        """
        explicit = _coerce_numeric(self.attributes.get("air_quality_index"))
        if explicit is not None:
            return explicit
        return _coerce_numeric(self.state)

    @property
    def particulate_matter_2_5(self) -> float | int | None:
        """PM2.5 reading, typically in µg/m³."""
        return _coerce_numeric(self.attributes.get("particulate_matter_2_5"))

    @property
    def particulate_matter_10(self) -> float | int | None:
        """PM10 reading, typically in µg/m³."""
        return _coerce_numeric(self.attributes.get("particulate_matter_10"))

    @property
    def carbon_dioxide(self) -> float | int | None:
        """CO2 concentration, typically in ppm."""
        return _coerce_numeric(self.attributes.get("carbon_dioxide"))

    @property
    def carbon_monoxide(self) -> float | int | None:
        """CO concentration, typically in ppm."""
        return _coerce_numeric(self.attributes.get("carbon_monoxide"))

    @property
    def volatile_organic_compounds(self) -> float | int | None:
        """Volatile organic compound concentration, if reported."""
        return _coerce_numeric(self.attributes.get("volatile_organic_compounds"))

    @property
    def nitrogen_dioxide(self) -> float | int | None:
        """NO2 concentration, if reported."""
        return _coerce_numeric(self.attributes.get("nitrogen_dioxide"))

    @property
    def ozone(self) -> float | int | None:
        """Ozone concentration, if reported."""
        return _coerce_numeric(self.attributes.get("ozone"))


SPEC: DomainSpec[AirQuality] = register_domain(
    DomainSpec(name="air_quality", entity_cls=AirQuality)
)
"""The `DomainSpec` registered with the shared `DomainRegistry`."""
