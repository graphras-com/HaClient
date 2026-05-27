# State and value listeners

HaClient exposes two listener tiers on every entity. Pick the one
that matches what you actually care about.

| You want to react to... | Use |
| --- | --- |
| Anything HA reports for this entity (raw dicts) | `entity.on_state_change` |
| The state string changing (e.g. `"off"` → `"on"`) | The domain's `on_*` decorators |
| A specific attribute changing (e.g. `brightness`) | The domain's `on_<attr>_change` decorators |

The decorator forms always return the handler unchanged, so they
compose naturally with any callable — sync function, `async def`
function, bound method, lambda.

## Raw state changes — `on_state_change`

This is the lowest-level listener. The handler is called with
`(old_state_dict, new_state_dict)`. Either side can be `None` when
the entity appears or disappears from Home Assistant.

```python
light = ha.light("kitchen")

@light.on_state_change
def on_change(old: dict | None, new: dict | None) -> None:
    print("kitchen ->", new and new.get("state"))
```

Async handlers are supported and are scheduled on the client's loop:

```python
@light.on_state_change
async def on_change(old, new):
    await some_async_work(new)
```

Use this when you need access to the full HA payload — for example,
you want to inspect every changed attribute, or persist the raw
state dict to a database. For everything else, prefer the granular
listeners below.

## Granular value listeners

Each domain exposes intent-specific decorators built on top of three
internal categories:

- **State string change** — fires whenever the state string changes
  at all. Sensor's `on_value_change` and Scene's `on_activate` are
  examples.
- **State transition to a specific value** — fires only when the
  state transitions *into* a specific string. Light's `on_turn_on`,
  Timer's `on_finished`, Lock's `on_jam` are examples.
- **Attribute change** — fires when a specific attribute value
  changes. Light's `on_brightness_change`, Climate's
  `on_temperature_change`, MediaPlayer's `on_volume_change` are
  examples.

All granular handlers receive `(old_value, new_value)`. They can be
sync or async:

```python
light = ha.light("kitchen")

@light.on_turn_on
def turned_on(old: str | None, new: str | None) -> None:
    print(f"kitchen turned on (was {old})")

@light.on_brightness_change
async def brightness_changed(old: int | None, new: int | None) -> None:
    await log_brightness(new)
```

See each [domain guide](domains/light.md) for the full set of
decorators a particular domain exposes.

## Why prefer granular listeners

The granular decorators give you three things `on_state_change`
cannot:

- **Filtering for free.** `on_brightness_change` only fires when the
  brightness attribute actually changes; you do not have to diff
  the dicts yourself.
- **Typed values.** Each domain exposes pre-extracted, sensibly-typed
  values (e.g. brightness as `int | None`, not a free-form dict
  lookup).
- **Stable contracts.** When HA renames an attribute or restructures
  a payload, the domain code absorbs the change — your handler
  signature stays the same.

## Removing listeners

Both tiers have a removal method:

```python
light.remove_listener(on_change)             # raw state-change handler
light.remove_granular_listener(turned_on)    # any granular handler
```

Unknown handlers are silently ignored, so removing twice is safe.

`remove_granular_listener` searches in this order:

1. Attribute listeners
2. State-transition listeners
3. State-value listeners

It removes the first match. If you have registered the same
function in multiple tiers (rare), call it once per tier.

## Exceptions in handlers

Synchronous exceptions raised by a listener are caught, logged, and
swallowed — they will not break the event dispatch loop or prevent
other listeners from running. Async handlers run on the client's
loop; exceptions there are surfaced via the loop's default exception
handler.

Treat listeners as *best-effort observers*. Anything that must
succeed (e.g. logging a state change to durable storage) should
handle its own retries.

## Subscribing to non-entity events

Some Home Assistant events are not tied to a single entity — for
example, `automation_triggered` or custom events fired by your own
automations. Use the `EventBus` directly for those:

```python
async def on_automation(event: dict) -> None:
    print("automation:", event["data"].get("name"))

ha.events.subscribe("automation_triggered", on_automation)
```

Subscriptions automatically re-register on reconnect. See the
[EventBus reference](../reference/core/events.md) for the full
API, including buffering and `subscribe_async` (which awaits the
underlying transport and raises on failure).
