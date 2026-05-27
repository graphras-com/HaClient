"""``vacuum`` domain implementation."""

from __future__ import annotations

import logging
from typing import Any

from haclient.core.plugins import DomainSpec, register_domain
from haclient.entity.base import Entity, ValueChangeHandler

_LOGGER = logging.getLogger(__name__)

# Home Assistant ``VacuumEntityFeature`` bitmask.
# See homeassistant/components/vacuum/const.py.
_FEATURE_TURN_ON = 1
_FEATURE_TURN_OFF = 2
_FEATURE_PAUSE = 4
_FEATURE_STOP = 8
_FEATURE_RETURN_HOME = 16
_FEATURE_FAN_SPEED = 32
_FEATURE_BATTERY = 64
_FEATURE_STATUS = 128
_FEATURE_SEND_COMMAND = 256
_FEATURE_LOCATE = 512
_FEATURE_CLEAN_SPOT = 1024
_FEATURE_MAP = 2048
_FEATURE_STATE = 4096
_FEATURE_START = 8192

# Canonical Home Assistant vacuum states.
_STATE_CLEANING = "cleaning"
_STATE_DOCKED = "docked"
_STATE_IDLE = "idle"
_STATE_PAUSED = "paused"
_STATE_RETURNING = "returning"
_STATE_ERROR = "error"


