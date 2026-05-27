"""``valve`` domain implementation."""

from __future__ import annotations

import logging

from haclient.core.plugins import DomainSpec, register_domain
from haclient.entity.base import Entity, ValueChangeHandler

_LOGGER = logging.getLogger(__name__)

# Home Assistant ``ValveEntityFeature`` bitmask.
# See homeassistant/components/valve/const.py.
_FEATURE_OPEN = 1
_FEATURE_CLOSE = 2
_FEATURE_SET_POSITION = 4
_FEATURE_STOP = 8


class Valve(Entity):
    """A Home Assistant valve entity (water shutoff, gas, irrigation).

    Mirrors the typed `Cover` shape because valves share the same
    open/close/position model, but is exposed as a distinct domain to
    preserve the safety-critical semantics of valves (water mains, gas
    lines) and to match Home Assistant's separate ``valve`` domain
    introduced in 2023.9.

    Uses intent-specific action names (``open``, ``close``, ``stop``,
    ``set_position``) rather than raw HA service names. The
    ``set_position`` and ``stop`` actions degrade safely on valves that
    only advertise binary open/close support: they log a debug message
    and return without raising, so user code targeting a heterogeneous
    fleet of valves does not break. Callers that need to know whether
    the action will actually be dispatched can pre-check with
    `supports_set_position` or `supports_stop`.
    """

    domain = "valve"

    # -- Listener decorators ------------------------------------------

    def on_open(self, func: ValueChangeHandler) -> ValueChangeHandler:
        """Register a listener for when the valve opens.

        Parameters
        ----------
        func : callable
            Sync or async callable invoked with ``(old_state, new_state)``
            on every transition into the ``open`` state.

        Returns
        -------
        callable
            The same *func*, returned for decorator use.
        """
        return self._register_state_transition_listener("open", func)

    def on_close(self, func: ValueChangeHandler) -> ValueChangeHandler:
        """Register a listener for when the valve closes.

        Parameters
        ----------
        func : callable
            Sync or async callable invoked with ``(old_state, new_state)``
            on every transition into the ``closed`` state.

        Returns
        -------
        callable
            The same *func*, returned for decorator use.
        """
        return self._register_state_transition_listener("closed", func)

    def on_position_change(self, func: ValueChangeHandler) -> ValueChangeHandler:
        """Register a listener for position changes.

        Parameters
        ----------
        func : callable
            Callable invoked with ``(old_value, new_value)`` whenever
            the ``current_position`` attribute (0-100) changes.

        Returns
        -------
        callable
            The same *func*, returned for decorator use.
        """
        return self._register_attr_listener("current_position", func)

    # -- State properties ---------------------------------------------

    @property
    def is_open(self) -> bool:
        """Whether the valve is currently open."""
        return self.state == "open"

    @property
    def is_closed(self) -> bool:
        """Whether the valve is currently closed."""
        return self.state == "closed"

    @property
    def is_opening(self) -> bool:
        """Whether the valve is currently in the process of opening."""
        return self.state == "opening"

    @property
    def is_closing(self) -> bool:
        """Whether the valve is currently in the process of closing."""
        return self.state == "closing"

    @property
    def current_position(self) -> int | None:
        """Current position (0--100) or ``None`` if unsupported."""
        value = self.attributes.get("current_position")
        return int(value) if isinstance(value, (int, float)) else None

    def _has_feature(self, mask: int) -> bool:
        """Return ``True`` when ``supported_features`` advertises *mask*.

        Parameters
        ----------
        mask : int
            ``ValveEntityFeature`` bit to test for.

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
    def supports_set_position(self) -> bool:
        """Whether the valve advertises ``SET_POSITION`` support."""
        return self._has_feature(_FEATURE_SET_POSITION)

    @property
    def supports_stop(self) -> bool:
        """Whether the valve advertises ``STOP`` support."""
        return self._has_feature(_FEATURE_STOP)

    # -- Actions ------------------------------------------------------

    async def open(self) -> None:
        """Open the valve fully."""
        await self._call_service("open_valve")

    async def close(self) -> None:
        """Close the valve fully."""
        await self._call_service("close_valve")

    async def stop(self) -> None:
        """Stop movement of the valve, if supported.

        Degrades safely: if the valve does not advertise the ``STOP``
        feature, this method logs a debug message and returns without
        raising. Callers can pre-check with `supports_stop`.
        """
        if not self.supports_stop:
            _LOGGER.debug(
                "stop() unsupported for %s; skipping (no ValveEntityFeature.STOP)",
                self.entity_id,
            )
            return
        await self._call_service("stop_valve")

    async def set_position(self, position: int) -> None:
        """Set the valve position, if supported.

        Parameters
        ----------
        position : int
            Target position (``0`` = fully closed, ``100`` = fully
            open), coerced to ``int``.

        Notes
        -----
        Degrades safely: if the valve does not advertise the
        ``SET_POSITION`` feature (e.g. a binary water shutoff), this
        method logs a debug message and returns without raising.
        Callers can pre-check with `supports_set_position`.
        """
        if not self.supports_set_position:
            _LOGGER.debug(
                "set_position() unsupported for %s; skipping (no ValveEntityFeature.SET_POSITION)",
                self.entity_id,
            )
            return
        await self._call_service("set_valve_position", {"position": int(position)})

    async def toggle(self) -> None:
        """Toggle open/close state."""
        await self._call_service("toggle")


SPEC: DomainSpec[Valve] = register_domain(DomainSpec(name="valve", entity_cls=Valve))
"""The `DomainSpec` registered with the shared `DomainRegistry`."""
