# AGENTS.md

## Setup

```bash
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
```

Python 3.11+ required (`.python-version` pins 3.11).

## Commands

```bash
# Lint
ruff check .

# Type-check (strict mode)
mypy ha_client/

# Tests with coverage (target ≥90%)
pytest --cov=ha_client --cov-report=term-missing

# Single test file
pytest tests/test_client.py

# Single test
pytest tests/test_client.py::test_name -x
```

Run order: `ruff check .` → `mypy ha_client/` → `pytest`

## Architecture

- `ha_client/client.py` — `HAClient`, the main async facade (REST + WebSocket)
- `ha_client/websocket.py` — low-level WS with auth, keepalive, auto-reconnect
- `ha_client/rest.py` — REST API client
- `ha_client/registry.py` — entity registry (state tracking)
- `ha_client/entity.py` — base `Entity` with state-change dispatch
- `ha_client/sync.py` — `SyncHAClient`, blocking wrapper running event loop in background thread
- `ha_client/domains/` — domain entity classes (`MediaPlayer`, `Light`, `Switch`, `Climate`, `Cover`, `Sensor`, `BinarySensor`)

## Testing

- All tests use a hermetic `FakeHA` server (`tests/fake_ha.py`) — no real HA instance needed
- `pytest-asyncio` with `asyncio_mode = "auto"` — async test functions run automatically, no `@pytest.mark.asyncio` needed
- Fixtures `fake_ha` and `client` in `tests/conftest.py` provide a running fake server and connected client

## Style

- Ruff line length: 100
- Ruff rules: E, W, F, I (isort), B (bugbear, B008 ignored), UP, C4, SIM
- mypy strict mode on `ha_client/`; tests are exempt from `disallow_untyped_defs`
- Build backend: hatchling
