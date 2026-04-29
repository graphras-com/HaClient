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
- Typed domain accessors: `light`, `switch`, `climate`, `cover`,
  `sensor`, `binary_sensor`, `media_player`, `scene`, `timer`.
- Real-time state-change listeners with attribute and transition
  filtering.
- Synchronous blocking wrapper for scripts, REPL, and Jupyter.
- Explicit service-call routing: `prefer="ws" | "rest" | "auto"`.
- Fully typed (PEP 561) with strict mypy enforcement.

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
    fan = ha.domain("fan")["ceiling"]
    # await fan.set_speed(75)

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

```python
from haclient import register_domain, DomainSpec, Entity

class Fan(Entity):
    domain = "fan"

    async def set_speed(self, pct: int) -> None:
        await self._call_service("set_percentage", {"percentage": pct})

register_domain(DomainSpec(name="fan", entity_cls=Fan))
```

Built-in or third-party — both routes are equivalent.
