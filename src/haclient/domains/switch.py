"""``switch`` domain implementation."""

from __future__ import annotations

from haclient.core.plugins import DomainSpec, register_domain
from haclient.entity.base import Entity, ValueChangeHandler


class Switch(Entity):
    """A Home Assistant switch entity.

    Switches are binary devices that can be turned on or off. The public
    API uses ``on()`` / ``off()`` / ``toggle()`` as intent-specific names
    rather than the raw HA ``turn_on`` / ``turn_off`` service names.
    """

    domain = "switch"

    # -- Listener decorators ------------------------------------------

    def on_turn_on(self, func: ValueChangeHandler) -> ValueChangeHandler:
        """Register a listener for when the switch turns on.

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
        """Register a listener for when the switch turns off.

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

    # -- State properties ---------------------------------------------

    @property
    def is_on(self) -> bool:
        """Whether the switch is currently on.

        Returns
        -------
        bool
            ``True`` when the cached entity ``state`` is exactly
            ``"on"``; ``False`` for ``"off"`` and any unknown,
            unavailable, or transitional value.
        """
        return self.state == "on"

    # -- Actions ------------------------------------------------------

    async def on(self) -> None:
        """Activate the switch.

        Invokes the ``switch.turn_on`` Home Assistant service via the
        configured routing policy (REST or WebSocket).

        Raises
        ------
        CommandError
            If Home Assistant rejects the service call (WebSocket path).
        HTTPError
            If the REST call returns a non-2xx response (REST path).
        TimeoutError
            If the call exceeds the configured request timeout.
        ConnectionClosedError
            If the WebSocket disconnects mid-call.
        """
        await self._call_service("turn_on")

    async def off(self) -> None:
        """Deactivate the switch.

        Invokes the ``switch.turn_off`` Home Assistant service.

        Raises
        ------
        CommandError
            If Home Assistant rejects the service call.
        HTTPError
            If the REST call returns a non-2xx response.
        TimeoutError
            If the call exceeds the configured request timeout.
        ConnectionClosedError
            If the WebSocket disconnects mid-call.
        """
        await self._call_service("turn_off")

    async def toggle(self) -> None:
        """Toggle the switch state.

        Invokes the ``switch.toggle`` Home Assistant service.

        Raises
        ------
        CommandError
            If Home Assistant rejects the service call.
        HTTPError
            If the REST call returns a non-2xx response.
        TimeoutError
            If the call exceeds the configured request timeout.
        ConnectionClosedError
            If the WebSocket disconnects mid-call.
        """
        await self._call_service("toggle")


SPEC: DomainSpec[Switch] = register_domain(DomainSpec(name="switch", entity_cls=Switch))
"""The `DomainSpec` registered with the shared `DomainRegistry`."""
