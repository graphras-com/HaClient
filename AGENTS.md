# AGENTS.md

## Project

HaClient — async Python client for Home Assistant (REST + WebSocket). Single package at `src/haclient/`, built with Hatchling, sole runtime dep is `aiohttp`.

## Core Mission

Provide a consistent, intuitive, and Pythonic abstraction over the Home Assistant API.

Do not mirror the API. Improve it.

### Non-Negotiable Rules

* Consistency over fidelity
    Do not replicate inconsistent API patterns.
* Explicit intent over generic services
    Avoid exposing raw service calls like turn_on when intent-specific methods are clearer.
* Graceful compatibility handling
    Detect feature support and degrade safely. Never break user code due to missing capabilities.
* Pythonic design
    Interfaces must feel like Python objects, not HTTP wrappers.

### Abstraction Rules

* Map entities to structured Python objects.
* Normalize domain inconsistencies.
* Split overloaded API actions into clear methods.

Example:

* ❌ light.turn_on(brightness=50)
* ✅ light.set_brightness(50)

### Design Priorities

1. Core domains must be clean and stable (Light, Lock, Media Player, Sensor, etc.)
2. Extend coverage without introducing inconsistency
3. Support advanced/edge domains only after core stability

### Anti-Goals

* Do not expose raw API complexity unless necessary
* Do not enforce strict API parity
* Do not design around Home Assistant internals—design around user expectations

### Implementation Standard

Every feature must answer:

* Is this intuitive without Home Assistant knowledge?
* Is this consistent with other domains?
* Does this degrade safely if unsupported?

If not, redesign it.

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
   python -m pytest tests/ --cov=haclient --cov-report=term-missing --cov-fail-under=95
   ```
4. **Commit** — only after all tests pass.
5. **Push and create a PR**:
   ```
   git push -u origin <branch>
   gh pr create --title "..." --body "..."
   ```

**Never commit directly to `main`.** No exceptions.

## Docstring convention

All AI agents modifying this repository must write NumPy-style docstrings for all relevant Python code.

Use NumPy-style docstrings for:

- Public modules
- Public classes
- Public methods
- Public functions
- Non-obvious private helpers
- Complex test fixtures or utilities

Docstrings must describe:

- Purpose and behavior
- Parameters
- Return values
- Raised exceptions, where relevant
- Side effects, where relevant
- Examples, when useful

Use this format:

```python
def example_function(name: str, retries: int = 3) -> bool:
    """Validate a named operation.

    Parameters
    ----------
    name : str
        Name of the operation to validate.
    retries : int, default=3
        Number of retry attempts before failing.

    Returns
    -------
    bool
        True if the operation is valid, otherwise False.

    Raises
    ------
    ValueError
        If ``name`` is empty.
    """
```

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
