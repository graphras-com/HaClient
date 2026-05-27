# Timer

The `timer` accessor returns `Timer` entities representing Home
Assistant timer helpers. HaClient adds a typed
`TimerAccessor.create` for runtime creation and forwards every
timer-finished event back to the right entity.

## Lifecycle of a timer

Timers move through these states:

- `idle` — created but not started, or finished/cancelled.
- `active` — counting down.
- `paused` — paused mid-countdown.

```python
timer = ha.timer("tea")

print(timer.is_idle, timer.is_active, timer.is_paused)
print(timer.duration)        # configured duration as HA string ("HH:MM:SS")
print(timer.remaining)       # remaining as HA string
print(timer.time_remaining)  # remaining as float seconds
print(timer.finishes_at)     # ISO timestamp or None
print(timer.persistent)
```

## Starting, pausing, cancelling

```python
await timer.start()                              # use configured duration
await timer.start(duration="00:05:00")           # override duration

await timer.pause()
await timer.cancel()                             # back to idle
await timer.finish()                             # mark finished immediately

await timer.change(duration="00:10:00")          # change a running timer
```

`change` only works on timers that are currently running; HA itself
rejects calls otherwise.

## Reacting to timer events

The decorator names match the lifecycle transitions:

```python
@timer.on_start
def started(old, new): ...

@timer.on_pause
def paused(old, new): ...

@timer.on_idle
def idle(old, new): ...

@timer.on_finished
async def finished(old, new):
    await notify("Tea is ready")

@timer.on_cancelled
def cancelled(old, new): ...
```

Two of those — `on_finished` and `on_cancelled` — are wired to the
HA events `timer.finished` and `timer.cancelled` (not just the state
transition), so they fire reliably even on timers that briefly skip
through `idle` between cycles.

## Creating a runtime timer

```python
new_timer = await ha.timer.create(duration="00:01:30")
await new_timer.start()
```

`create` auto-generates a name when you do not supply one. For a
named, persistent timer (one that survives restarts) you must
provide a `name`:

```python
laundry = await ha.timer.create(
    name="laundry_cycle",
    duration="00:45:00",
    persistent=True,
)
```

Creating a `persistent=True` timer without a `name` raises
`ValueError`.

## Deleting

```python
await timer.delete()
```

Deletes the helper from HA. Library-created timers should be deleted
when you are done with them, otherwise they accumulate.

## Common patterns

### Wait for a timer to finish

```python
import asyncio

done = asyncio.Event()

@timer.on_finished
def _(old, new) -> None:
    done.set()

await timer.start(duration="00:00:30")
await done.wait()
```

### Resettable countdown

```python
async def reset() -> None:
    await timer.cancel()
    await timer.start(duration="00:10:00")
```

`cancel` followed by `start` is the standard way to reset; HA does
not expose a single-call "restart".
