"""``binary_sensor`` domain implementation (read-only)."""

from __future__ import annotations

from typing import Any

from ..entity import Entity


class BinarySensor(Entity):
    """A read-only Home Assistant binary sensor entity.

    Binary sensors represent boolean detection states (e.g. motion
    detected, door open). They are read-only -- no actions are exposed.
    Listener names use ``on_activate`` / ``on_deactivate`` to reflect
    that the sensor itself does not "turn on" or "turn off".
    """

    domain = "binary_sensor"

    # -- Listener decorators --

    def on_activate(self, func: Any) -> Any:
        """Register a listener for when the sensor activates (state becomes ``on``).

        Parameters
        ----------
        func : callable
            Callback with signature ``(old_state, new_state)``.

        Returns
        -------
        callable
            The same *func*, for use as a decorator.
        """
        return self._register_state_transition_listener("on", func)

    def on_deactivate(self, func: Any) -> Any:
        """Register a listener for when the sensor deactivates (state becomes ``off``).

        Parameters
        ----------
        func : callable
            Callback with signature ``(old_state, new_state)``.

        Returns
        -------
        callable
            The same *func*, for use as a decorator.
        """
        return self._register_state_transition_listener("off", func)

    # -- State properties --

    @property
    def is_on(self) -> bool:
        """Check whether the binary sensor is in the ``on`` state.

        Returns
        -------
        bool
            ``True`` if the sensor is active.
        """
        return self.state == "on"

    @property
    def device_class(self) -> str | None:
        """The device class (e.g. ``"motion"``, ``"door"``).

        Returns
        -------
        str or None
            The device class string, or ``None`` if not set.
        """
        value = self.attributes.get("device_class")
        return str(value) if value is not None else None
