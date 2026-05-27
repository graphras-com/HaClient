# Service routing (advanced)

> This guide is for **advanced use only**. Most users should never
> need to touch `client.services.call(...)` or the `prefer=` knob.
> If you find yourself reaching for raw service calls, first check
> whether a domain method already covers your use case.

## The normal path: domain methods

The supported, stable way to invoke Home Assistant is through the
domain entity methods:

```python
await ha.light("kitchen").set_brightness(200, transition=2.0)
await ha.media_player("living_room").play()
await ha.cover("garage").set_position(50)
await ha.scene.apply({"light.ceiling": {"state": "on", "brightness": 120}})
```

These methods:

- Validate inputs (e.g. brightness is `0..255`, volume is `0.0..1.0`).
- Normalise domain quirks (e.g. Light's many color formats, Cover's
  position direction).
- Use the right transport for each service.
- Keep working when Home Assistant restructures its underlying
  service payloads.

If you can express what you want through a domain method, do that.

## When you might need raw service calls

There are exactly three legitimate reasons to drop to
`client.services.call(...)`:

1. **The service is not exposed by any domain.** Some integrations
   (e.g. custom user integrations, niche third-party domains) have
   no built-in HaClient coverage.
2. **You need a one-off call to an HA-wide service** that is not
   entity-scoped — for example `homeassistant.restart` or
   `persistent_notification.create`.
3. **You need explicit transport control for a single call** that
   the default policy would route the wrong way.

For everything else, file a feature request — coverage gaps are bugs.

## Calling a service directly

```python
await ha.services.call(
    "notify",
    "mobile_app_my_phone",
    {"title": "Doorbell", "message": "Someone is at the door"},
)
```

The signature is:

```python
async def call(
    domain: str,
    service: str,
    data: dict | None = None,
    *,
    prefer: ServicePolicy | None = None,
) -> Any
```

`data` is the raw service payload. There is no entity-id injection
— if the service needs an entity, you put it in `data` yourself.

## The `prefer` policy

`ServicePolicy` is a `Literal["ws", "rest", "auto"]` that controls
which transport carries a service call:

- `"auto"` (default) — use the WebSocket when it is connected,
  otherwise fall back to REST. This is what you want in nearly
  every case.
- `"ws"` — always use the WebSocket. Raises `ConnectionClosedError`
  if the WS is not connected. Use this only when you specifically
  need the WS-only behaviour of a service.
- `"rest"` — always use REST. Use this when you must guarantee the
  call goes over HTTP — for example, in a script that runs before
  the WebSocket has fully come up, or when you are debugging
  routing.

You can set the default for a client at construction:

```python
ha = HAClient.from_url(url, token=token, service_policy="rest")
```

Or override per call:

```python
await ha.services.call(
    "homeassistant", "restart", prefer="rest"
)
```

## Why the abstraction exists

Home Assistant has two service-call transports with subtly different
behaviours:

- The **WebSocket** path returns service results inline. It is the
  only transport for some HA features (e.g. `media_player/browse_media`
  results, `timer/create` responses).
- The **REST** path is fire-and-forget for most services; the
  response just confirms the request was accepted. It works without
  an active WS subscription, which makes it useful for one-shot
  scripts.

The `ServiceCaller` makes this choice explicit and testable instead
of hiding it. Domain methods already pick correctly — they ask for
`prefer="ws"` whenever they need an actual response payload, and
otherwise let `"auto"` decide.

## Anti-patterns

- **Wrapping domain methods in service calls.** Do not write
  `services.call("light", "turn_on", {"entity_id": "light.kitchen",
  "brightness": 200})` instead of
  `ha.light("kitchen").set_brightness(200)`. You lose validation,
  type safety, and forward compatibility.
- **Polling the WS state via raw service calls.** State is already
  cached and updated by the event stream. Read `entity.state` /
  `entity.attributes`.
- **Hard-coding `prefer="rest"` for everything.** The default
  `"auto"` policy is correct for nearly all workloads and will
  transparently use the more efficient WS path when available.
