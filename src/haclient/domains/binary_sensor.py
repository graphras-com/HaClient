"""``binary_sensor`` domain implementation (read-only)."""

from __future__ import annotations

from haclient.core.plugins import DomainSpec, register_domain
from haclient.entity.base import Entity, ValueChangeHandler


class BinarySensor(Entity):
    """A read-only Home Assistant binary sensor entity.

    Binary sensors represent boolean detection states (e.g. motion,
    door open). They are read-only; no actions are exposed. Listener
    names use ``on_activate`` / ``on_deactivate``.
    """

    domain = "binary_sensor"

    # -- Listener decorators ------------------------------------------

    def on_activate(self, func: ValueChangeHandler) -> ValueChangeHandler:
        """Register a listener for when the sensor activates (state ``on``).

        Parameters
        ----------
        func : callable
            Sync or async callable invoked with ``(old_state, new_state)``
            on every transition into the ``on`` state.

        Returns
        -------
        callable
            The same *func*, returned so the method can be used as a
            decorator.
        """
        return self._register_state_transition_listener("on", func)

    def on_deactivate(self, func: ValueChangeHandler) -> ValueChangeHandler:
        """Register a listener for when the sensor deactivates (state ``off``).

        Parameters
        ----------
        func : callable
            Sync or async callable invoked with ``(old_state, new_state)``
            on every transition into the ``off`` state.

        Returns
        -------
        callable
            The same *func*, returned so the method can be used as a
            decorator.
        """
        return self._register_state_transition_listener("off", func)

    # -- State properties ---------------------------------------------

    @property
    def is_on(self) -> bool:
        """Whether the binary sensor is in the ``on`` state."""
        return self.state == "on"

    @property
    def device_class(self) -> str | None:
        """Device class (e.g. ``"motion"``, ``"door"``)."""
        value = self.attributes.get("device_class")
        return str(value) if value is not None else None


SPEC: DomainSpec[BinarySensor] = register_domain(
    DomainSpec(name="binary_sensor", entity_cls=BinarySensor)
)
"""The `DomainSpec` registered with the shared `DomainRegistry`."""
