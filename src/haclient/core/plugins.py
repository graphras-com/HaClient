"""Domain plugin registry and accessor base.

Adding a new domain to HaClient is done by creating an `Entity` subclass
and registering a `DomainSpec`. The core never imports specific domains;
it iterates the spec registry instead.

A `DomainAccessor` is the object returned by ``ha.<domain>`` (e.g.
``ha.light`` or ``ha.scene``). It provides:

* ``__call__(name)`` and ``__getitem__(name)`` for entity lookup.
* Domain-level operations registered by the spec via ``operations``.

Third-party plugins can ship additional domains by exposing an entry
point under the ``haclient.domains`` group; see
`DomainRegistry.load_entry_points`.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from importlib import metadata
from typing import TYPE_CHECKING, Any, Generic, TypeVar, cast

from haclient.exceptions import HAClientError

if TYPE_CHECKING:
    from haclient.entity.base import Entity

_LOGGER = logging.getLogger(__name__)

E = TypeVar("E", bound="Entity")

DomainEventHandler = Callable[["Entity", str, dict[str, Any]], None]
"""Per-domain handler invoked for non-``state_changed`` events.

Receives the entity instance, the event_type string, and the raw event
data dictionary. Used by domains that need direct event routing (e.g.
the ``timer`` domain consuming ``timer.finished`` / ``timer.cancelled``).
"""


@dataclass(frozen=True)
class DomainSpec(Generic[E]):
    """Declarative description of a Home Assistant domain.

    Built-in domains live in `haclient.domains.*` and register a spec at
    import time. Third-party packages can register additional domains via
    the ``haclient.domains`` entry-point group.

    Attributes
    ----------
    name : str
        The HA domain name (e.g. ``"light"``).
    entity_cls : type[Entity]
        The entity class instantiated for this domain.
    accessor : str
        Attribute name on the `HAClient` facade. Defaults to *name*.
    event_subscriptions : tuple of str
        Additional HA event types this domain wants delivered, beyond
        the always-on ``state_changed`` subscription.
    on_event : callable or None
        Per-domain event handler (see `DomainEventHandler`).
    operations : dict
        Domain-level async operations registered on the
        `DomainAccessor`. Each value is an async callable; it will be
        bound to the accessor so the first positional argument *is* the
        accessor instance.
    """

    name: str
    entity_cls: type[E]
    accessor: str = ""
    event_subscriptions: tuple[str, ...] = ()
    on_event: DomainEventHandler | None = None
    operations: dict[str, Callable[..., Any]] = field(default_factory=dict)

    def accessor_name(self) -> str:
        """Return the accessor attribute name (defaults to ``name``)."""
        return self.accessor or self.name


class DomainAccessor(Generic[E]):
    """Runtime facade for one domain.

    Returned by ``HAClient.<accessor>``. Exposes:

    * Lookup by short name: ``ha.light("kitchen")`` or ``ha.light["kitchen"]``.
    * Domain-level operations registered on the spec, bound to this accessor:
      ``await ha.scene.create("romantic", ...)``.

    Parameters
    ----------
    spec : DomainSpec
        The spec describing this domain.
    factory : EntityFactory
        Factory used to create entity instances on demand.
    """

    def __init__(self, spec: DomainSpec[E], factory: EntityFactoryProtocol) -> None:
        self._spec = spec
        self._factory = factory
        for op_name, op in spec.operations.items():
            # Bind each operation as an attribute on the instance.
            setattr(self, op_name, self._bind(op))

    @property
    def spec(self) -> DomainSpec[E]:
        """Return the underlying `DomainSpec`."""
        return self._spec

    def _bind(self, op: Callable[..., Any]) -> Callable[..., Any]:
        """Bind a domain operation to this accessor.

        Each operation is invoked with the accessor as the first argument,
        analogous to a method receiving ``self``. Async operations remain
        coroutine functions so introspection (e.g. by `_SyncProxy`) keeps
        working.
        """
        import asyncio

        if asyncio.iscoroutinefunction(op):

            async def async_bound(*args: Any, **kwargs: Any) -> Any:
                return await op(self, *args, **kwargs)

            async_bound.__name__ = getattr(op, "__name__", "operation")
            async_bound.__doc__ = op.__doc__
            return async_bound

        def bound(*args: Any, **kwargs: Any) -> Any:
            return op(self, *args, **kwargs)

        bound.__name__ = getattr(op, "__name__", "operation")
        bound.__doc__ = op.__doc__
        return bound

    def __call__(self, name: str) -> E:
        """Return the entity with short *name*, creating it if needed."""
        return cast("E", self._factory.get_or_create(self._spec, name))

    def __getitem__(self, name: str) -> E:
        """Return the entity with short *name*, creating it if needed."""
        return cast("E", self._factory.get_or_create(self._spec, name))

    def all(self) -> list[E]:
        """Return every entity currently registered for this domain.

        Returns
        -------
        list of Entity
            All entities whose id starts with ``"<domain>."``.
        """
        return cast("list[E]", self._factory.in_domain(self._spec))


class EntityFactoryProtocol:
    """Structural type used by `DomainAccessor`.

    Defined as a regular class to keep imports simple. Concrete
    `EntityFactory` lives in `haclient.core.factory`.
    """

    def get_or_create(self, spec: DomainSpec[Any], name: str) -> Any:  # pragma: no cover
        """Return the entity for *spec*/*name*, creating it on first use.

        Parameters
        ----------
        spec : DomainSpec
            The spec describing the entity's domain.
        name : str
            Short entity name or full ``<domain>.<name>`` entity id.

        Returns
        -------
        Entity
            The (possibly newly created) entity instance.
        """
        raise NotImplementedError

    def in_domain(self, spec: DomainSpec[Any]) -> list[Any]:  # pragma: no cover
        """Return every registered entity belonging to *spec*'s domain.

        Parameters
        ----------
        spec : DomainSpec
            The spec describing the domain to enumerate.

        Returns
        -------
        list of Entity
            All entities currently in the registry whose id starts with
            ``"<spec.name>."``.
        """
        raise NotImplementedError


class DomainRegistry:
    """Mutable registry of `DomainSpec` keyed by domain name.

    Built-in domains register on import (see `haclient.domains.__init__`).
    Third-party domains can be discovered via entry points using
    `load_entry_points`.
    """

    _instance: DomainRegistry | None = None

    def __init__(self) -> None:
        self._specs: dict[str, DomainSpec[Any]] = {}

    @classmethod
    def shared(cls) -> DomainRegistry:
        """Return the process-wide shared registry instance.

        Built-in domain modules use this when they register at import
        time. `HAClient` reads from the same instance unless a custom
        registry is passed explicitly.
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(self, spec: DomainSpec[Any]) -> None:
        """Register *spec*, raising on duplicate domain names.

        Parameters
        ----------
        spec : DomainSpec
            The spec to register.

        Raises
        ------
        HAClientError
            If a spec with the same ``name`` is already registered for a
            different entity class. Re-registering the same class is a
            no-op (this happens when a module is imported twice).
        """
        existing = self._specs.get(spec.name)
        if existing is not None:
            if existing.entity_cls is spec.entity_cls:
                self._specs[spec.name] = spec
                return
            raise HAClientError(
                f"Domain {spec.name!r} already registered with "
                f"{existing.entity_cls.__name__}; cannot replace with "
                f"{spec.entity_cls.__name__}"
            )
        self._specs[spec.name] = spec

    def unregister(self, name: str) -> None:
        """Remove the spec registered under *name*, if any."""
        self._specs.pop(name, None)

    def get(self, name: str) -> DomainSpec[Any]:
        """Return the spec registered for *name* or raise.

        Parameters
        ----------
        name : str
            The HA domain name to look up.

        Returns
        -------
        DomainSpec
            The registered spec.

        Raises
        ------
        HAClientError
            If no domain *name* is registered.
        """
        spec = self._specs.get(name)
        if spec is None:
            raise HAClientError(
                f"Unknown domain {name!r}; ensure the corresponding plugin is loaded"
            )
        return spec

    def __contains__(self, name: object) -> bool:
        return isinstance(name, str) and name in self._specs

    def __iter__(self) -> Iterator[DomainSpec[Any]]:
        return iter(self._specs.values())

    def names(self) -> list[str]:
        """Return all registered domain names."""
        return list(self._specs.keys())

    def filter(self, names: Iterable[str]) -> list[DomainSpec[Any]]:
        """Return only the specs whose names are in *names*.

        Parameters
        ----------
        names : iterable of str
            Allowed domain names. Unknown names are silently ignored.

        Returns
        -------
        list of DomainSpec
            Registered specs filtered to the requested subset, in
            registration order.
        """
        wanted = set(names)
        return [s for s in self._specs.values() if s.name in wanted]

    def load_entry_points(self, group: str = "haclient.domains") -> list[str]:
        """Discover and load third-party domain plugins.

        Each entry point is loaded inside a ``try/except`` so a single
        broken plugin cannot prevent the rest from loading. The names
        of the entry points that loaded successfully are returned.

        Parameters
        ----------
        group : str, optional
            The entry-point group name. Defaults to ``"haclient.domains"``.

        Returns
        -------
        list of str
            Names of the entry points that loaded without raising.
        """
        loaded: list[str] = []
        try:
            entry_points = metadata.entry_points(group=group)
        except Exception:  # pragma: no cover - defensive
            _LOGGER.exception("Failed to enumerate entry points for %s", group)
            return loaded
        for ep in entry_points:
            try:
                ep.load()
                loaded.append(ep.name)
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Failed to load haclient domain plugin %r", ep.name)
        return loaded


def register_domain(spec: DomainSpec[Any]) -> DomainSpec[Any]:
    """Register *spec* on the shared registry.

    This is the canonical entry point for both built-in and third-party
    domain modules.

    Parameters
    ----------
    spec : DomainSpec
        The spec to register.

    Returns
    -------
    DomainSpec
        The same spec, for convenience.
    """
    DomainRegistry.shared().register(spec)
    return spec
