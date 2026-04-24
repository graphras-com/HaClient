<a id="haclient.domains.binary_sensor"></a>

# haclient.domains.binary\_sensor

``binary_sensor`` domain implementation (read-only).

<a id="haclient.domains.binary_sensor.BinarySensor"></a>

## BinarySensor Objects

```python
class BinarySensor(Entity)
```

A read-only Home Assistant binary sensor entity.

<a id="haclient.domains.binary_sensor.BinarySensor.on_turn_on"></a>

#### on\_turn\_on

```python
def on_turn_on(func: Any) -> Any
```

Register a listener for when the sensor activates.

Callback: ``(old_state, new_state)``.

<a id="haclient.domains.binary_sensor.BinarySensor.on_turn_off"></a>

#### on\_turn\_off

```python
def on_turn_off(func: Any) -> Any
```

Register a listener for when the sensor deactivates.

Callback: ``(old_state, new_state)``.

<a id="haclient.domains.binary_sensor.BinarySensor.is_on"></a>

#### is\_on

```python
@property
def is_on() -> bool
```

``True`` if the binary sensor is in the ``on`` state.

<a id="haclient.domains.binary_sensor.BinarySensor.device_class"></a>

#### device\_class

```python
@property
def device_class() -> str | None
```

The device class (e.g. ``"motion"``, ``"door"``).

