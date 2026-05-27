# HaClient

Async-first, high-level Python client for Home Assistant with REST and
WebSocket support.

## Features

- Hexagonal architecture: a thin facade over `Connection`, `EventBus`,
  `ServiceCaller`, and `StateStore`.
- Domain plugin model: built-ins register at import time; third parties
  ship via the `haclient.domains` entry-point group.
- Async context manager with automatic WebSocket connect, race-free
  state priming, and reconnect-aware refresh.
- Typed domain accessors: `air_quality`, `binary_sensor`, `climate`,
  `cover`, `event`, `fan`, `humidifier`, `light`, `lock`,
  `media_player`, `scene`, `sensor`, `switch`, `timer`, `vacuum`,
  `valve`.
- Real-time state-change listeners with attribute and transition
  filtering.
- Synchronous blocking wrapper for scripts, REPL, and Jupyter.
- Explicit service-call routing (`prefer="ws" | "rest" | "auto"`)
  available via `client.services.call(...)` for advanced use; the
  normal path is the high-level domain methods.
- Fully typed (PEP 561) with strict mypy enforcement.

## Next steps

- New here? Start with the [Guides](guides/index.md) — they walk
  through async lifecycle, listeners, reconnect handling, custom
  domains, and per-domain workflows.
- Looking up a specific method or class? See the
  [API Reference](reference/index.md).
- Curious how the pieces fit together? Read the
  [Architecture](architecture.md) document.

## Installation

```bash
pip install haclient
```

Or from source:

```bash
git clone https://github.com/graphras-com/HaClient.git
cd HaClient
pip install .
```

## Quick Start

### Async

```python
from haclient import HAClient

async with HAClient.from_url("http://localhost:8123", token="YOUR_TOKEN") as ha:
    light = ha.light("kitchen")
    await light.set_brightness(200)

    # Generic accessor — works for any registered domain.
    fan = ha.fan("ceiling")
    await fan.set_percentage(75)

    # Domain-level operations.
    await ha.scene.apply({"light.ceiling": {"state": "on", "brightness": 120}})
```

### Synchronous

```python
from haclient import SyncHAClient

with SyncHAClient.from_url("http://localhost:8123", token="YOUR_TOKEN") as ha:
    light = ha.light("kitchen")
    light.set_brightness(200)
```

### Adding a custom domain

Use this extension point to add a domain that HaClient does not ship
with. Built-in domains such as `fan`, `light`, and `cover` are already
registered at import time and cannot be replaced.

Register *before* constructing the client — active domains are
snapshotted at `HAClient` construction time.

```python
from haclient import DomainSpec, Entity, register_domain

class Sprinkler(Entity):
    domain = "sprinkler"

    async def start(self, duration: int) -> None:
        # Extension implementation: call the underlying HA service directly.
        await self._call_service("start", {"duration": duration})

register_domain(DomainSpec(name="sprinkler", entity_cls=Sprinkler))
```

Once registered, the domain is reachable through the same accessors as
built-ins:

```python
async with HAClient.from_url("http://localhost:8123", token="YOUR_TOKEN") as ha:
    sprinkler = ha.domain("sprinkler")["lawn"]
    await sprinkler.start(600)
```

See the [Custom domains and plugins guide](guides/custom-domains.md)
for collection-level operations, event routing, listener
decorators, and entry-point publishing.
