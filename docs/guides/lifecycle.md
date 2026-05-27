# Async lifecycle and state priming

`HAClient` is an async context manager. The normal usage pattern is:

```python
import asyncio
from haclient import HAClient

async def main() -> None:
    async with HAClient.from_url(
        "http://localhost:8123",
        token="YOUR_LONG_LIVED_TOKEN",
    ) as ha:
        light = ha.light("kitchen")
        await light.on()

asyncio.run(main())
```

Entering the `async with` block performs three things, in order:

1. Opens the WebSocket and completes the Home Assistant auth
   handshake.
2. Subscribes to `state_changed` events with **buffering enabled**
   so no event is missed during step 3.
3. Issues a single REST `get_states` call to prime the in-memory
   state cache, then drains the buffered events on top.

This priming sequence is what makes `light.state`, `light.attributes`,
and the `is_on` / `brightness` properties readable the moment you
get the entity back — no `await` required to read cached state.

## Why priming exists

If the client subscribed to events first and *then* fetched the
snapshot, a `state_changed` event arriving between those two calls
would be lost. If it fetched the snapshot first and *then*
subscribed, the same event would be missed. HaClient subscribes
first, buffers everything until the snapshot lands, applies the
snapshot, then replays the buffer.

State application is **idempotent** — applying a state dict twice
produces the same result — so replaying a buffered event that was
already reflected in the snapshot is safe.

## Reading vs refreshing

State is kept live by the event stream. You do not need to poll.
Once you have an entity, just read its attributes:

```python
async with HAClient.from_url(url, token=token) as ha:
    light = ha.light("kitchen")
    print(light.is_on, light.brightness)
```

For the rare case where you need to force a REST round trip for a
single entity (e.g. you suspect the event stream missed something
after a network blip), use:

```python
await light.async_refresh()
```

To refresh every registered entity, use the store:

```python
await ha.state.refresh_all()
```

This is also what runs automatically after each successful WebSocket
reconnect — see the [reconnect guide](reconnect.md).

## Lazy entity creation

Domain accessors create entities on demand:

```python
light = ha.light("kitchen")  # creates and registers a Light entity
```

The entity is registered with the `StateStore` immediately, and its
`state` / `attributes` are populated from the cache if Home Assistant
already knows about `light.kitchen`. If the entity id is unknown,
`state` stays `"unknown"` and `attributes` stays empty until the
first event arrives — there is no error.

This means you can pre-register an entity that does not yet exist in
Home Assistant and start listening to it; it will hydrate the moment
HA sends its first `state_changed` event.

## Shutdown

Exiting the `async with` block calls `close()`, which:

- Cancels reconnect and keepalive tasks.
- Closes the WebSocket. Registered `on_disconnect` listeners run
  here.
- Closes the REST adapter and releases the aiohttp session
  *if HaClient created it*. Externally-supplied sessions are left
  alone.

`close()` is safe to call multiple times.

## Manual control

If you cannot use `async with` (e.g. you need to construct the
client in one place and connect it in another), use `connect()` and
`close()` directly:

```python
ha = HAClient.from_url(url, token=token)
await ha.connect()
try:
    light = ha.light("kitchen")
    await light.on()
finally:
    await ha.close()
```

## Errors during connect

`connect()` can raise:

- `AuthenticationError` — the token was rejected.
- `ConnectionClosedError` — the WebSocket dropped before the
  handshake completed.
- `TimeoutError` — a transport call exceeded the configured
  `request_timeout`.
- `HTTPError` — the initial REST `get_states` returned an error.

If you pre-constructed the client and `connect()` raises, you still
own the partially-initialised instance. Call `close()` to release
its resources before discarding it.
