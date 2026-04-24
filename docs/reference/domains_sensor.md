<a id="haclient.domains.sensor"></a>

# haclient.domains.sensor

``sensor`` domain implementation (read-only).

<a id="haclient.domains.sensor.Sensor"></a>

## Sensor Objects

```python
class Sensor(Entity)
```

A read-only Home Assistant sensor entity.

<a id="haclient.domains.sensor.Sensor.on_value_change"></a>

#### on\_value\_change

```python
def on_value_change(func: Any) -> Any
```

Register a listener for sensor value changes. Callback: ``(old_state, new_state)``.

<a id="haclient.domains.sensor.Sensor.unit_of_measurement"></a>

#### unit\_of\_measurement

```python
@property
def unit_of_measurement() -> str | None
```

The unit of the sensor value, if provided by Home Assistant.

<a id="haclient.domains.sensor.Sensor.device_class"></a>

#### device\_class

```python
@property
def device_class() -> str | None
```

The device class (e.g. ``"temperature"``).

<a id="haclient.domains.sensor.Sensor.value"></a>

#### value

```python
@property
def value() -> float | str | None
```

Return the sensor value coerced to ``float`` if numeric.

