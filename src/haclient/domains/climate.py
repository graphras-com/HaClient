"""``climate`` domain implementation."""

from __future__ import annotations

from typing import Any

from ..entity import Entity


class Climate(Entity):
    """A Home Assistant climate (thermostat / HVAC) entity."""

    domain = "climate"

    def on_hvac_mode_change(self, func: Any) -> Any:
        """Register a listener for HVAC mode changes. Callback: ``(old_mode, new_mode)``."""
        return self._register_state_value_listener(func)

    def on_temperature_change(self, func: Any) -> Any:
        """Register a listener for current temperature changes. Callback: ``(old, new)``."""
        return self._register_attr_listener("current_temperature", func)

    def on_target_temperature_change(self, func: Any) -> Any:
        """Register a listener for target temperature changes. Callback: ``(old, new)``."""
        return self._register_attr_listener("temperature", func)

    @property
    def current_temperature(self) -> float | None:
        """The current measured temperature, if reported."""
        value = self.attributes.get("current_temperature")
        return float(value) if isinstance(value, (int, float)) else None

    @property
    def target_temperature(self) -> float | None:
        """The current target temperature set-point."""
        value = self.attributes.get("temperature")
        return float(value) if isinstance(value, (int, float)) else None

    @property
    def hvac_mode(self) -> str:
        """The active HVAC mode (same as :attr:`state`)."""
        return self.state

    @property
    def hvac_modes(self) -> list[str]:
        """Supported HVAC modes reported by Home Assistant."""
        modes = self.attributes.get("hvac_modes")
        return list(modes) if isinstance(modes, list) else []

    async def set_temperature(
        self,
        temperature: float,
        *,
        hvac_mode: str | None = None,
        **extra: Any,
    ) -> None:
        """Set the target temperature (optionally changing HVAC mode)."""
        data: dict[str, Any] = {"temperature": float(temperature), **extra}
        if hvac_mode is not None:
            data["hvac_mode"] = hvac_mode
        await self.call_service("set_temperature", data)

    async def set_hvac_mode(self, hvac_mode: str) -> None:
        """Change the HVAC mode (e.g. ``"heat"``, ``"cool"``, ``"off"``)."""
        await self.call_service("set_hvac_mode", {"hvac_mode": hvac_mode})

    async def set_fan_mode(self, fan_mode: str) -> None:
        """Set the fan mode."""
        await self.call_service("set_fan_mode", {"fan_mode": fan_mode})

    async def turn_off(self) -> None:
        """Turn off the climate entity."""
        await self.call_service("turn_off")

    async def turn_on(self) -> None:
        """Turn on the climate entity (resumes last HVAC mode)."""
        await self.call_service("turn_on")
