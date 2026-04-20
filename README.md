# ha-client

An async-first, high-level Python client for [Home Assistant](https://www.home-assistant.io/).
It talks to a Home Assistant instance over both the WebSocket API (for live
state and events) and the REST API (for the initial snapshot and fallback
service calls) and exposes an intuitive, domain-oriented interface:

```python
async with HAClient("http://homeassistant.local:8123", token=TOKEN) as ha:
    light = ha.light("kitchen")
    await light.turn_on(brightness=200, rgb_color=(255, 160, 0))

    player = ha.media_player("livingroom")
    for fav in await player.favorites():
        print(fav.title)
```

## Features

- Async core (`asyncio` + `aiohttp`) with a synchronous wrapper (`SyncHAClient`)
- Persistent WebSocket connection with auth handshake, keepalive pings and
  automatic reconnect + resubscribe
- First-class entity model: `MediaPlayer`, `Light`, `Switch`, `Climate`,
  `Cover`, `Sensor`, `BinarySensor`
- Decorator-based state-change listeners (`@entity.on_state_change`)
- `MediaPlayer.favorites()` – walks `browse_media` recursively and returns
  flattened, directly-playable `FavoriteItem` objects
- Fully type-annotated (`py.typed`), clean `mypy --strict` build
- 90+ % test coverage using a hermetic fake HA server

## Installation

```bash
pip install ha-client
```

From source (with dev extras):

```bash
uv pip install -e ".[dev]"
```

## Quick start

```python
import asyncio
from ha_client import HAClient


async def main() -> None:
    async with HAClient("http://homeassistant.local:8123", token="LONG_LIVED_TOKEN") as ha:
        # Entities are accessed via the client. Short names (object id) or
        # fully qualified entity ids both work:
        light = ha.light("kitchen")            # light.kitchen
        player = ha.media_player("media_player.livingroom")

        await light.turn_on(brightness=180)
        await player.play()


asyncio.run(main())
```

### Authentication

Create a long-lived access token in the Home Assistant UI (Profile → Security
→ *Long-Lived Access Tokens*) and pass it as `token=`. Both the REST and the
WebSocket API use the same token.

## Domain classes

| Domain         | Class           | Notable methods                                        |
| -------------- | --------------- | ------------------------------------------------------ |
| `media_player` | `MediaPlayer`   | `play() / pause() / next() / set_volume() / favorites()` |
| `light`        | `Light`         | `turn_on() / turn_off() / toggle()`                    |
| `switch`       | `Switch`        | `turn_on() / turn_off() / toggle()`                    |
| `climate`      | `Climate`       | `set_temperature() / set_hvac_mode()`                  |
| `cover`        | `Cover`         | `open() / close() / set_position()`                    |
| `sensor`       | `Sensor`        | read-only (`.state`, `.value`, `.unit_of_measurement`) |
| `binary_sensor`| `BinarySensor`  | read-only (`.is_on`, `.device_class`)                  |

All entities expose `.entity_id`, `.state`, `.attributes` and `.available`.

## Examples

### MediaPlayer

```python
player = ha.media_player("livingroom")
await player.play()
await player.set_volume(0.5)
await player.next()

# Access structured media info
np = player.now_playing
print(f"{np.artist} - {np.title} ({np.album})")
```

### Light control

```python
light = ha.light("kitchen")
await light.turn_on(brightness=180, rgb_color=(255, 160, 0), transition=1.5)
await light.turn_off(transition=1.5)
```

### Event handling

```python
light = ha.light("kitchen")

@light.on_state_change
async def on_change(old, new):
    print("kitchen light:", (old or {}).get("state"), "→", (new or {}).get("state"))
```

Multiple listeners are supported per entity, both sync and async callbacks
work, and exceptions raised by one listener never disrupt the others.

### Granular events

In addition to the generic `on_state_change`, each domain exposes higher-level
event decorators that fire only when a specific attribute or state value
changes. Callbacks receive `(old_value, new_value)`:

```python
player = ha.media_player("livingroom")

@player.on_volume_change
async def vol(old, new):
    print(f"Volume: {old} → {new}")

@player.on_play
def started(old_state, new_state):
    print("Playback started!")
```

Available events per domain:

| Domain          | Events                                                                 |
| --------------- | ---------------------------------------------------------------------- |
| `MediaPlayer`   | `on_volume_change`, `on_mute_change`, `on_media_change`, `on_play`, `on_pause`, `on_stop` |
| `Light`         | `on_turn_on`, `on_turn_off`, `on_brightness_change`, `on_color_change` |
| `Switch`        | `on_turn_on`, `on_turn_off`                                            |
| `BinarySensor`  | `on_turn_on`, `on_turn_off`                                            |
| `Cover`         | `on_open`, `on_close`, `on_position_change`                            |
| `Climate`       | `on_hvac_mode_change`, `on_temperature_change`, `on_target_temperature_change` |
| `Sensor`        | `on_value_change`                                                      |

Use `entity.remove_granular_listener(func)` to unregister a granular listener.

### `favorites()`

```python
player = ha.media_player("livingroom")
favs = await player.favorites()
for item in favs:
    print(item.media_content_type, item.title, item.media_content_id)

if favs:
    await favs[0].play()
```

`favorites()` issues `media_player/browse_media` WebSocket commands,
recursively descends into expandable nodes and returns a flat list of
`FavoriteItem` instances. If the media player does not support browsing,
`favorites()` returns `[]` – no exception is raised.

### Synchronous wrapper

```python
from ha_client import SyncHAClient

with SyncHAClient("http://homeassistant.local:8123", token=TOKEN) as ha:
    player = ha.media_player("livingroom")
    player.play()              # no await
    player.set_volume(0.4)
```

The wrapper runs its event loop in a dedicated background thread and submits
coroutines with `asyncio.run_coroutine_threadsafe`. There are no event-loop
conflicts inside Jupyter / IPython.

## Error handling

The library defines a small hierarchy rooted at `HAClientError`:

| Exception                   | Raised when                                           |
| --------------------------- | ----------------------------------------------------- |
| `AuthenticationError`       | Invalid / expired access token                        |
| `ConnectionClosedError`     | WebSocket is closed while an operation was in flight  |
| `CommandError`              | HA returned `success: false` for a WebSocket command  |
| `TimeoutError`              | A request did not complete within the timeout         |
| `EntityNotFoundError`       | Lookup for an entity that was never registered failed |
| `UnsupportedOperationError` | A domain operation is not supported on this entity    |

Dropped WebSocket connections trigger an automatic reconnect with
exponential back-off, and any previously registered event subscriptions are
re-established transparently.

## Project layout

```
ha_client/
  __init__.py
  client.py          # HAClient (high-level facade)
  websocket.py       # WebSocketClient (low-level WS + reconnect)
  rest.py            # RestClient
  registry.py        # EntityRegistry
  entity.py          # Entity base class + state-change dispatch
  sync.py            # SyncHAClient (blocking wrapper)
  exceptions.py
  domains/
    media_player.py  # MediaPlayer + FavoriteItem
    light.py
    switch.py
    climate.py
    cover.py
    sensor.py
    binary_sensor.py
examples/
tests/
pyproject.toml
```

## Development

```bash
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"

# Run the full test suite with coverage (target: ≥ 90 %).
pytest --cov=ha_client --cov-report=term-missing

# Lint and type-check.
ruff check .
mypy ha_client/
```

## License

Apache 2.0 – see `LICENSE` for details.
