<a id="haclient.registry"></a>

# haclient.registry

Entity registry.

The registry stores :class:`haclient.entity.Entity` instances keyed by their
``entity_id`` and supports lookup by short (object) name scoped to a domain.
It is owned by each :class:`haclient.client.HAClient` instance to avoid the
pitfalls of global singletons in test and multi-client scenarios.

<a id="haclient.registry.EntityRegistry"></a>

## EntityRegistry Objects

```python
class EntityRegistry()
```

In-memory mapping of ``entity_id`` → :class:`Entity`.

<a id="haclient.registry.EntityRegistry.register"></a>

#### register

```python
def register(entity: Entity) -> None
```

Register ``entity`` (overwriting any existing entry).

<a id="haclient.registry.EntityRegistry.unregister"></a>

#### unregister

```python
def unregister(entity_id: str) -> None
```

Remove the entity identified by ``entity_id`` if present.

<a id="haclient.registry.EntityRegistry.get"></a>

#### get

```python
def get(entity_id: str) -> Entity | None
```

Return the entity for ``entity_id`` or ``None`` if missing.

<a id="haclient.registry.EntityRegistry.require"></a>

#### require

```python
def require(entity_id: str) -> Entity
```

Return the entity for ``entity_id`` or raise :class:`EntityNotFoundError`.

<a id="haclient.registry.EntityRegistry.clear"></a>

#### clear

```python
def clear() -> None
```

Remove all registered entities.

<a id="haclient.registry.EntityRegistry.resolve"></a>

#### resolve

```python
def resolve(domain: str, name: str) -> str
```

Resolve a short name to a full ``entity_id`` within ``domain``.

``name`` may be either:

* the *object id* (``"livingroom"``), or
* the fully-qualified ``entity_id`` (``"media_player.livingroom"``).

Parameters
----------
domain:
    The Home Assistant domain (e.g. ``"media_player"``).
name:
    The short name or full entity id to resolve.

<a id="haclient.registry.EntityRegistry.in_domain"></a>

#### in\_domain

```python
def in_domain(domain: str) -> list[Entity]
```

Return all registered entities belonging to ``domain``.

