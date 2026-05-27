# Reconnect and disconnect handling

HaClient is built for long-lived connections. When the WebSocket to
Home Assistant drops — because of a network blip, an HA restart, or
a transient TLS error — the client automatically:

1. Notifies registered `on_disconnect` handlers.
2. Reconnects in the background (with backoff).
3. Re-authenticates and **re-subscribes to every event type** that
   was registered before the drop.
4. Re-primes the entire state cache via REST so your entities
   reflect anything that changed while you were offline.
5. Notifies registered `on_reconnect` handlers.

You do **not** need to:

- Re-call `subscribe(...)` on the `EventBus`.
- Re-call `on_state_change` / `on_*` on entities.
- Re-fetch state for entities you already hold references to.

All of that is automatic.

## Disabling auto-reconnect

Auto-reconnect is on by default. Disable it via `from_url`:

```python
ha = HAClient.from_url(url, token=token, reconnect=False)
```

With reconnect off, a dropped WebSocket fires `on_disconnect` and
stays down. You become responsible for calling `close()` and
constructing a new client when you want to recover.

## Registering disconnect / reconnect listeners

Both methods can be used either imperatively or as decorators. Both
accept sync or async zero-argument callables.

```python
@ha.on_disconnect
def disconnected() -> None:
    metrics.increment("ha.disconnect")

@ha.on_reconnect
async def reconnected() -> None:
    # State has already been re-primed before this runs.
    await audit_log("ha-reconnected")
```

The same methods exist on `SyncHAClient` and behave identically; the
handlers run on the background loop thread (see the
[sync wrapper guide](sync-wrapper.md)).

## Timing guarantees

- `on_disconnect` fires when the underlying WebSocket transitions
  from connected to disconnected — including the close performed by
  `HAClient.close()`. If your handler must distinguish "shutdown"
  from "network failure", check application state, not the client.
- `on_reconnect` fires **after** state has been re-primed. Reading
  `entity.state` / `entity.attributes` inside the handler returns
  the freshly synced values, not stale pre-drop values.

If a re-prime fails — for example, the HA REST API is unreachable —
the failure is logged and swallowed; `on_reconnect` still fires.
This keeps your application running even if the very first
post-reconnect refresh is unlucky. Subsequent state changes will
heal the cache through the normal event stream.

## What happens to in-flight calls

Any service call that was in flight when the WebSocket dropped will
raise:

- `ConnectionClosedError` if the call was routed to the WebSocket
  and the transport closed mid-call.

Wrap calls you want to survive transient drops in your own retry
logic. The reconnect machinery is about *keeping the client live*,
not about implicitly retrying user calls. Implicit retries would
cause double execution of side-effectful services such as
`switch.toggle`.

## Pattern: wait for the next reconnect

For scripts that want to block until the client has recovered:

```python
import asyncio

reconnected = asyncio.Event()

@ha.on_reconnect
def _() -> None:
    reconnected.set()

# ... later, when you know you need fresh state:
await reconnected.wait()
reconnected.clear()
```

## Pattern: degrade UI on disconnect

For interactive applications, dual handlers give you the on / off
edges:

```python
@ha.on_disconnect
def _() -> None:
    ui.set_banner("Reconnecting to Home Assistant…")

@ha.on_reconnect
def _() -> None:
    ui.clear_banner()
```

Because `on_reconnect` runs after the re-prime, this gives users
a single moment when "everything is consistent again" rather than a
race between the banner clearing and entities updating.
