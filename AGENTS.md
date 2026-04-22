# AGENTS.md

## Workflow

All work MUST be done on a feature branch — never commit directly to `main`.

1. **Create a branch** from `main` before starting any work:
   ```bash
   git checkout main && git pull
   git checkout -b <type>/<short-description>   # e.g. feat/add-fan-domain, fix/ws-reconnect
   ```
2. **Implement the change** — code, tests, and documentation (see checklists below).
3. **Run the full check suite** (lint → type-check → tests) and ensure it passes.
4. **Commit and push** the branch:
   ```bash
   git add -A && git commit -m "<descriptive message>"
   git push -u origin HEAD
   ```
5. **Create a Pull Request** against `main`:
   ```bash
   gh pr create --fill
   ```

### Change Checklist

Every change MUST include **all** of the following:

- [ ] **Tests** — new or updated tests covering the change with **≥ 95% coverage** for affected modules. Verify with:
  ```bash
  pytest --cov=ha_client --cov-report=term-missing --cov-fail-under=95
  ```
- [ ] **Documentation** — update relevant files in `docs/` to reflect the change (new features get a new or updated doc page).
- [ ] **README.md** — update the project README if the change affects public API, installation, usage examples, or feature list.
- [ ] **Lint & type-check pass** — `ruff check .` and `mypy ha_client/` must be clean.

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

# Tests with coverage (target ≥95%)
pytest --cov=ha_client --cov-report=term-missing --cov-fail-under=95

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