class Vacuum(Entity):
    """A Home Assistant vacuum entity.

    Provides intent-specific actions (``start``, ``pause``, ``stop``,
    ``return_to_base``, ``locate``, ``set_fan_speed``, ``send_command``,
    ``clean_spot``) and structured state introspection (``is_cleaning``,
    ``is_docked``, ``is_idle``, ``is_paused``, ``is_returning``,
    ``is_error``, ``battery_level``, ``fan_speed``, ``fan_speed_list``)
    rather than exposing raw service calls.

    Methods that depend on optional vacuum capabilities degrade safely:
    if the underlying hardware does not advertise the relevant
    ``VacuumEntityFeature`` bit in ``supported_features``, the call
    becomes a no-op that logs a debug message instead of raising. This
    keeps user code portable across heterogeneous fleets. Callers that
    need to know whether an action will actually be dispatched can
    pre-check with the ``supports_*`` properties.
    """

    domain = "vacuum"

    # -- Listener decorators ------------------------------------------

    def on_start(self, func: ValueChangeHandler) -> ValueChangeHandler:
        """Register a listener for when the vacuum starts cleaning.

        Parameters
        ----------
        func : callable
            Sync or async callable invoked with ``(old_state, new_state)``
            on every transition into the ``cleaning`` state.

        Returns
        -------
        callable
            The same *func*, returned for decorator use.
        """
        return self._register_state_transition_listener(_STATE_CLEANING, func)

    def on_dock(self, func: ValueChangeHandler) -> ValueChangeHandler:
        """Register a listener for when the vacuum returns to the dock.

        Parameters
        ----------
        func : callable
            Sync or async callable invoked with ``(old_state, new_state)``
            on every transition into the ``docked`` state.

        Returns
        -------
        callable
            The same *func*, returned for decorator use.
        """
        return self._register_state_transition_listener(_STATE_DOCKED, func)

    def on_error(self, func: ValueChangeHandler) -> ValueChangeHandler:
        """Register a listener for when the vacuum enters the error state.

        Parameters
        ----------
        func : callable
            Sync or async callable invoked with ``(old_state, new_state)``
            on every transition into the ``error`` state.

        Returns
        -------
        callable
            The same *func*, returned for decorator use.
        """
        return self._register_state_transition_listener(_STATE_ERROR, func)

    def on_battery_change(self, func: ValueChangeHandler) -> ValueChangeHandler:
        """Register a listener for battery level changes.

        Parameters
        ----------
        func : callable
            Callable invoked with ``(old_value, new_value)`` whenever
            the ``battery_level`` attribute (0-100) changes.

        Returns
        -------
        callable
            The same *func*, returned for decorator use.
        """
        return self._register_attr_listener("battery_level", func)

    def on_fan_speed_change(self, func: ValueChangeHandler) -> ValueChangeHandler:
        """Register a listener for fan-speed changes.

        Parameters
        ----------
        func : callable
            Callable invoked with ``(old_value, new_value)`` whenever
            the ``fan_speed`` attribute changes.

        Returns
        -------
        callable
            The same *func*, returned for decorator use.
        """
        return self._register_attr_listener("fan_speed", func)

    # -- State properties ---------------------------------------------

    @property
    def is_cleaning(self) -> bool:
        """Whether the vacuum is currently cleaning."""
        return self.state == _STATE_CLEANING

    @property
    def is_docked(self) -> bool:
        """Whether the vacuum is currently docked."""
        return self.state == _STATE_DOCKED

    @property
    def is_idle(self) -> bool:
        """Whether the vacuum is currently idle."""
        return self.state == _STATE_IDLE

    @property
    def is_paused(self) -> bool:
        """Whether the vacuum is currently paused."""
        return self.state == _STATE_PAUSED

    @property
    def is_returning(self) -> bool:
        """Whether the vacuum is currently returning to the dock."""
        return self.state == _STATE_RETURNING

    @property
    def is_error(self) -> bool:
        """Whether the vacuum is currently in an error state."""
        return self.state == _STATE_ERROR

    @property
    def battery_level(self) -> int | None:
        """Battery charge percentage (0--100) or ``None`` if unsupported."""
        value = self.attributes.get("battery_level")
        return int(value) if isinstance(value, (int, float)) else None

    @property
    def fan_speed(self) -> str | None:
        """Current fan speed label, or ``None`` if unsupported."""
        value = self.attributes.get("fan_speed")
        return str(value) if isinstance(value, str) else None

    @property
    def fan_speed_list(self) -> list[str]:
        """Available fan-speed labels, or an empty list if unsupported."""
        value = self.attributes.get("fan_speed_list")
        if not isinstance(value, list):
            return []
        return [str(item) for item in value if isinstance(item, str)]

    def _has_feature(self, mask: int) -> bool:
        """Return ``True`` when ``supported_features`` advertises *mask*.

        Parameters
        ----------
        mask : int
            ``VacuumEntityFeature`` bit to test for.

        Returns
        -------
        bool
            ``True`` if the entity advertises *mask* in its
            ``supported_features`` bitmask, otherwise ``False``.
        """
        features = self.attributes.get("supported_features")
        if not isinstance(features, int):
            return False
        return bool(features & mask)

    @property
    def supports_start(self) -> bool:
        """Whether the vacuum advertises ``START`` support."""
        return self._has_feature(_FEATURE_START)

    @property
    def supports_pause(self) -> bool:
        """Whether the vacuum advertises ``PAUSE`` support."""
        return self._has_feature(_FEATURE_PAUSE)

    @property
    def supports_stop(self) -> bool:
        """Whether the vacuum advertises ``STOP`` support."""
        return self._has_feature(_FEATURE_STOP)

    @property
    def supports_return_home(self) -> bool:
        """Whether the vacuum advertises ``RETURN_HOME`` support."""
        return self._has_feature(_FEATURE_RETURN_HOME)

    @property
    def supports_locate(self) -> bool:
        """Whether the vacuum advertises ``LOCATE`` support."""
        return self._has_feature(_FEATURE_LOCATE)

    @property
    def supports_fan_speed(self) -> bool:
        """Whether the vacuum advertises ``FAN_SPEED`` support."""
        return self._has_feature(_FEATURE_FAN_SPEED)

    @property
    def supports_send_command(self) -> bool:
        """Whether the vacuum advertises ``SEND_COMMAND`` support."""
        return self._has_feature(_FEATURE_SEND_COMMAND)

    @property
    def supports_clean_spot(self) -> bool:
        """Whether the vacuum advertises ``CLEAN_SPOT`` support."""
        return self._has_feature(_FEATURE_CLEAN_SPOT)

    # -- Actions ------------------------------------------------------

    async def start(self) -> None:
        """Start (or resume) cleaning.

        Degrades safely: if the vacuum does not advertise the ``START``
        feature, this method logs a debug message and returns without
        raising. Callers can pre-check with `supports_start`.
        """
        if not self.supports_start:
            _LOGGER.debug(
                "start() unsupported for %s; skipping (no VacuumEntityFeature.START)",
                self.entity_id,
            )
            return
        await self._call_service("start")

    async def pause(self) -> None:
        """Pause the current cleaning cycle.

        Degrades safely: if the vacuum does not advertise the ``PAUSE``
        feature, this method logs a debug message and returns without
        raising. Callers can pre-check with `supports_pause`.
        """
        if not self.supports_pause:
            _LOGGER.debug(
                "pause() unsupported for %s; skipping (no VacuumEntityFeature.PAUSE)",
                self.entity_id,
            )
            return
        await self._call_service("pause")

    async def stop(self) -> None:
        """Stop the current cleaning cycle.

        Degrades safely: if the vacuum does not advertise the ``STOP``
        feature, this method logs a debug message and returns without
        raising. Callers can pre-check with `supports_stop`.
        """
        if not self.supports_stop:
            _LOGGER.debug(
                "stop() unsupported for %s; skipping (no VacuumEntityFeature.STOP)",
                self.entity_id,
            )
            return
        await self._call_service("stop")

    async def return_to_base(self) -> None:
        """Send the vacuum back to its dock.

        Degrades safely: if the vacuum does not advertise the
        ``RETURN_HOME`` feature, this method logs a debug message and
        returns without raising. Callers can pre-check with
        `supports_return_home`.
        """
        if not self.supports_return_home:
            _LOGGER.debug(
                "return_to_base() unsupported for %s; skipping "
                "(no VacuumEntityFeature.RETURN_HOME)",
                self.entity_id,
            )
            return
        await self._call_service("return_to_base")

    async def locate(self) -> None:
        """Make the vacuum emit a locator sound, if supported.

        Degrades safely: if the vacuum does not advertise the ``LOCATE``
        feature, this method logs a debug message and returns without
        raising. Callers can pre-check with `supports_locate`.
        """
        if not self.supports_locate:
            _LOGGER.debug(
                "locate() unsupported for %s; skipping (no VacuumEntityFeature.LOCATE)",
                self.entity_id,
            )
            return
        await self._call_service("locate")

    async def clean_spot(self) -> None:
        """Perform a spot-cleaning cycle, if supported.

        Degrades safely: if the vacuum does not advertise the
        ``CLEAN_SPOT`` feature, this method logs a debug message and
        returns without raising. Callers can pre-check with
        `supports_clean_spot`.
        """
        if not self.supports_clean_spot:
            _LOGGER.debug(
                "clean_spot() unsupported for %s; skipping (no VacuumEntityFeature.CLEAN_SPOT)",
                self.entity_id,
            )
            return
        await self._call_service("clean_spot")

    async def set_fan_speed(self, speed: str) -> None:
        """Set the vacuum's fan speed, if supported.

        Parameters
        ----------
        speed : str
            Fan-speed label. Should be one of the values reported in
            the entity's ``fan_speed_list`` attribute.

        Notes
        -----
        Degrades safely: if the vacuum does not advertise the
        ``FAN_SPEED`` feature, this method logs a debug message and
        returns without raising. Callers can pre-check with
        `supports_fan_speed`.
        """
        if not self.supports_fan_speed:
            _LOGGER.debug(
                "set_fan_speed() unsupported for %s; skipping (no VacuumEntityFeature.FAN_SPEED)",
                self.entity_id,
            )
            return
        await self._call_service("set_fan_speed", {"fan_speed": str(speed)})

    async def send_command(
        self,
        command: str,
        params: dict[str, Any] | None = None,
    ) -> None:
        """Send a vendor-specific command to the vacuum, if supported.

        Parameters
        ----------
        command : str
            Vendor-specific command name to send.
        params : dict or None, optional
            Optional parameters dictionary forwarded verbatim to Home
            Assistant alongside the command.

        Notes
        -----
        Degrades safely: if the vacuum does not advertise the
        ``SEND_COMMAND`` feature, this method logs a debug message and
        returns without raising. Callers can pre-check with
        `supports_send_command`.
        """
        if not self.supports_send_command:
            _LOGGER.debug(
                "send_command() unsupported for %s; skipping (no VacuumEntityFeature.SEND_COMMAND)",
                self.entity_id,
            )
            return
        data: dict[str, Any] = {"command": str(command)}
        if params is not None:
            data["params"] = dict(params)
        await self._call_service("send_command", data)


SPEC: DomainSpec[Vacuum] = register_domain(DomainSpec(name="vacuum", entity_cls=Vacuum))
"""The `DomainSpec` registered with the shared `DomainRegistry`."""
