# Guides

These guides walk through common HaClient workflows. They focus on
*how* to use the client effectively rather than enumerating every
parameter — see the [API Reference](../reference/index.md) for that.

## Getting started

- [Async lifecycle and state priming](lifecycle.md) — how `HAClient`
  connects, primes its cache, and shuts down cleanly.
- [Sync wrapper](sync-wrapper.md) — when and how to use
  `SyncHAClient` from scripts, the REPL, or Jupyter.

## Reacting to state

- [State and value listeners](listeners.md) — the two listener tiers,
  decorator patterns, and removal.
- [Reconnect and disconnect handling](reconnect.md) — what survives
  reconnects automatically and what you need to wire up yourself.

## Extending the client

- [Custom domains and plugins](custom-domains.md) — adding a new
  domain in-process or via the `haclient.domains` entry point.
- [Service routing (advanced)](service-routing.md) — when to drop to
  raw `services.call(...)` and what `prefer="ws" | "rest" | "auto"`
  actually does.

## Domain workflows

- [Light](domains/light.md)
- [Switch](domains/switch.md)
- [Climate](domains/climate.md)
- [Cover](domains/cover.md)
- [Media Player](domains/media_player.md)
- [Scene](domains/scene.md)
- [Timer](domains/timer.md)
- [Sensor](domains/sensor.md)

## Design philosophy

HaClient is **not** a thin wrapper over the Home Assistant REST and
WebSocket APIs. It deliberately reshapes them into something more
consistent and more Pythonic:

- Use the high-level domain methods (`light.set_brightness(...)`,
  `cover.set_position(...)`, `media_player.play()`) as the normal
  path. They normalise domain quirks, validate inputs, and pick the
  right transport.
- Drop to `client.services.call(...)` only for services that no
  domain method covers, or when you need very specific routing.
- Map entity events to domain-specific listener decorators
  (`@light.on_brightness_change`, `@timer.on_finished`) before
  reaching for the generic `on_state_change`.
