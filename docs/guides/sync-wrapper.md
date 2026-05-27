# Sync wrapper

`SyncHAClient` is a blocking facade over `HAClient` aimed at scripts,
the REPL, and Jupyter notebooks — anywhere `async/await` would be
inconvenient.

```python
from haclient import SyncHAClient

with SyncHAClient.from_url(
    "http://localhost:8123",
    token="YOUR_TOKEN",
) as ha:
    light = ha.light("kitchen")
    light.set_brightness(200)
    print(light.is_on, light.brightness)
```

The same surface is available — domain accessors, entity properties,
listener registration — but every async method becomes a blocking
call.

## How it works

Construction spawns a dedicated daemon thread (`haclient-sync-loop`)
that owns a single `asyncio` event loop. The underlying `HAClient` is
created on that loop. Every method call from your synchronous code is
forwarded to the loop via `asyncio.run_coroutine_threadsafe` and the
calling thread blocks on the result.

You never have to think about the loop directly — `ha.light("kitchen")`
returns a proxy that auto-blocks on async methods and transparently
returns plain values for sync ones.

## Construction

Use `from_url` exactly as you would for the async client:

```python
ha = SyncHAClient.from_url(
    "http://localhost:8123",
    token="YOUR_TOKEN",
    reconnect=True,
    request_timeout=30.0,
    service_policy="auto",
)
```

There is **no `from_async_client(...)` factory** — the sync wrapper
always owns its own loop and its own underlying `HAClient`. Trying to
share one async client across both interfaces will not work and is
not supported.

## Context manager and `close()`

The `with` statement is the recommended usage. It guarantees both
sides of the bring-up:

- `__enter__` calls `connect()`, which blocks until the background
  loop has authenticated, primed state, and is ready.
- `__exit__` calls `close()`, which shuts down the underlying client,
  stops the loop, and joins the background thread (with a 5 s
  timeout).

If you cannot use `with`, call them manually:

```python
ha = SyncHAClient.from_url(url, token=token)
ha.connect()
try:
    ...
finally:
    ha.close()
```

**Always call `close()`.** Failing to do so leaves the loop thread
running for the lifetime of the process; the thread is a daemon so
the interpreter can still exit, but pending tasks may be abandoned
mid-flight.

## Listeners on the sync wrapper

You can still use `on_state_change` and the granular `on_*`
decorators. Handlers can be plain functions; they run on the
background loop thread, so any code they execute should be
thread-safe with the rest of your program.

```python
light = ha.light("kitchen")

@light.on_brightness_change
def on_brightness(old: int | None, new: int | None) -> None:
    print(f"kitchen brightness {old} -> {new}")
```

Async handlers also work and are awaited on the loop thread.

## Reconnect hooks

`on_reconnect` and `on_disconnect` work the same as on the async
client:

```python
@ha.on_disconnect
def disconnected() -> None:
    print("ha gone")

@ha.on_reconnect
def reconnected() -> None:
    print("ha back; state has been re-primed")
```

See the [reconnect guide](reconnect.md) for what runs automatically
between those two events.

## When *not* to use it

- Inside an existing `asyncio` application — use `HAClient` directly.
  Wrapping an async event loop inside another loop thread just adds
  overhead and surprising deadlocks.
- In a long-running server. The blocking-call-from-one-thread model
  serialises every operation across the loop thread, which becomes
  the bottleneck at any real concurrency. Servers should use
  `HAClient` from native async code.
