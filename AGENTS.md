# AGENTS.md

## Project

HaClient — async Python client for Home Assistant (REST + WebSocket). Single package at `src/haclient/`, built with Hatchling, sole runtime dep is `aiohttp`.

## Setup

```bash
pip install -e ".[dev]"
```

Uses `uv.lock`; if `uv` is available prefer `uv pip install -e ".[dev]"`.

Python 3.11+ required (`.python-version` pins 3.11).

## Mandatory workflow — read this FIRST

You MUST follow this sequence for every task. Do not write any code before step 1.

1. **Create a branch** from up-to-date `main`:
   ```
   git checkout main && git pull
   git checkout -b <prefix>/<name>
   ```
2. **Do the work.**
3. **Run the full test suite** — every test must pass before you commit:
   ```
   python -m pytest tests/ --cov=deckui --cov-report=term-missing --cov-fail-under=95
   ```
4. **Commit** — only after all tests pass.
5. **Push and create a PR**:
   ```
   git push -u origin <branch>
   gh pr create --title "..." --body "..."
   ```

**Never commit directly to `main`.** No exceptions.

## Commands

```bash
# Lint (ruff)
ruff check src tests
ruff format --check src tests

# Type check (strict mypy)
mypy src

# Tests
pytest
pytest --cov=haclient --cov-report=term-missing

# Single test file
pytest tests/test_client.py

# Single test
pytest tests/test_client.py::test_name -x
```

CI order: lint, typecheck, and tests run in parallel. All must pass (quality gate).

## CI thresholds

- **Coverage: 95%** — CI fails below this (`coverage-threshold: 95`).
- Test matrix: Python 3.11, 3.12, 3.13.

## Code layout

```
src/haclient/
  client.py      # HAClient — main async context-manager client
  sync.py         # SyncHAClient — blocking wrapper
  rest.py         # REST API calls
  websocket.py    # WebSocket connection & reconnect
  entity.py       # Entity base
  domains/        # Typed domain accessors (light, switch, climate, etc.)
  registry.py     # Entity registry
  exceptions.py   # Custom exceptions
  py.typed        # PEP 561 marker
```

## Testing quirks

- `pytest-asyncio` with `asyncio_mode = "auto"` — async test functions need no decorator.
- Tests use `FakeHA` (`tests/fake_ha.py`), an in-process aiohttp server. No real HA instance needed.
- Fixtures `fake_ha` and `client` are in `tests/conftest.py`.

## Style

- Ruff line length: **100**.
- Ruff rules: E, W, F, I (isort), B, UP, C4, SIM. `B008` ignored globally; `B011` ignored in tests.
- mypy strict mode. `ignore_missing_imports = false` — all imports must have stubs or type info.
- Tests are exempt from `disallow_untyped_defs`.
