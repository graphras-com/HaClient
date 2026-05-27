"""``climate`` domain implementation."""

from __future__ import annotations

from typing import Any

from haclient.core.plugins import DomainSpec, register_domain
from haclient.entity.base import Entity, ValueChangeHandler


class Climate(Entity):
    """A Home Assistant climate (thermostat / HVAC) entity.

    The public API uses ``set_hvac_mode`` for all mode changes rather
    than exposing raw ``turn_on`` / ``turn_off`` services.
    """

    domain = "climate"

    # -- Listener decorators ------------------------------------------

    def on_hvac_mode_change(self, func: ValueChangeHandler) -> ValueChangeHandler:
        """Register a listener for HVAC mode changes.

        Parameters
        ----------
        func : callable
            Sync or async callable invoked with ``(old_state, new_state)``
            HVAC mode strings (e.g. ``("cool", "heat")``).

        Returns
        -------
        callable
            The same *func*, returned for decorator use.
        """
        return self._register_state_value_listener(func)

    def on_temperature_change(self, func: ValueChangeHandler) -> ValueChangeHandler:
        """Register a listener for current temperature changes.

        Parameters
        ----------
        func : callable
            Callable invoked with ``(old_value, new_value)`` whenever
            the ``current_temperature`` attribute changes.

        Returns
        -------
        callable
            The same *func*, returned for decorator use.
        """
        return self._register_attr_listener("current_temperature", func)

    def on_target_temperature_change(self, func: ValueChangeHandler) -> ValueChangeHandler:
        """Register a listener for target temperature changes.

        Parameters
        ----------
        func : callable
            Callable invoked with ``(old_value, new_value)`` whenever
            the ``temperature`` (target temperature) attribute changes.

        Returns
        -------
        callable
            The same *func*, returned for decorator use.
        """
        return self._register_attr_listener("temperature", func)

    # -- State properties ---------------------------------------------

    @property
    def current_temperature(self) -> float | None:
        """Current measured temperature, if reported."""
        value = self.attributes.get("current_temperature")
        return float(value) if isinstance(value, (int, float)) else None

    @property
    def target_temperature(self) -> float | None:
        """Current target temperature set-point."""
        value = self.attributes.get("temperature")
        return float(value) if isinstance(value, (int, float)) else None

    @property
    def hvac_mode(self) -> str:
        """Active HVAC mode (same as ``state``)."""
        return self.state

    @property
    def hvac_modes(self) -> list[str]:
        """Supported HVAC modes reported by Home Assistant."""
        modes = self.attributes.get("hvac_modes")
        return list(modes) if isinstance(modes, list) else []

    # -- Actions ------------------------------------------------------

    async def set_temperature(
        self,
        temperature: float,
        *,
        hvac_mode: str | None = None,
        **extra: Any,
    ) -> None:
        """Set the target temperature, optionally changing HVAC mode.

        Parameters
        ----------
        temperature : float
            New target temperature, in the units configured on the
            entity.
        hvac_mode : str or None, optional
            HVAC mode to switch to alongside the temperature change.
        **extra : Any
            Additional fields forwarded verbatim to Home Assistant
            (e.g. ``target_temp_high``, ``target_temp_low``).
        """
        data: dict[str, Any] = {"temperature": float(temperature), **extra}
        if hvac_mode is not None:
            data["hvac_mode"] = hvac_mode
        await self._call_service("set_temperature", data)

    async def set_hvac_mode(self, hvac_mode: str) -> None:
        """Change the HVAC mode (e.g. ``"heat"``, ``"cool"``, ``"off"``).

        Parameters
        ----------
        hvac_mode : str
            One of the modes reported by `hvac_modes`.
        """
        await self._call_service("set_hvac_mode", {"hvac_mode": hvac_mode})

    async def set_fan_mode(self, fan_mode: str) -> None:
        """Set the fan mode.

        Parameters
        ----------
        fan_mode : str
            Fan mode supported by the device (e.g. ``"auto"``,
            ``"low"``, ``"high"``).
        """
        await self._call_service("set_fan_mode", {"fan_mode": fan_mode})


SPEC: DomainSpec[Climate] = register_domain(DomainSpec(name="climate", entity_cls=Climate))
"""The `DomainSpec` registered with the shared `DomainRegistry`."""
