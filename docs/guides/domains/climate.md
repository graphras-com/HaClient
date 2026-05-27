# Climate

The `climate` accessor returns `Climate` entities representing
thermostats, A/C units, and HVAC systems.

## Reading current state

```python
climate = ha.climate("living_room")

print(climate.hvac_mode)             # "heat", "cool", "off", ...
print(climate.current_temperature)   # sensed temperature, or None
print(climate.target_temperature)    # current setpoint, or None
print(climate.hvac_modes)            # supported modes, e.g. ["off", "heat", "cool"]
```

`hvac_mode` is the entity's `state` string — they are aliases. We
expose it under the intent-specific name because that is what users
actually mean.

## Setting the setpoint

```python
await climate.set_temperature(temperature=21.5)
```

The method accepts the underlying HA service's full parameter set —
including `target_temp_high` / `target_temp_low` for ranged
thermostats — via the same keyword arguments HA expects.

## Switching modes

```python
await climate.set_hvac_mode("heat")
await climate.set_hvac_mode("off")
await climate.set_fan_mode("auto")
```

Use values from `climate.hvac_modes` rather than guessing. Different
devices support different mode strings.

## Reacting to changes

```python
@climate.on_hvac_mode_change
def mode(old: str | None, new: str | None) -> None:
    print(f"hvac {old} -> {new}")

@climate.on_temperature_change
def measured(old: float | None, new: float | None) -> None:
    print(f"current temp now {new}")

@climate.on_target_temperature_change
def setpoint(old: float | None, new: float | None) -> None:
    print(f"setpoint now {new}")
```

`on_temperature_change` fires on the sensed temperature; use
`on_target_temperature_change` for setpoint changes (e.g. someone
moved the slider in the HA UI).

## Common patterns

### Bump the setpoint

```python
current = climate.target_temperature or 20.0
await climate.set_temperature(temperature=current + 0.5)
```

### Switch to heat if cold enough

```python
if (climate.current_temperature or 100) < 18 and climate.hvac_mode == "off":
    await climate.set_hvac_mode("heat")
    await climate.set_temperature(temperature=20)
```

### Log every setpoint change

```python
@climate.on_target_temperature_change
async def audit(old, new):
    await db.insert("hvac_setpoint", entity=climate.entity_id, old=old, new=new)
```
