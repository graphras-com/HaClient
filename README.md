# HaClient

[![CI](https://github.com/graphras-com/HaClient/actions/workflows/ci.yml/badge.svg)](https://github.com/graphras-com/HaClient/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue)](https://www.python.org)
[![gitleaks](https://img.shields.io/badge/protected%20by-gitleaks-blue)](https://github.com/gitleaks/gitleaks)
[![Dependabot](https://img.shields.io/badge/dependabot-enabled-brightgreen?logo=dependabot)](https://github.com/graphras-com/HaClient/network/updates)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)

Async-first, high-level Python client for Home Assistant with REST and WebSocket support. Provides typed domain accessors, real-time state tracking, automatic reconnection, and a synchronous wrapper for scripts and REPL use.

**[Documentation](https://graphras-com.github.io/HaClient/)**

## Features

- Async context manager with automatic WebSocket connection and state priming
- Typed domain accessors: light, switch, climate, cover, sensor, binary sensor, media player, scene, timer
- Intent-specific methods over raw service calls (e.g. `light.set_brightness(200)` instead of `light.turn_on(brightness=200)`)
- Real-time state change listeners with granular attribute and state-transition filtering
- Synchronous blocking wrapper for scripts, REPL, and Jupyter
- Automatic WebSocket reconnection with exponential backoff
- Configurable service routing policy (`ws`, `rest`, or `auto`)
- Plugin system for third-party domain extensions via entry points
- Fully typed (PEP 561) with strict mypy enforcement
- Single runtime dependency (`aiohttp`)

## Requirements

- Python 3.11+
- A running Home Assistant instance
- A long-lived access token from Home Assistant

## Installation

```bash
pip install haclient
```

Or install from source:

```bash
git clone https://github.com/graphras-com/HaClient.git
cd HaClient
pip install .
```

## Usage

### Async

```python
from haclient import HAClient

async with HAClient.from_url("http://localhost:8123", token="YOUR_TOKEN") as ha:
    light = ha.light("kitchen")
    await light.set_brightness(200)
    await light.set_kelvin(3000)

    switch = ha.switch("garage_door")
    await switch.off()

    # Listen for state changes
    sensor = ha.sensor("outdoor_temperature")
    sensor.on_value_change(lambda old, new: print(f"Temp: {old} -> {new}"))
```

### Synchronous

```python
from haclient import SyncHAClient

with SyncHAClient.from_url("http://localhost:8123", token="YOUR_TOKEN") as ha:
    light = ha.light("kitchen")
    light.set_brightness(200)

    player = ha.media_player("living_room")
    player.set_volume(0.5)
```

## Configuration

Create a client with `HAClient.from_url()` or by passing a `ConnectionConfig` directly:

- **`base_url`** -- Base URL of your Home Assistant instance (e.g. `http://localhost:8123`)
- **`token`** -- Long-lived access token generated from the Home Assistant UI
- **`reconnect`** -- Enable automatic WebSocket reconnection (default: `True`)
- **`ping_interval`** -- WebSocket keepalive interval in seconds (default: `30`)
- **`request_timeout`** -- Timeout for REST and WS commands in seconds (default: `10`)
- **`verify_ssl`** -- Verify SSL certificates (default: `True`)
- **`service_policy`** -- Service call routing: `"ws"`, `"rest"`, or `"auto"` (default: `"auto"`)

Store tokens securely using environment variables or a secrets manager. Do not commit tokens to version control.

## Development

Install development dependencies:

```bash
pip install -e ".[dev]"
```

Run tests:

```bash
pytest
```

Run tests with coverage:

```bash
pytest --cov=haclient --cov-report=term-missing
```

Lint and format:

```bash
ruff check src tests
ruff format --check src tests
```

Type checking:

```bash
mypy src
```

## Security

- Never commit Home Assistant tokens or secrets to the repository
- Gitleaks runs on every CI pipeline execution to detect accidentally committed secrets
- The `.gitignore` excludes `.env` files by default

## CI/CD

GitHub Actions workflows handle:

- **Lint** -- Ruff check and format verification
- **Type Check** -- Strict mypy analysis
- **Tests** -- Pytest matrix across Python 3.11/3.12/3.13 with 95% coverage threshold
- **Secrets Scan** -- Gitleaks full-history scan
- **Release** -- Automated GitHub release on `v*` tags
- **Dependabot** -- Weekly dependency updates for pip and GitHub Actions

## Contributing

Contributions are welcome. Please open an issue or pull request. Follow existing code style and ensure all CI checks pass before submitting.

## License

Apache-2.0 -- see [LICENSE](LICENSE).
