"""``fan`` domain implementation."""

from __future__ import annotations

import logging

from haclient.core.plugins import DomainSpec, register_domain
from haclient.entity.base import Entity, ValueChangeHandler

_LOGGER = logging.getLogger(__name__)

# Home Assistant ``FanEntityFeature`` bitmask.
# See homeassistant/components/fan/const.py.
_FEATURE_SET_SPEED = 1
_FEATURE_OSCILLATE = 2
_FEATURE_DIRECTION = 4
_FEATURE_PRESET_MODE = 8

# Canonical Home Assistant fan direction values.
_DIRECTION_FORWARD = "forward"
_DIRECTION_REVERSE = "reverse"
_VALID_DIRECTIONS = frozenset({_DIRECTION_FORWARD, _DIRECTION_REVERSE})


class Fan(Entity):
    """A Home Assistant fan entity.

    The public API uses intent-specific actions (``on``, ``off``,
    ``toggle``, ``set_percentage``, ``set_preset_mode``,
    ``set_direction``, ``oscillate``) and exposes structured state
    (``is_on``, ``percentage``, ``preset_mode``, ``preset_modes``,
    ``oscillating``, ``direction``) rather than raw service calls.

    Methods that depend on optional fan capabilities degrade safely: if
    the underlying hardware does not advertise the relevant
    ``FanEntityFeature`` bit in ``supported_features``, the call becomes
    a no-op that logs a debug message instead of raising. Callers that
    need to know whether an action will actually be dispatched can
    pre-check with the ``supports_*`` properties.
    """

    domain = "fan"

    # -- Listener decorators ------------------------------------------

    def on_turn_on(self, func: ValueChangeHandler) -> ValueChangeHandler:
        """Register a listener for when the fan turns on.

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
        """Register a listener for when the fan turns off.

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

    def on_speed_change(self, func: ValueChangeHandler) -> ValueChangeHandler:
        """Register a listener for fan speed (``percentage``) changes.

        Parameters
        ----------
        func : callable
            Callable receiving the new ``percentage`` value as
            ``(old_value, new_value)``.

        Returns
        -------
        callable
            The same *func*, returned for decorator use.
        """
        return self._register_attr_listener("percentage", func)

    def on_direction_change(self, func: ValueChangeHandler) -> ValueChangeHandler:
        """Register a listener for fan direction changes.

        Parameters
        ----------
        func : callable
            Callable receiving the new direction string as
            ``(old_value, new_value)``.

        Returns
        -------
        callable
            The same *func*, returned for decorator use.
        """
        return self._register_attr_listener("direction", func)

    # -- Feature detection --------------------------------------------

    def _has_feature(self, mask: int) -> bool:
        """Return ``True`` when ``supported_features`` advertises *mask*.

        Parameters
        ----------
        mask : int
            One of the ``FanEntityFeature`` bit constants.

        Returns
        -------
        bool
            ``True`` if the entity reports an integer
            ``supported_features`` bitmask, otherwise ``False``.
        """
        features = self.attributes.get("supported_features")
        if not isinstance(features, int):
            return False
        return bool(features & mask)

    @property
    def supports_set_speed(self) -> bool:
        """Whether the device advertises ``FanEntityFeature.SET_SPEED``."""
        return self._has_feature(_FEATURE_SET_SPEED)

    @property
    def supports_oscillate(self) -> bool:
        """Whether the device advertises ``FanEntityFeature.OSCILLATE``."""
        return self._has_feature(_FEATURE_OSCILLATE)

    @property
    def supports_direction(self) -> bool:
        """Whether the device advertises ``FanEntityFeature.DIRECTION``."""
        return self._has_feature(_FEATURE_DIRECTION)

    @property
    def supports_preset_mode(self) -> bool:
        """Whether the device advertises ``FanEntityFeature.PRESET_MODE``."""
        return self._has_feature(_FEATURE_PRESET_MODE)

    # -- State properties ---------------------------------------------

    @property
    def is_on(self) -> bool:
        """Whether the fan is currently on."""
        return self.state == "on"

    @property
    def percentage(self) -> int | None:
        """Current fan speed in percent, or ``None`` when not reported."""
        value = self.attributes.get("percentage")
        return int(value) if isinstance(value, (int, float)) else None

    @property
    def preset_mode(self) -> str | None:
        """Active preset mode, or ``None`` when the device has none."""
        value = self.attributes.get("preset_mode")
        return str(value) if isinstance(value, str) else None

    @property
    def preset_modes(self) -> list[str]:
        """Preset modes supported by the device.

        Returns an empty list when the device does not advertise modes.
        Non-string entries in the underlying attribute are filtered out.
        """
        modes = self.attributes.get("preset_modes")
        if not isinstance(modes, list):
            return []
        return [m for m in modes if isinstance(m, str)]

    @property
    def oscillating(self) -> bool | None:
        """Whether the fan is currently oscillating.

        Returns ``None`` when the device does not report this attribute.
        """
        value = self.attributes.get("oscillating")
        return bool(value) if isinstance(value, bool) else None

    @property
    def direction(self) -> str | None:
        """Current fan direction (``"forward"`` or ``"reverse"``).

        Returns ``None`` when the device does not report a direction.
        """
        value = self.attributes.get("direction")
        return str(value) if isinstance(value, str) else None

    # -- Actions ------------------------------------------------------

    async def on(self) -> None:
        """Turn the fan on."""
        await self._call_service("turn_on")

    async def off(self) -> None:
        """Turn the fan off."""
        await self._call_service("turn_off")

    async def toggle(self) -> None:
        """Toggle the fan state."""
        await self._call_service("toggle")

    async def set_percentage(self, percentage: int) -> None:
        """Set the fan speed, in percent.

        Parameters
        ----------
        percentage : int
            Target speed between 0 and 100 (inclusive). ``0`` typically
            turns the fan off.

        Raises
        ------
        ValueError
            If *percentage* is outside the 0-100 range.

        Notes
        -----
        Degrades safely: if the fan does not advertise the
        ``SET_SPEED`` feature, this method logs a debug message and
        returns without raising. Callers can pre-check with
        `supports_set_speed`.
        """
        value = int(percentage)
        if not 0 <= value <= 100:
            raise ValueError("percentage must be between 0 and 100")
        if not self.supports_set_speed:
            _LOGGER.debug(
                "set_percentage() unsupported for %s; skipping (no FanEntityFeature.SET_SPEED)",
                self.entity_id,
            )
            return
        await self._call_service("set_percentage", {"percentage": value})

    async def set_preset_mode(self, mode: str) -> None:
        """Activate a named preset mode, when supported.

        Parameters
        ----------
        mode : str
            Preset mode to activate. Must be one of `preset_modes` when
            the device reports any.

        Raises
        ------
        ValueError
            If the device reports `preset_modes` and *mode* is not in
            that list.

        Notes
        -----
        Degrades safely: if the fan does not advertise the
        ``PRESET_MODE`` feature, or reports no preset modes at all,
        this method logs a debug message and returns without raising.
        Callers can pre-check with `supports_preset_mode`.
        """
        if not self.supports_preset_mode:
            _LOGGER.debug(
                "set_preset_mode() unsupported for %s; skipping (no FanEntityFeature.PRESET_MODE)",
                self.entity_id,
            )
            return
        modes = self.preset_modes
        if not modes:
            # Graceful degradation: device exposes no preset modes.
            _LOGGER.debug(
                "set_preset_mode() skipped for %s; device reports no preset_modes",
                self.entity_id,
            )
            return
        if mode not in modes:
            raise ValueError(
                f"preset_mode {mode!r} not in preset_modes {modes!r}",
            )
        await self._call_service("set_preset_mode", {"preset_mode": mode})

    async def set_direction(self, direction: str) -> None:
        """Set the fan rotation direction, when supported.

        Parameters
        ----------
        direction : str
            Either ``"forward"`` or ``"reverse"``.

        Raises
        ------
        ValueError
            If *direction* is not ``"forward"`` or ``"reverse"``.

        Notes
        -----
        Degrades safely: if the fan does not advertise the
        ``DIRECTION`` feature, this method logs a debug message and
        returns without raising. Callers can pre-check with
        `supports_direction`.
        """
        value = str(direction)
        if value not in _VALID_DIRECTIONS:
            raise ValueError(
                f"direction must be one of {sorted(_VALID_DIRECTIONS)!r}, got {direction!r}",
            )
        if not self.supports_direction:
            _LOGGER.debug(
                "set_direction() unsupported for %s; skipping (no FanEntityFeature.DIRECTION)",
                self.entity_id,
            )
            return
        await self._call_service("set_direction", {"direction": value})

    async def oscillate(self, oscillating: bool) -> None:
        """Toggle oscillation on or off, when supported.

        Parameters
        ----------
        oscillating : bool
            ``True`` to oscillate, ``False`` to stop oscillating.

        Notes
        -----
        Degrades safely: if the fan does not advertise the
        ``OSCILLATE`` feature, this method logs a debug message and
        returns without raising. Callers can pre-check with
        `supports_oscillate`.
        """
        if not self.supports_oscillate:
            _LOGGER.debug(
                "oscillate() unsupported for %s; skipping (no FanEntityFeature.OSCILLATE)",
                self.entity_id,
            )
            return
        await self._call_service("oscillate", {"oscillating": bool(oscillating)})


SPEC: DomainSpec[Fan] = register_domain(DomainSpec(name="fan", entity_cls=Fan))
"""The `DomainSpec` registered with the shared `DomainRegistry`."""
