"""``scene`` domain implementation."""

from __future__ import annotations

from typing import Any

from ..entity import Entity


class Scene(Entity):
    """A Home Assistant scene entity.

    Scenes are fire-and-forget: activating a scene applies a set of
    pre-defined entity states. There is no ``turn_off`` counterpart.
    The entity ``state`` is the ISO-8601 timestamp of the last activation
    (or ``"unavailable"`` / ``"unknown"`` when not applicable).
    """

    domain = "scene"

    # -- State properties --

    @property
    def last_activated(self) -> str | None:
        """ISO-8601 timestamp of the last activation.

        Returns
        -------
        str or None
            The timestamp string, or ``None`` if the scene state is
            ``"unavailable"`` or ``"unknown"``.
        """
        if self.state in ("unavailable", "unknown", None):
            return None
        return self.state

    @property
    def entity_ids(self) -> list[str]:
        """Entity IDs controlled by this scene.

        Returns
        -------
        list of str
            The entity IDs, or an empty list if not available.
        """
        val = self.attributes.get("entity_id")
        if isinstance(val, list):
            return [str(v) for v in val]
        return []

    @property
    def name(self) -> str | None:
        """Human-readable name of the scene.

        Returns
        -------
        str or None
            The friendly name, or ``None`` if not set.
        """
        val = self.attributes.get("friendly_name")
        return str(val) if val is not None else None

    @property
    def icon(self) -> str | None:
        """Icon identifier for the scene (e.g. ``"mdi:palette"``).

        Returns
        -------
        str or None
            The icon string, or ``None`` if not set.
        """
        val = self.attributes.get("icon")
        return str(val) if val is not None else None

    # -- Actions --

    async def activate(self, *, transition: float | None = None) -> None:
        """Activate the scene.

        Parameters
        ----------
        transition : float or None, optional
            Transition time in seconds (only affects lights that support it).
        """
        data: dict[str, Any] | None = None
        if transition is not None:
            data = {"transition": transition}
        await self._call_service("turn_on", data)

    # -- Listener decorators --

    def on_activate(self, func: Any) -> Any:
        """Register a listener that fires when the scene is activated.

        The listener fires whenever the scene's state changes (the timestamp
        is updated on each activation).

        Parameters
        ----------
        func : callable
            Callback with signature ``(old_state, new_state)``.

        Returns
        -------
        callable
            The same *func*, for use as a decorator.
        """
        return self._register_state_value_listener(func)
