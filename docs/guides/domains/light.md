# Light

The `light` accessor returns `Light` entities. Lights cover the
single biggest range of capabilities in Home Assistant — brightness,
RGB, color temperature, transitions — and HaClient normalises those
into a small set of intent-specific methods.

## Basic on / off

```python
light = ha.light("kitchen")

await light.on()
await light.off()
await light.toggle()

if light.is_on:
    print("kitchen is on")
```

## Brightness

Brightness is on the Home Assistant 0–255 scale.

```python
await light.set_brightness(200)
await light.set_brightness(0)            # equivalent to light.off()
await light.set_brightness(255, transition=2.0)

print(light.brightness)                  # current brightness or None
```

Pass `transition` (seconds) to any brightness/color/on/off method to
ramp the change. Lights that do not support transitions ignore it
silently — Home Assistant degrades the request.

## Color temperature

Use kelvin directly:

```python
await light.set_kelvin(2700, transition=1.0)   # warm white
await light.set_kelvin(6500)                   # cool white

print(light.kelvin, light.min_kelvin, light.max_kelvin)
```

`min_kelvin` / `max_kelvin` are reported by Home Assistant per
device; values outside that range are clamped by HA.

## Color

```python
await light.set_rgb(255, 128, 0)              # orange
await light.set_color(rgb=(255, 0, 128))      # multi-format helper
print(light.rgb_color)                        # current RGB or None
```

`set_color` accepts whichever format the light supports — RGB,
kelvin, hex, named — and lets you pick one at the call site.

## Reacting to changes

Each Light entity exposes intent-specific decorators built on the
generic [listener tiers](../listeners.md):

```python
@light.on_turn_on
def turned_on(old: str | None, new: str | None) -> None:
    print("kitchen turned on")

@light.on_turn_off
def turned_off(old, new): ...

@light.on_brightness_change
def brightness(old: int | None, new: int | None) -> None:
    print(f"brightness {old} -> {new}")

@light.on_color_change
def color(old, new): ...

@light.on_kelvin_change
def kelvin(old: int | None, new: int | None) -> None: ...
```

Use these instead of `on_state_change` whenever you can — they
filter for you and give you typed values.

## Common patterns

### Soft wake-up ramp

```python
await light.on()
await light.set_brightness(20)
await asyncio.sleep(1)
await light.set_brightness(255, transition=30.0)
```

### Match brightness across rooms

```python
target = ha.light("kitchen").brightness or 200
for room in ("hallway", "living_room", "bedroom"):
    await ha.light(room).set_brightness(target)
```

### Only act when state actually changes

```python
if not light.is_on:
    await light.on()
```

`light.is_on` and `light.brightness` read from the locally cached
state, so the check is free.
