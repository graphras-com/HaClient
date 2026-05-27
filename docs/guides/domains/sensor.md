# Sensor

The `sensor` accessor returns read-only `Sensor` entities — anything
HA reports a value for: temperature, humidity, power, presence
counts, energy totals, and so on.

## Reading values

```python
sensor = ha.sensor("outdoor_temperature")

print(sensor.value)                  # float, str, or None
print(sensor.unit_of_measurement)    # "°C", "kWh", "%", ...
print(sensor.device_class)           # "temperature", "energy", ...
print(sensor.state)                  # the raw HA state string
print(sensor.attributes)             # full attribute dict
```

`value` is HaClient's normalised view of the sensor reading:

- If the state parses as a number, you get a `float`.
- If it does not, you get the raw state string (e.g. `"on"`,
  `"home"`).
- If the entity is unavailable or has not arrived yet, you get
  `None`.

For absolute fidelity, read `sensor.state` (always a string) and
`sensor.attributes` directly.

## Reacting to changes

```python
@sensor.on_value_change
def changed(old, new):
    print(f"{sensor.entity_id}: {old} -> {new}")
```

`on_value_change` fires on any state-string change. The handler
receives the raw old/new strings; if you want the normalised numeric
value, read `sensor.value` inside the handler.

## Common patterns

### Threshold alerting

```python
@sensor.on_value_change
async def temp_alert(old, new):
    v = sensor.value
    if isinstance(v, float) and v > 30.0:
        await notify(f"{sensor.entity_id} is hot: {v} {sensor.unit_of_measurement}")
```

### Periodic polling fallback

State arrives via the event stream, so polling is rarely needed.
When you suspect a stale reading after a reconnect or HA restart,
force a single refresh:

```python
await sensor.async_refresh()
```

Or refresh everything at once via `await ha.state.refresh_all()`.

### Collecting all sensors in a domain

```python
for entity in ha.sensor.all():
    print(entity.entity_id, entity.value)
```

`all()` returns every sensor entity the client has registered so
far. Entities are created lazily when you first ask for them by
name, so `all()` only reflects sensors you (or built-in priming)
have touched — it is not a discovery API.
