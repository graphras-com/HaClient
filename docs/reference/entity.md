<a id="haclient.entity"></a>

# haclient.entity

Base :class:`Entity` implementation.

Entities are bound to an :class:`haclient.client.HAClient` instance and
automatically receive state updates from WebSocket ``state_changed`` events.

<a id="haclient.entity.Entity"></a>

## Entity Objects

```python
class Entity()
```

Represent a single Home Assistant entity.

Subclasses map to specific domains (``media_player``, ``light``, ...) and
should override :attr:`domain` and add domain-specific methods.

The :attr:`state` string and :attr:`attributes` dictionary reflect the most
recent state known to the client. They are refreshed automatically when the
client receives ``state_changed`` events for this entity.

<a id="haclient.entity.Entity.remove_granular_listener"></a>

#### remove\_granular\_listener

```python
def remove_granular_listener(func: ValueChangeHandler) -> None
```

Remove a previously registered granular (attribute/state) listener.

<a id="haclient.entity.Entity.on_state_change"></a>

#### on\_state\_change

```python
def on_state_change(func: F) -> F
```

Register ``func`` as a listener for state changes on this entity.

May be used as a decorator. The callback receives the previous and new
raw state objects (``dict`` or ``None``). Coroutine functions are fully
supported and will be scheduled on the client's event loop without
blocking the dispatcher.

<a id="haclient.entity.Entity.remove_listener"></a>

#### remove\_listener

```python
def remove_listener(func: StateChangeHandler) -> None
```

Remove a previously registered state change listener.

<a id="haclient.entity.Entity.available"></a>

#### available

```python
@property
def available() -> bool
```

Return ``True`` if the entity is currently available.

<a id="haclient.entity.Entity.async_refresh"></a>

#### async\_refresh

```python
async def async_refresh() -> None
```

Fetch the latest state for this entity from the REST API.

<a id="haclient.entity.Entity.call_service"></a>

#### call\_service

```python
async def call_service(service: str,
                       data: dict[str, Any] | None = None,
                       *,
                       domain: str | None = None) -> Any
```

Call a Home Assistant service targeting this entity.

``service`` is the service name within ``domain`` (defaulting to this
entity's domain). ``entity_id`` is injected automatically into the
service data.

