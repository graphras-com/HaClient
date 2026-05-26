"""``humidifier`` domain implementation."""

from __future__ import annotations

from typing import Any

from haclient.core.plugins import DomainSpec, register_domain
from haclient.entity.base import Entity


class Humidifier(Entity):
    """A Home Assistant humidifier (or dehumidifier) entity.

    The public API uses ``on()`` / ``off()`` / ``toggle()`` as
    intent-specific names rather than the raw HA ``turn_on`` /
    ``turn_off`` services, and exposes humidity-specific state and
    actions.

    Mode operations degrade safely: `set_mode` checks the entity's
    reported `available_modes` and raises ``ValueError`` for unsupported
    modes, while devices that do not report modes at all expose an
    empty `available_modes` list and a `mode` of ``None``.
    """

    domain = "humidifier"

    # -- Listener decorators ------------------------------------------

    def on_turn_on(self, func: Any) -> Any:
        """Register a listener for when the humidifier turns on.

        Parameters
        ----------
        func : callable
            Sync or async zero-argument callable invoked on every
            transition into the ``on`` state.

        Returns
        -------
        callable
            The same *func*, returned for decorator use.
        """
        return self._register_state_transition_listener("on", func)

    def on_turn_off(self, func: Any) -> Any:
        """Register a listener for when the humidifier turns off.

        Parameters
        ----------
        func : callable
            Sync or async zero-argument callable invoked on every
            transition into the ``off`` state.

        Returns
        -------
        callable
            The same *func*, returned for decorator use.
        """
        return self._register_state_transition_listener("off", func)

    def on_humidity_change(self, func: Any) -> Any:
        """Register a listener for target humidity changes.

        Parameters
        ----------
        func : callable
            Callable receiving the new target ``humidity`` value.

        Returns
        -------
        callable
            The same *func*, returned for decorator use.
        """
        return self._register_attr_listener("humidity", func)

    def on_mode_change(self, func: Any) -> Any:
        """Register a listener for operating mode changes.

        Parameters
        ----------
        func : callable
            Callable receiving the new mode string.

        Returns
        -------
        callable
            The same *func*, returned for decorator use.
        """
        return self._register_attr_listener("mode", func)

    # -- State properties ---------------------------------------------

    @property
    def is_on(self) -> bool:
        """Whether the humidifier is currently on."""
        return self.state == "on"

    @property
    def target_humidity(self) -> int | None:
        """Configured target humidity, in percent, if reported."""
        value = self.attributes.get("humidity")
        return int(value) if isinstance(value, (int, float)) else None

    @property
    def current_humidity(self) -> int | None:
        """Currently measured humidity, in percent.

        Returns ``None`` when the device does not report a reading.
        """
        value = self.attributes.get("current_humidity")
        return int(value) if isinstance(value, (int, float)) else None

    @property
    def mode(self) -> str | None:
        """Active operating mode, or ``None`` when the device has none."""
        value = self.attributes.get("mode")
        return str(value) if isinstance(value, str) else None

    @property
    def available_modes(self) -> list[str]:
        """Operating modes supported by the device.

        Returns an empty list when the device does not advertise modes.
        """
        modes = self.attributes.get("available_modes")
        return [str(m) for m in modes] if isinstance(modes, list) else []

    @property
    def device_class(self) -> str | None:
        """Device class (``"humidifier"`` or ``"dehumidifier"``)."""
        value = self.attributes.get("device_class")
        return str(value) if isinstance(value, str) else None

    # -- Actions ------------------------------------------------------

    async def on(self) -> None:
        """Activate the humidifier."""
        await self._call_service("turn_on")

    async def off(self) -> None:
        """Deactivate the humidifier."""
        await self._call_service("turn_off")

    async def toggle(self) -> None:
        """Toggle the humidifier state."""
        await self._call_service("toggle")

    async def set_humidity(self, humidity: int) -> None:
        """Set the target humidity, in percent.

        Parameters
        ----------
        humidity : int
            Target humidity between 0 and 100 (inclusive).

        Raises
        ------
        ValueError
            If *humidity* is outside the 0-100 range.
        """
        value = int(humidity)
        if not 0 <= value <= 100:
            raise ValueError("humidity must be between 0 and 100")
        await self._call_service("set_humidity", {"humidity": value})

    async def set_mode(self, mode: str) -> None:
        """Set the operating mode, when supported.

        Parameters
        ----------
        mode : str
            Mode to activate. Must be one of `available_modes` when the
            device reports any; the call is silently skipped for devices
            that do not support modes at all (empty `available_modes`).

        Raises
        ------
        ValueError
            If the device reports `available_modes` and *mode* is not
            in that list.
        """
        modes = self.available_modes
        if not modes:
            # Graceful degradation: device exposes no modes.
            return
        if mode not in modes:
            raise ValueError(
                f"mode {mode!r} not in available_modes {modes!r}",
            )
        await self._call_service("set_mode", {"mode": mode})


SPEC: DomainSpec[Humidifier] = register_domain(DomainSpec(name="humidifier", entity_cls=Humidifier))
"""The `DomainSpec` registered with the shared `DomainRegistry`."""
