"""``lock`` domain implementation."""

from __future__ import annotations

import logging
from typing import Any

from haclient.core.plugins import DomainSpec, register_domain
from haclient.entity.base import Entity

_LOGGER = logging.getLogger(__name__)

# Home Assistant ``LockEntityFeature`` bitmask.
# See homeassistant/components/lock/const.py.
_FEATURE_OPEN = 1


class Lock(Entity):
    """A Home Assistant lock entity.

    Provides intent-specific actions (``lock``, ``unlock``, ``open``)
    and state introspection (``is_locked``, ``is_unlocked``,
    ``is_locking``, ``is_unlocking``, ``is_jammed``) rather than
    exposing raw ``lock.lock`` / ``lock.unlock`` service calls.

    The ``open`` action is only available on lock hardware that
    advertises the ``OPEN`` (unlatch) feature via the
    ``supported_features`` attribute; on locks without it ``open`` is a
    no-op that logs a debug message, so user code does not break across
    heterogeneous lock backends. Callers can pre-check with
    `supports_open`.
    """

    domain = "lock"

    # -- Listener decorators ------------------------------------------

    def on_lock(self, func: Any) -> Any:
        """Register a listener for when the lock becomes locked.

        Parameters
        ----------
        func : callable
            Sync or async zero-argument callable invoked on every
            transition into the ``locked`` state.

        Returns
        -------
        callable
            The same *func*, returned for decorator use.
        """
        return self._register_state_transition_listener("locked", func)

    def on_unlock(self, func: Any) -> Any:
        """Register a listener for when the lock becomes unlocked.

        Parameters
        ----------
        func : callable
            Sync or async zero-argument callable invoked on every
            transition into the ``unlocked`` state.

        Returns
        -------
        callable
            The same *func*, returned for decorator use.
        """
        return self._register_state_transition_listener("unlocked", func)

    def on_jam(self, func: Any) -> Any:
        """Register a listener for when the lock jams.

        Parameters
        ----------
        func : callable
            Sync or async zero-argument callable invoked on every
            transition into the ``jammed`` state.

        Returns
        -------
        callable
            The same *func*, returned for decorator use.
        """
        return self._register_state_transition_listener("jammed", func)

    # -- State properties ---------------------------------------------

    @property
    def is_locked(self) -> bool:
        """Whether the lock is currently locked."""
        return self.state == "locked"

    @property
    def is_unlocked(self) -> bool:
        """Whether the lock is currently unlocked."""
        return self.state == "unlocked"

    @property
    def is_locking(self) -> bool:
        """Whether the lock is currently in the process of locking."""
        return self.state == "locking"

    @property
    def is_unlocking(self) -> bool:
        """Whether the lock is currently in the process of unlocking."""
        return self.state == "unlocking"

    @property
    def is_jammed(self) -> bool:
        """Whether the lock is currently jammed."""
        return self.state == "jammed"

    @property
    def supports_open(self) -> bool:
        """Whether the underlying lock hardware supports the ``open`` action.

        Returns
        -------
        bool
            ``True`` if the entity advertises the ``OPEN`` feature in
            its ``supported_features`` bitmask, otherwise ``False``.
        """
        features = self.attributes.get("supported_features")
        if not isinstance(features, int):
            return False
        return bool(features & _FEATURE_OPEN)

    # -- Actions ------------------------------------------------------

    async def lock(self) -> None:
        """Engage the lock."""
        await self._call_service("lock")

    async def unlock(self) -> None:
        """Release the lock."""
        await self._call_service("unlock")

    async def open(self) -> None:
        """Open (unlatch) the lock, if supported.

        Degrades safely: if the lock does not advertise the ``OPEN``
        feature, this method logs a debug message and returns without
        raising, so user code that targets a heterogeneous fleet of
        locks does not break on hardware that lacks an unlatch.

        Callers that need to know whether the action will actually be
        dispatched can check `supports_open` first.
        """
        if not self.supports_open:
            _LOGGER.debug(
                "open() unsupported for %s; skipping (no LockEntityFeature.OPEN)",
                self.entity_id,
            )
            return
        await self._call_service("open")


SPEC: DomainSpec[Lock] = register_domain(DomainSpec(name="lock", entity_cls=Lock))
"""The `DomainSpec` registered with the shared `DomainRegistry`."""
