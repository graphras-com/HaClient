"""Entity registry.

The registry stores :class:`haclient.entity.Entity` instances keyed by their
``entity_id`` and supports lookup by short (object) name scoped to a domain.
It is owned by each :class:`haclient.client.HAClient` instance to avoid the
pitfalls of global singletons in test and multi-client scenarios.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING

from .exceptions import EntityNotFoundError

if TYPE_CHECKING:
    from .entity import Entity


class EntityRegistry:
    """In-memory mapping of ``entity_id`` → :class:`Entity`."""

    def __init__(self) -> None:
        self._entities: dict[str, Entity] = {}

    def register(self, entity: Entity) -> None:
        """Register ``entity`` (overwriting any existing entry)."""
        self._entities[entity.entity_id] = entity

    def unregister(self, entity_id: str) -> None:
        """Remove the entity identified by ``entity_id`` if present."""
        self._entities.pop(entity_id, None)

    def get(self, entity_id: str) -> Entity | None:
        """Return the entity for ``entity_id`` or ``None`` if missing."""
        return self._entities.get(entity_id)

    def require(self, entity_id: str) -> Entity:
        """Return the entity for ``entity_id`` or raise :class:`EntityNotFoundError`."""
        entity = self._entities.get(entity_id)
        if entity is None:
            raise EntityNotFoundError(f"Entity not found: {entity_id}")
        return entity

    def __contains__(self, entity_id: object) -> bool:
        return isinstance(entity_id, str) and entity_id in self._entities

    def __iter__(self) -> Iterator[Entity]:
        return iter(self._entities.values())

    def __len__(self) -> int:
        return len(self._entities)

    def clear(self) -> None:
        """Remove all registered entities."""
        self._entities.clear()

    def resolve(self, domain: str, name: str) -> str:
        """Resolve a short name to a full ``entity_id`` within ``domain``.

        ``name`` may be either:

        * the *object id* (``"livingroom"``), or
        * the fully-qualified ``entity_id`` (``"media_player.livingroom"``).

        Parameters
        ----------
        domain:
            The Home Assistant domain (e.g. ``"media_player"``).
        name:
            The short name or full entity id to resolve.
        """
        if "." in name:
            return name
        return f"{domain}.{name}"

    def in_domain(self, domain: str) -> list[Entity]:
        """Return all registered entities belonging to ``domain``."""
        prefix = f"{domain}."
        return [e for eid, e in self._entities.items() if eid.startswith(prefix)]
