"""``climate`` domain implementation."""

from __future__ import annotations

from typing import Any

from ..entity import Entity


class Climate(Entity):
    """A Home Assistant climate (thermostat / HVAC) entity.

    The public API uses ``set_hvac_mode`` for all mode changes rather
    than exposing raw ``turn_on`` / ``turn_off`` services. Calling
    ``set_hvac_mode("off")`` is equivalent to the HA ``turn_off``
    service.
    """

    domain = "climate"

    # -- Listener decorators --

    def on_hvac_mode_change(self, func: Any) -> Any:
        """Register a listener for HVAC mode changes.

        Parameters
        ----------
        func : callable
            Callback with signature ``(old_mode, new_mode)``.

        Returns
        -------
        callable
            The same *func*, for use as a decorator.
        """
        return self._register_state_value_listener(func)

    def on_temperature_change(self, func: Any) -> Any:
        """Register a listener for current temperature changes.

        Parameters
        ----------
        func : callable
            Callback with signature ``(old_temp, new_temp)``.

        Returns
        -------
        callable
            The same *func*, for use as a decorator.
        """
        return self._register_attr_listener("current_temperature", func)

    def on_target_temperature_change(self, func: Any) -> Any:
        """Register a listener for target temperature changes.

        Parameters
        ----------
        func : callable
            Callback with signature ``(old_temp, new_temp)``.

        Returns
        -------
        callable
            The same *func*, for use as a decorator.
        """
        return self._register_attr_listener("temperature", func)

    # -- State properties --

    @property
    def current_temperature(self) -> float | None:
        """The current measured temperature, if reported.

        Returns
        -------
        float or None
            The measured temperature.
        """
        value = self.attributes.get("current_temperature")
        return float(value) if isinstance(value, (int, float)) else None

    @property
    def target_temperature(self) -> float | None:
        """The current target temperature set-point.

        Returns
        -------
        float or None
            The target temperature.
        """
        value = self.attributes.get("temperature")
        return float(value) if isinstance(value, (int, float)) else None

    @property
    def hvac_mode(self) -> str:
        """The active HVAC mode (same as ``state``).

        Returns
        -------
        str
            The current HVAC mode string (e.g. ``"heat"``, ``"cool"``, ``"off"``).
        """
        return self.state

    @property
    def hvac_modes(self) -> list[str]:
        """Supported HVAC modes reported by Home Assistant.

        Returns
        -------
        list of str
            The list of supported mode strings.
        """
        modes = self.attributes.get("hvac_modes")
        return list(modes) if isinstance(modes, list) else []

    # -- Actions --

    async def set_temperature(
        self,
        temperature: float,
        *,
        hvac_mode: str | None = None,
        **extra: Any,
    ) -> None:
        """Set the target temperature.

        Parameters
        ----------
        temperature : float
            Desired target temperature.
        hvac_mode : str or None, optional
            Optionally change the HVAC mode at the same time.
        **extra : Any
            Additional service data forwarded to Home Assistant.
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
            The desired HVAC mode.
        """
        await self._call_service("set_hvac_mode", {"hvac_mode": hvac_mode})

    async def set_fan_mode(self, fan_mode: str) -> None:
        """Set the fan mode.

        Parameters
        ----------
        fan_mode : str
            The desired fan mode (e.g. ``"auto"``, ``"low"``, ``"high"``).
        """
        await self._call_service("set_fan_mode", {"fan_mode": fan_mode})
