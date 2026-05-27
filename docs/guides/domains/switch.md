# Switch

Switches are the simplest entities in Home Assistant: an on/off
state with no extra attributes.

```python
switch = ha.switch("fan_outlet")

await switch.on()
await switch.off()
await switch.toggle()

print(switch.is_on)
```

## Reacting to changes

```python
@switch.on_turn_on
def on(old: str | None, new: str | None) -> None:
    print("fan outlet on")

@switch.on_turn_off
def off(old, new):
    print("fan outlet off")
```

For lower-level access (raw state dicts) use `switch.on_state_change`
— see the [listeners guide](../listeners.md).

## Common patterns

### Idempotent toggle

`toggle()` always flips. If you want "ensure on" or "ensure off",
test first:

```python
if not switch.is_on:
    await switch.on()
```

### Coordinated multi-switch action

```python
for name in ("outlet_a", "outlet_b", "outlet_c"):
    await ha.switch(name).off()
```

Service calls are serialised through the same WebSocket session, so
this is safe — no need for additional locking.

### Watching for an external change

A common automation pattern is to react when a switch is flipped by
a physical button or another script:

```python
@switch.on_turn_on
async def someone_turned_it_on(old, new):
    if not we_are_the_one_who_did_it:
        await notify("fan outlet was turned on externally")
```

Granular handlers also fire for changes you initiate yourself, so
guard accordingly if you need that distinction.
