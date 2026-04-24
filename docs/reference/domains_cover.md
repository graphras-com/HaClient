<a id="haclient.domains.cover"></a>

# haclient.domains.cover

``cover`` domain implementation.

<a id="haclient.domains.cover.Cover"></a>

## Cover Objects

```python
class Cover(Entity)
```

A Home Assistant cover (blind/garage/shade) entity.

<a id="haclient.domains.cover.Cover.on_open"></a>

#### on\_open

```python
def on_open(func: Any) -> Any
```

Register a listener for when the cover opens. Callback: ``(old_state, new_state)``.

<a id="haclient.domains.cover.Cover.on_close"></a>

#### on\_close

```python
def on_close(func: Any) -> Any
```

Register a listener for when the cover closes. Callback: ``(old_state, new_state)``.

<a id="haclient.domains.cover.Cover.on_position_change"></a>

#### on\_position\_change

```python
def on_position_change(func: Any) -> Any
```

Register a listener for position changes. Callback: ``(old, new)``.

<a id="haclient.domains.cover.Cover.is_open"></a>

#### is\_open

```python
@property
def is_open() -> bool
```

``True`` if the cover is currently open.

<a id="haclient.domains.cover.Cover.is_closed"></a>

#### is\_closed

```python
@property
def is_closed() -> bool
```

``True`` if the cover is currently closed.

<a id="haclient.domains.cover.Cover.current_position"></a>

#### current\_position

```python
@property
def current_position() -> int | None
```

Current position (0–100) or ``None`` if unsupported.

<a id="haclient.domains.cover.Cover.open"></a>

#### open

```python
async def open() -> None
```

Open the cover fully.

<a id="haclient.domains.cover.Cover.close"></a>

#### close

```python
async def close() -> None
```

Close the cover fully.

<a id="haclient.domains.cover.Cover.stop"></a>

#### stop

```python
async def stop() -> None
```

Stop movement of the cover.

<a id="haclient.domains.cover.Cover.set_position"></a>

#### set\_position

```python
async def set_position(position: int) -> None
```

Set the cover position (0 closed, 100 open).

<a id="haclient.domains.cover.Cover.toggle"></a>

#### toggle

```python
async def toggle() -> None
```

Toggle open/close state.

