<a id="haclient.domains.switch"></a>

# haclient.domains.switch

``switch`` domain implementation.

<a id="haclient.domains.switch.Switch"></a>

## Switch Objects

```python
class Switch(Entity)
```

A Home Assistant switch entity.

<a id="haclient.domains.switch.Switch.on_turn_on"></a>

#### on\_turn\_on

```python
def on_turn_on(func: Any) -> Any
```

Register a listener for when the switch turns on.

Callback: ``(old_state, new_state)``.

<a id="haclient.domains.switch.Switch.on_turn_off"></a>

#### on\_turn\_off

```python
def on_turn_off(func: Any) -> Any
```

Register a listener for when the switch turns off.

Callback: ``(old_state, new_state)``.

<a id="haclient.domains.switch.Switch.is_on"></a>

#### is\_on

```python
@property
def is_on() -> bool
```

``True`` if the switch is currently on.

<a id="haclient.domains.switch.Switch.turn_on"></a>

#### turn\_on

```python
async def turn_on() -> None
```

Turn the switch on.

<a id="haclient.domains.switch.Switch.turn_off"></a>

#### turn\_off

```python
async def turn_off() -> None
```

Turn the switch off.

<a id="haclient.domains.switch.Switch.toggle"></a>

#### toggle

```python
async def toggle() -> None
```

Toggle the switch state.

