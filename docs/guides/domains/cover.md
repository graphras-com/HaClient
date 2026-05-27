# Cover

The `cover` accessor returns `Cover` entities — garage doors,
blinds, shades, awnings. The HA `cover` domain conflates "open /
close" with "set position to N%"; HaClient exposes both clearly.

## Reading state

```python
cover = ha.cover("garage")

print(cover.is_open)            # state == "open"
print(cover.is_closed)          # state == "closed"
print(cover.current_position)   # 0-100 (closed-open), or None
```

`state` is a string and may also be `"opening"`, `"closing"`, or
`"unknown"`. `is_open` / `is_closed` only check the steady-state
strings — neither is `True` mid-motion.

## Opening, closing, stopping

```python
await cover.open()
await cover.close()
await cover.stop()       # stop a motion in progress
await cover.toggle()     # open if closed, close otherwise
```

`stop()` is a no-op for covers that do not support stopping.

## Setting a specific position

```python
await cover.set_position(50)     # half-open
await cover.set_position(100)    # fully open (equivalent to open())
await cover.set_position(0)      # fully closed (equivalent to close())
```

`position` is `0..100`. Covers that do not support intermediate
positions will round to the nearest supported value (typically `0`
or `100`).

## Reacting to changes

```python
@cover.on_open
def opened(old: str | None, new: str | None) -> None:
    print("garage is now open")

@cover.on_close
def closed(old, new): ...

@cover.on_position_change
def position(old: int | None, new: int | None) -> None:
    print(f"garage position {old} -> {new}")
```

`on_open` / `on_close` fire on the *transition into* the open or
closed state — not on each tick of motion. Use `on_position_change`
if you need every percentage update.

## Common patterns

### Open only if currently closed

```python
if cover.is_closed:
    await cover.open()
```

### Vent — open partially, then close again

```python
await cover.set_position(20)
await asyncio.sleep(300)
await cover.close()
```

### Sync two covers

```python
target = ha.cover("blind_left").current_position or 100
await ha.cover("blind_right").set_position(target)
```
