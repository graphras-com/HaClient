"""``scene`` domain implementation.

Scenes apply a pre-defined set of entity states in one shot.  They are
fire-and-forget: there is no ``turn_off`` counterpart.

Domain-level operations
-----------------------
Beyond per-entity actions, the scene domain exposes two collection-level
operations on the `SceneAccessor` (returned by ``ha.scene``):

* ``await ha.scene.create(scene_id, entities, *, snapshot_entities=None)``
  — create (or update) a runtime scene helper, returning a `Scene`.
* ``await ha.scene.apply(entities, *, transition=None)``
  — apply a state combination without persisting it.

Per-entity access still works through the usual
``ha.scene("name")`` / ``ha.scene["name"]`` syntax.
"""

from __future__ import annotations

from typing import Any

from haclient.core.plugins import DomainAccessor, DomainSpec, register_domain
from haclient.entity.base import Entity, ValueChangeHandler


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
        """Human-readable name of the scene.

        Returns
        -------
        str or None
            The HA ``friendly_name`` attribute, or ``None`` when the
            entity does not advertise one. Note that this property
            deliberately does not return the scene's ``entity_id``
            or object-id slug.
        """
        val = self.attributes.get("friendly_name")
        return str(val) if val is not None else None

    @property
    def icon(self) -> str | None:
        """Icon identifier for the scene.

        Returns
        -------
        str or None
            The raw HA ``icon`` attribute, typically a Material Design
            Icons identifier of the form ``"mdi:<name>"``. ``None`` when
            the entity does not advertise an icon.
        """
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
        """Delete this dynamically-created scene.

        Invokes the ``scene.delete`` Home Assistant service. This is
        only meaningful for scenes created at runtime via
        `SceneAccessor.create`; static scenes defined in YAML cannot be
        deleted this way and Home Assistant will surface an error.

        Notes
        -----
        The local entity object is **not** removed from the registry by
        this call. Callers that want to discard the proxy should also
        drop their reference.

        Raises
        ------
        CommandError
            If Home Assistant rejects the call (for example, the scene
            is YAML-defined and not deletable).
        HTTPError
            If the REST call returns a non-2xx response.
        TimeoutError
            If the call exceeds the configured request timeout.
        ConnectionClosedError
            If the WebSocket disconnects mid-call.
        """
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


# -- Typed domain accessor ----------------------------------------------


class SceneAccessor(DomainAccessor[Scene]):
    """Typed domain accessor for the ``scene`` domain.

    Returned by ``ha.scene``. Provides statically-typed collection-level
    operations in addition to the standard entity lookup methods inherited
    from `DomainAccessor`.
    """

    async def create(
        self,
        scene_id: str,
        entities: dict[str, dict[str, Any]],
        *,
        snapshot_entities: list[str] | None = None,
    ) -> Scene:
        """Create (or update) a runtime scene helper.

        Parameters
        ----------
        scene_id : str
            Object-id for the new scene (e.g. ``"romantic"`` →
            ``scene.romantic``).
        entities : dict
            Mapping of entity ids to target state/attribute dicts.
        snapshot_entities : list of str or None, optional
            Entity ids whose current state should be captured instead of
            providing an explicit state dict.

        Returns
        -------
        Scene
            The newly created (or updated) scene entity.
        """
        from haclient.core.factory import EntityFactory

        factory = self.factory
        assert isinstance(factory, EntityFactory)
        payload: dict[str, Any] = {"scene_id": scene_id, "entities": entities}
        if snapshot_entities is not None:
            payload["snapshot_entities"] = snapshot_entities
        await factory.services.call("scene", "create", payload)
        return self[scene_id]

    async def apply(
        self,
        entities: dict[str, dict[str, Any]],
        *,
        transition: float | None = None,
    ) -> None:
        """Apply a scene-like state combination without persisting it.

        Parameters
        ----------
        entities : dict
            Mapping of entity ids to desired state/attribute dicts.
        transition : float or None, optional
            Transition seconds for entities that support it.
        """
        from haclient.core.factory import EntityFactory

        factory = self.factory
        assert isinstance(factory, EntityFactory)
        payload: dict[str, Any] = {"entities": entities}
        if transition is not None:
            payload["transition"] = transition
        await factory.services.call("scene", "apply", payload)


SPEC: DomainSpec[Scene] = register_domain(
    DomainSpec(
        name="scene",
        entity_cls=Scene,
        accessor_cls=SceneAccessor,
    )
)
"""The `DomainSpec` registered with the shared `DomainRegistry`."""
