"""``light`` domain implementation."""

from __future__ import annotations

from typing import Any

from haclient.core.plugins import DomainSpec, register_domain
from haclient.entity.base import Entity, ValueChangeHandler


class Light(Entity):
    """A Home Assistant light entity.

    Provides intent-specific methods for controlling brightness, color,
    and color temperature rather than exposing the overloaded
    ``turn_on`` / ``turn_off`` HA service interface directly.

    Properties expose the current state of the light: whether it is on,
    its brightness, RGB color, and Kelvin color temperature.
    """

    domain = "light"

    # -- Listener decorators ------------------------------------------

    def on_turn_on(self, func: ValueChangeHandler) -> ValueChangeHandler:
        """Register a listener for when the light turns on.

        Parameters
        ----------
        func : callable
            Sync or async callable invoked with ``(old_state, new_state)``
            on every transition into the ``on`` state.

        Returns
        -------
        callable
            The same *func*, returned for decorator use.
        """
        return self._register_state_transition_listener("on", func)

    def on_turn_off(self, func: ValueChangeHandler) -> ValueChangeHandler:
        """Register a listener for when the light turns off.

        Parameters
        ----------
        func : callable
            Sync or async callable invoked with ``(old_state, new_state)``
            on every transition into the ``off`` state.

        Returns
        -------
        callable
            The same *func*, returned for decorator use.
        """
        return self._register_state_transition_listener("off", func)

    def on_brightness_change(self, func: ValueChangeHandler) -> ValueChangeHandler:
        """Register a listener for brightness changes.

        Parameters
        ----------
        func : callable
            Callable invoked with ``(old_value, new_value)`` whenever
            the ``brightness`` attribute (0-255) changes.

        Returns
        -------
        callable
            The same *func*, returned for decorator use.
        """
        return self._register_attr_listener("brightness", func)

    def on_color_change(self, func: ValueChangeHandler) -> ValueChangeHandler:
        """Register a listener for RGB color changes.

        Parameters
        ----------
        func : callable
            Callable invoked with ``(old_value, new_value)`` whenever
            the ``rgb_color`` attribute reported by Home Assistant
            changes.

        Returns
        -------
        callable
            The same *func*, returned for decorator use.
        """
        return self._register_attr_listener("rgb_color", func)

    def on_kelvin_change(self, func: ValueChangeHandler) -> ValueChangeHandler:
        """Register a listener for color temperature (Kelvin) changes.

        Parameters
        ----------
        func : callable
            Callable invoked with ``(old_value, new_value)`` whenever
            the ``color_temp_kelvin`` attribute changes.

        Returns
        -------
        callable
            The same *func*, returned for decorator use.
        """
        return self._register_attr_listener("color_temp_kelvin", func)

    # -- State properties ---------------------------------------------

    @property
    def is_on(self) -> bool:
        """Whether the light is currently on."""
        return self.state == "on"

    @property
    def brightness(self) -> int | None:
        """Current brightness (0--255) or ``None``."""
        value = self.attributes.get("brightness")
        return int(value) if isinstance(value, (int, float)) else None

    @property
    def min_kelvin(self) -> int | None:
        """Minimum supported color temperature in Kelvin, or ``None``."""
        value = self.attributes.get("min_color_temp_kelvin")
        return int(value) if isinstance(value, (int, float)) else None

    @property
    def max_kelvin(self) -> int | None:
        """Maximum supported color temperature in Kelvin, or ``None``."""
        value = self.attributes.get("max_color_temp_kelvin")
        return int(value) if isinstance(value, (int, float)) else None

    @property
    def kelvin(self) -> int | None:
        """Current color temperature in Kelvin, or ``None``."""
        value = self.attributes.get("color_temp_kelvin")
        return int(value) if isinstance(value, (int, float)) else None

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Current RGB color tuple, or ``None``."""
        value = self.attributes.get("rgb_color")
        if isinstance(value, (list, tuple)) and len(value) == 3:
            return (int(value[0]), int(value[1]), int(value[2]))
        return None

    # -- Actions ------------------------------------------------------

    async def set_brightness(self, brightness: int, *, transition: float | None = None) -> None:
        """Set the brightness (0--255), turning the light on if needed.

        Parameters
        ----------
        brightness : int
            New brightness value, coerced to ``int``. ``0`` turns the
            light off; ``255`` is full brightness.
        transition : float or None, optional
            Seconds for the transition. Forwarded to HA when set.
        """
        data: dict[str, Any] = {"brightness": int(brightness)}
        if transition is not None:
            data["transition"] = transition
        await self._call_service("turn_on", data)

    async def set_kelvin(self, kelvin: int, *, transition: float | None = None) -> None:
        """Set the color temperature in Kelvin, turning the light on if needed.

        Parameters
        ----------
        kelvin : int
            Target color temperature in Kelvin.
        transition : float or None, optional
            Seconds for the transition. Forwarded to HA when set.
        """
        data: dict[str, Any] = {"color_temp_kelvin": int(kelvin)}
        if transition is not None:
            data["transition"] = transition
        await self._call_service("turn_on", data)

    async def set_rgb(
        self,
        r: int,
        g: int,
        b: int,
        *,
        transition: float | None = None,
    ) -> None:
        """Set the RGB color, turning the light on if needed.

        Parameters
        ----------
        r : int
            Red component (0-255).
        g : int
            Green component (0-255).
        b : int
            Blue component (0-255).
        transition : float or None, optional
            Seconds for the transition. Forwarded to HA when set.
        """
        data: dict[str, Any] = {"rgb_color": [r, g, b]}
        if transition is not None:
            data["transition"] = transition
        await self._call_service("turn_on", data)

    async def set_color(
        self,
        *,
        rgb: tuple[int, int, int] | None = None,
        kelvin: int | None = None,
        transition: float | None = None,
    ) -> None:
        """Set the light color by RGB or Kelvin.

        Exactly one of *rgb* or *kelvin* must be provided.

        Parameters
        ----------
        rgb : tuple of int or None, optional
            Three-tuple ``(r, g, b)`` with components in 0-255.
        kelvin : int or None, optional
            Target color temperature in Kelvin.
        transition : float or None, optional
            Seconds for the transition. Forwarded to HA when set.

        Raises
        ------
        ValueError
            If neither or both of *rgb* and *kelvin* are provided.
        """
        if (rgb is None) == (kelvin is None):
            raise ValueError("Exactly one of 'rgb' or 'kelvin' must be provided")
        if rgb is not None:
            data: dict[str, Any] = {"rgb_color": list(rgb)}
            if transition is not None:
                data["transition"] = transition
            await self._call_service("turn_on", data)
        else:
            data = {"color_temp_kelvin": int(kelvin)}  # type: ignore[arg-type]
            if transition is not None:
                data["transition"] = transition
            await self._call_service("turn_on", data)

    async def on(self, *, transition: float | None = None) -> None:
        """Turn the light on without changing color or brightness.

        Parameters
        ----------
        transition : float or None, optional
            Seconds for the transition. Forwarded to HA when set.
        """
        data: dict[str, Any] = {}
        if transition is not None:
            data["transition"] = transition
        await self._call_service("turn_on", data or None)

    async def off(self, *, transition: float | None = None) -> None:
        """Turn the light off.

        Parameters
        ----------
        transition : float or None, optional
            Seconds for the transition. Forwarded to HA when set.
        """
        data: dict[str, Any] = {}
        if transition is not None:
            data["transition"] = transition
        await self._call_service("turn_off", data or None)

    async def toggle(self) -> None:
        """Toggle the on/off state of the light."""
        await self._call_service("toggle")


SPEC: DomainSpec[Light] = register_domain(DomainSpec(name="light", entity_cls=Light))
"""The `DomainSpec` registered with the shared `DomainRegistry`."""
