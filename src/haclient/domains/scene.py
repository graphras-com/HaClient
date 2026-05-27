"""``scene`` domain implementation.

Scenes apply a pre-defined set of entity states in one shot.  They are
fire-and-forget: there is no ``turn_off`` counterpart.

Domain-level operations
-----------------------
Beyond per-entity actions, the scene domain exposes two collection-level
operations on the `DomainAccessor`:

* ``create(scene_id, entities, *, snapshot_entities=None) -> Scene`` —
  create (or update) a runtime scene helper.
* ``apply(entities, *, transition=None) -> None`` — apply a state
  combination without persisting it.

These are invoked as ``await ha.scene.create(...)`` and
``await ha.scene.apply(...)``. Per-entity access still works through the
usual ``ha.scene("name")`` / ``ha.scene["name"]`` syntax.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from haclient.core.plugins import DomainAccessor, DomainSpec, register_domain
from haclient.entity.base import Entity, ValueChangeHandler

if TYPE_CHECKING:
    from haclient.core.factory import EntityFactory


class Scene(Entity):
    """A Home Assistant scene entity.

    Activating a scene applies a set of pre-defined entity states.  The
    entity ``state`` is the ISO-8601 timestamp of the last activation
    (or ``"unavailable"`` / ``"unknown"`` when not applicable).
    """

    domain = "scene"

    # -- State properties ---------------------------------------------

    @property
    def last_activated(self) -> str | None:
        """ISO-8601 timestamp of the last activation, or ``None``."""
        if self.state in ("unavailable", "unknown", None):
            return None
        return self.state

    @property
    def entity_ids(self) -> list[str]:
        """Entity IDs controlled by this scene."""
        val = self.attributes.get("entity_id")
        if isinstance(val, list):
            return [str(v) for v in val]
        return []

    @property
    def name(self) -> str | None:
        """Human-readable name of the scene."""
        val = self.attributes.get("friendly_name")
        return str(val) if val is not None else None

    @property
    def icon(self) -> str | None:
        """Icon identifier for the scene (e.g. ``"mdi:palette"``)."""
        val = self.attributes.get("icon")
        return str(val) if val is not None else None

    # -- Actions ------------------------------------------------------

    async def activate(self, *, transition: float | None = None) -> None:
        """Activate the scene.

        Parameters
        ----------
        transition : float or None, optional
            Seconds over which entities supporting transitions should
            move to their scene state.
        """
        data: dict[str, Any] | None = None
        if transition is not None:
            data = {"transition": transition}
        await self._call_service("turn_on", data)

    async def delete(self) -> None:
        """Delete this dynamically-created scene."""
        await self._call_service("delete")

    # -- Listener decorators ------------------------------------------

    def on_activate(self, func: ValueChangeHandler) -> ValueChangeHandler:
        """Register a listener that fires when the scene is activated.

        Parameters
        ----------
        func : callable
            Sync or async callable invoked with ``(old_state, new_state)``
            ISO-8601 activation-timestamp strings whenever the scene is
            re-activated.

        Returns
        -------
        callable
            The same *func*, returned for decorator use.
        """
        return self._register_state_value_listener(func)


# -- Domain-level operations --------------------------------------------


async def _create(
    accessor: DomainAccessor[Scene],
    scene_id: str,
    entities: dict[str, dict[str, Any]],
    *,
    snapshot_entities: list[str] | None = None,
) -> Scene:
    """Create a runtime scene and return the corresponding `Scene`.

    Parameters
    ----------
    accessor : DomainAccessor
        The scene accessor (provided automatically by the binding).
    scene_id : str
        Object-id for the new scene (e.g. ``"romantic"`` →
        ``scene.romantic``).
    entities : dict
        Mapping of entity ids to state/attribute dicts.
    snapshot_entities : list of str or None, optional
        Entity ids whose current state should be captured.

    Returns
    -------
    Scene
        The newly created scene.
    """
    factory: EntityFactory = accessor._factory  # type: ignore[assignment]
    services = factory.services
    payload: dict[str, Any] = {"scene_id": scene_id, "entities": entities}
    if snapshot_entities is not None:
        payload["snapshot_entities"] = snapshot_entities
    await services.call("scene", "create", payload)
    return accessor[scene_id]


async def _apply(
    accessor: DomainAccessor[Scene],
    entities: dict[str, dict[str, Any]],
    *,
    transition: float | None = None,
) -> None:
    """Apply a scene-like state combination without persisting it.

    Parameters
    ----------
    accessor : DomainAccessor
        The scene accessor.
    entities : dict
        Mapping of entity ids to desired state/attribute dicts.
    transition : float or None, optional
        Transition seconds for entities that support it.
    """
    factory: EntityFactory = accessor._factory  # type: ignore[assignment]
    services = factory.services
    payload: dict[str, Any] = {"entities": entities}
    if transition is not None:
        payload["transition"] = transition
    await services.call("scene", "apply", payload)


SPEC: DomainSpec[Scene] = register_domain(
    DomainSpec(
        name="scene",
        entity_cls=Scene,
        operations={"create": _create, "apply": _apply},
    )
)
"""The `DomainSpec` registered with the shared `DomainRegistry`."""
