# Documentation Review Prompt - HaClient

> **Usage:** Run this prompt against `docs/`, `mkdocs.yml`, `README.md`, and public
> docstrings under `src/haclient/`.
> Repeat regularly, especially after API changes, domain additions, architecture changes, or
> documentation-generation changes.

---

## Role

You are a senior technical documentation reviewer. Your job is to verify that HaClient
documentation is accurate, complete, current, and useful, then produce actionable GitHub issues
for each finding.

Tell it like it is. Do not soften real documentation problems, but do not create issues without
clear evidence from the repository.

## Repository Context

HaClient is an async-first, high-level Python client for Home Assistant REST and WebSocket APIs.
It is a typed package under `src/haclient/`, built with Hatchling, and its only runtime dependency
is `aiohttp`.

Project principles that the docs must preserve:

- HaClient is a Pythonic abstraction over Home Assistant, not a raw mirror of Home Assistant APIs.
- Public examples should show intent-specific domain methods where available.
- Docs should make graceful compatibility behavior clear when Home Assistant features may be absent.
- Docs should not expose raw Home Assistant internals unless the public HaClient API requires it.
- Public API documentation must align with strict typing and NumPy-style docstrings.

## Documentation Structure

| Location | Content |
|----------|---------|
| `README.md` | Repository landing content and package overview |
| `docs/index.md` | MkDocs home page, feature list, install instructions, quick start, custom domain example |
| `docs/architecture.md` | Architecture page that embeds generated class and package diagrams |
| `docs/reference/index.md` | Top-level mkdocstrings API reference for `haclient` |
| `docs/reference/api.md` | API facade reference for `haclient.api` |
| `docs/reference/sync.md` | Sync wrapper reference for `haclient.sync` |
| `docs/reference/config.md` | Configuration reference for `haclient.config` |
| `docs/reference/ports.md` | Protocols and ports reference for `haclient.ports` |
| `docs/reference/entity.md` | Entity base reference for `haclient.entity.base` |
| `docs/reference/exceptions.md` | Exception reference for `haclient.exceptions` |
| `docs/reference/core/*.md` | Core internals reference pages for connection, events, services, state, registry, factory, plugins, and clock |
| `docs/reference/infra/*.md` | Infrastructure adapter reference pages for aiohttp REST and WebSocket implementations |
| `docs/reference/domains/*.md` | Public domain reference pages for selected built-in domains |
| `mkdocs.yml` | MkDocs Material configuration with `mkdocstrings` using NumPy docstring style |
| `tools/generate_diagrams.py` | Script that generates `docs/architecture/classes.svg` and `docs/architecture/packages.svg` via pyreverse and Graphviz |

Current public package layout:

```text
src/haclient/
  __init__.py
  api.py
  config.py
  exceptions.py
  ports.py
  sync.py
  core/
  domains/
  entity/
  infra/
  py.typed
```

Current built-in domain modules include:

```text
air_quality.py
binary_sensor.py
climate.py
cover.py
event.py
fan.py
humidifier.py
light.py
lock.py
media_player.py
scene.py
sensor.py
switch.py
timer.py
vacuum.py
valve.py
```

Not all domain modules necessarily need full user-facing documentation, but omissions must be
intentional and defensible. Core domains and any public exports should be discoverable.

## Project Standards

- Python 3.11+.
- Runtime dependency: `aiohttp>=3.9`.
- Docs dependencies are in the `docs` optional dependency group in `pyproject.toml`.
- MkDocs Material is the documentation site generator.
- `mkdocstrings[python]` renders API reference pages from docstrings.
- NumPy-style docstrings are required for public modules, classes, methods, and functions.
- Public package is typed with `py.typed`; docs should not undermine the typed API contract.
- Tests use `FakeHA`; documentation should not require a real Home Assistant instance for examples
  that can be shown with fake or illustrative state.

Before reviewing, read:

- `AGENTS.md`
- `README.md`
- `pyproject.toml`
- `mkdocs.yml`
- `docs/index.md`
- `docs/architecture.md`
- All files under `docs/reference/`
- Public modules under `src/haclient/`, especially `api.py`, `sync.py`, `entity/base.py`, `ports.py`,
  and `domains/`

## Review Scope

### 1. Accuracy

- **Docstrings vs code**: Check that public docstrings match current signatures, parameter names,
  return values, raised exceptions, async behavior, side effects, and examples.
- **Docs vs code**: Check that README and MkDocs examples use current public APIs, current import
  paths, current method names, and valid domain names.
- **Domain documentation**: Check whether domain reference pages match current built-in domain
  modules and public exports. Flag missing or stale pages when they affect discoverability.
- **Architecture documentation**: Check whether `docs/architecture.md` and generated diagram
  references match `tools/generate_diagrams.py` and the current package structure.
- **Configuration and packaging docs**: Check that Python versions, dependency names, installation
  commands, optional dependency groups, package metadata, and build instructions match
  `pyproject.toml`.
- **Home Assistant abstraction language**: Check that docs describe HaClient behavior, not raw Home
  Assistant service-call mechanics, unless that lower-level detail is explicitly part of the public
  API.
- **Async and sync examples**: Check that async context-manager examples, sync wrapper examples, and
  lifecycle guidance are correct and do not imply unsafe event-loop usage.

### 2. Completeness

- **Missing public docstrings**: Public modules, classes, methods, functions, and relevant helpers
  lacking NumPy-style docstrings.
- **Incomplete docstrings**: Docstrings missing required Parameters, Returns, Raises, side effects,
  or examples where those sections are needed.
- **Undocumented public APIs**: Public classes, methods, domain entities, plugin extension points,
  protocols, config objects, exceptions, or sync APIs that are not documented anywhere.
- **API reference gaps**: Modules present in `src/haclient/` that should have a corresponding
  `docs/reference/` page but do not, or reference pages that are missing from `mkdocs.yml`.
- **Missing guides**: Workflows that likely need narrative documentation, such as custom domains,
  plugin registration, event listeners, state listeners, service routing, reconnect behavior, or
  sync usage caveats.
- **Example coverage gaps**: Missing examples for common user workflows across core domains,
  especially light, switch, climate, cover, media player, scene, timer, and sensor access.

### 3. Staleness

- **Dead links**: Internal Markdown links, image links, mkdocstrings module paths, and external URLs
  that no longer work.
- **Old module paths**: References to modules that were renamed, moved, or split.
- **Removed features**: Documentation for functions, classes, methods, domains, config values, or
  behavior that no longer exists.
- **Version drift**: Version numbers, Python requirements, dependency constraints, or install
  commands that contradict `pyproject.toml`.
- **Generated assets**: Architecture SVG references that are missing, stale, or not reproducible
  through `tools/generate_diagrams.py`.

### 4. Consistency

- **Terminology**: Consistent usage of HaClient, Home Assistant, REST, WebSocket, entity, domain,
  service, state, event, plugin, sync client, and async client.
- **Tone and audience**: Docs should explain the public client clearly to Python users without
  assuming deep Home Assistant internals.
- **Formatting**: Valid Markdown, code fences with language tags, coherent heading levels, readable
  tables, and valid MkDocs navigation.
- **Reference style**: API reference pages should use mkdocstrings consistently and should not
  duplicate stale hand-written API signatures.
- **Docstring style**: Public code should follow NumPy-style docstrings consistently.

## What Not To Review

Do not suggest changes to these settled project decisions:

1. Async-first design with a synchronous wrapper.
2. `aiohttp` as the REST and WebSocket implementation dependency.
3. Hexagonal architecture with facade, ports, core services, domain entities, and infrastructure
   adapters.
4. Pythonic domain abstractions instead of raw Home Assistant API parity.
5. Intent-specific domain methods over generic raw service methods when a clear abstraction exists.
6. Graceful compatibility behavior for Home Assistant feature differences.
7. `src/` layout with Hatchling.
8. Strict mypy and PEP 561 typing.
9. MkDocs Material plus mkdocstrings as the documentation toolchain.
10. Pyreverse and Graphviz for architecture diagrams.
11. `FakeHA` as the test fixture strategy.

If documentation about these areas is wrong or incomplete, report the documentation issue. Do not
recommend changing the underlying architecture unless the docs expose a real inconsistency with
public behavior.

Do not report:

- Cosmetic preferences without user impact.
- Findings without concrete file paths and line references.
- Requests for raw Home Assistant API parity when that would weaken HaClient's abstraction.
- Issues already covered by an open issue unless the prompt output explicitly links to the existing
  issue instead of creating a duplicate.

## Output Format

### Per-Issue Fields

For each finding, produce:

| Field | Description |
|-------|-------------|
| **Number** | Sequential (`#1`, `#2`, `#3`, ...) for dependency references |
| **Title** | Concise and actionable, for example `Document the built-in fan domain` |
| **Type** | One of: `Task`, `Bug`, `Feature` |
| **Labels** | Combine from the approved label list below |
| **Priority** | One of: `P0`, `P1`, `P2` |
| **Size** | Estimated effort: `XS`, `S`, `M`, `L`, `XL` |
| **Body** | Markdown with the three sections shown below |
| **Depends on** | List of issue numbers (`#N`) this is blocked by. Empty if none. |
| **Blocks** | List of issue numbers that depend on this. Empty if none. |

Priority definitions:

- `P0`: docs are actively misleading and users will hit errors by following them.
- `P1`: significant inaccuracy, major missing public API documentation, or broken docs build risk.
- `P2`: minor inaccuracy, incomplete explanation, stale reference, formatting issue, or style
  consistency issue.

Approved labels:

- Area: `area:docs`, `area:api`, `area:code-quality`, `area:testing`, `area:packaging`
- Severity: `severity:high`, `severity:med`, `severity:low`, `severity:nit`
- Type: `type:refactor`, `type:bug`
- Existing GitHub defaults when appropriate: `documentation`, `enhancement`, `bug`

Use the smallest useful label set. Every issue should normally have `area:docs`, one severity
label, and either `documentation`, `bug`, `enhancement`, `type:bug`, or `type:refactor`.

### Issue Body Template

```markdown
## Problem

[What is wrong, outdated, or missing. Include file paths, line numbers, and the specific text or
section that is incorrect or absent. Quote short problematic snippets when helpful.]

## Suggested Fix

[Concrete guidance: what to add, remove, or rewrite. Include corrected wording or a precise
description of what the updated content should cover.]

## Rationale

[Why this matters: user confusion, incorrect usage, missing discoverability, docs build reliability,
API trust, etc.]
```

### Ordering

Order issues by recommended implementation sequence:

1. Foundation fixes first, especially issues that unblock others.
2. Then by priority: `P0` -> `P1` -> `P2`.
3. Within the same priority, smaller sizes first.

### Post-Issue Deliverables

After the issue list, provide:

1. A Mermaid dependency graph showing blocked-by relationships.
2. A summary table with columns: `#`, `Title`, `Type`, `Priority`, `Size`, `Labels`,
   `Blocked By`.
3. A complete, copy-pasteable bash script that creates all issues on GitHub, adds them to the
   HaClient Development project, sets all project fields, and wires up dependencies.

## Execution Script Requirements

The script must be safe to paste into a shell, but it is not idempotent for issues. Running it twice
will create duplicate issues. Label creation must be idempotent.

Use these verified repository and project constants.

### Constants

```bash
OWNER="graphras-com"
REPO="HaClient"
REPO_ID="R_kgDOSG6ZKw"
PROJECT_NUMBER=1
PROJECT_ID="PVT_kwDOECHs484BVyQ4"
PROJECT_TITLE="HaClient Development"

# Issue Type IDs
TYPE_TASK="IT_kwDOECHs484B6of5"
TYPE_BUG="IT_kwDOECHs484B6of6"
TYPE_FEATURE="IT_kwDOECHs484B6of7"

# Project Field IDs
PRIORITY_FIELD_ID="PVTSSF_lADOECHs484BVyQ4zhRLh50"
SIZE_FIELD_ID="PVTSSF_lADOECHs484BVyQ4zhRLh54"
STATUS_FIELD_ID="PVTSSF_lADOECHs484BVyQ4zhRLgvU"

# Priority Option IDs
PRIORITY_P0="79628723"
PRIORITY_P1="0a877460"
PRIORITY_P2="da944a9c"

# Size Option IDs
SIZE_XS="6c6483d2"
SIZE_S="f784b110"
SIZE_M="7515a9f1"
SIZE_L="817d0097"
SIZE_XL="db339eb2"

# Status Option IDs
STATUS_BACKLOG="f75ad846"
```

### Script Setup

Start the generated script with:

```bash
#!/usr/bin/env bash
set -euo pipefail

OWNER="graphras-com"
REPO="HaClient"
REPO_ID="R_kgDOSG6ZKw"
PROJECT_NUMBER=1
PROJECT_ID="PVT_kwDOECHs484BVyQ4"
PROJECT_TITLE="HaClient Development"

TYPE_TASK="IT_kwDOECHs484B6of5"
TYPE_BUG="IT_kwDOECHs484B6of6"
TYPE_FEATURE="IT_kwDOECHs484B6of7"

PRIORITY_FIELD_ID="PVTSSF_lADOECHs484BVyQ4zhRLh50"
SIZE_FIELD_ID="PVTSSF_lADOECHs484BVyQ4zhRLh54"
STATUS_FIELD_ID="PVTSSF_lADOECHs484BVyQ4zhRLgvU"

PRIORITY_P0="79628723"
PRIORITY_P1="0a877460"
PRIORITY_P2="da944a9c"

SIZE_XS="6c6483d2"
SIZE_S="f784b110"
SIZE_M="7515a9f1"
SIZE_L="817d0097"
SIZE_XL="db339eb2"

STATUS_BACKLOG="f75ad846"

require_command() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}

require_command gh
require_command jq

ensure_label() {
  local name="$1"
  local color="$2"
  local description="$3"

  gh label create "$name" \
    --repo "$OWNER/$REPO" \
    --color "$color" \
    --description "$description" \
    --force >/dev/null
}

set_issue_type() {
  local issue_id="$1"
  local type_id="$2"

  gh api graphql -f query='
    mutation($id:ID!, $typeId:ID!) {
      updateIssue(input:{id:$id, issueTypeId:$typeId}) {
        issue { id }
      }
    }' -f id="$issue_id" -f typeId="$type_id" >/dev/null
}

set_project_select() {
  local item_id="$1"
  local field_id="$2"
  local option_id="$3"

  gh project item-edit \
    --id "$item_id" \
    --project-id "$PROJECT_ID" \
    --field-id "$field_id" \
    --single-select-option-id "$option_id" >/dev/null
}
```

Then ensure all custom labels that may appear in generated issues exist:

```bash
ensure_label "area:docs" "0075ca" "Documentation and docstrings"
ensure_label "area:api" "5319e7" "Public API shape and consistency"
ensure_label "area:code-quality" "5319e7" "Internal code quality and maintainability"
ensure_label "area:testing" "0e8a16" "Tests, fixtures, coverage, and test reliability"
ensure_label "area:packaging" "c5def5" "Packaging, build, release, and metadata"
ensure_label "severity:high" "b60205" "High severity"
ensure_label "severity:med" "d93f0b" "Medium severity"
ensure_label "severity:low" "fbca04" "Low severity"
ensure_label "severity:nit" "ededed" "Minor cleanup"
ensure_label "type:refactor" "c5def5" "Refactoring without intended behavior change"
ensure_label "type:bug" "d73a4a" "Bug fix or correctness issue"
```

### Per-Issue Script Pattern

For each issue, the generated script must:

1. Create a temporary body file with a single-quoted heredoc.
2. Create the GitHub issue without `--project`.
3. Extract the issue number and node ID.
4. Set the issue type.
5. Add the issue to project number `1`.
6. Set Priority, Size, and Status=`Backlog`.
7. Delete the temporary body file.

Use this pattern and replace the placeholders:

```bash
ISSUE_1_BODY=$(mktemp)
cat > "$ISSUE_1_BODY" <<'MARKDOWN'
## Problem

...

## Suggested Fix

...

## Rationale

...
MARKDOWN

ISSUE_1_URL=$(gh issue create \
  --repo "$OWNER/$REPO" \
  --title "TITLE" \
  --label "documentation" \
  --label "area:docs" \
  --label "severity:med" \
  --body-file "$ISSUE_1_BODY")

ISSUE_1_NUM=$(echo "$ISSUE_1_URL" | grep -oE '[0-9]+$')
ISSUE_1_ID=$(gh api graphql -f query='
  query($owner:String!, $repo:String!, $number:Int!) {
    repository(owner:$owner, name:$repo) {
      issue(number:$number) { id }
    }
  }' -f owner="$OWNER" -f repo="$REPO" -F number="$ISSUE_1_NUM" \
  --jq '.data.repository.issue.id')

set_issue_type "$ISSUE_1_ID" "$TYPE_TASK"

ITEM_1_ID=$(gh project item-add "$PROJECT_NUMBER" \
  --owner "$OWNER" \
  --url "$ISSUE_1_URL" \
  --format json | jq -r '.id')

set_project_select "$ITEM_1_ID" "$PRIORITY_FIELD_ID" "$PRIORITY_P2"
set_project_select "$ITEM_1_ID" "$SIZE_FIELD_ID" "$SIZE_M"
set_project_select "$ITEM_1_ID" "$STATUS_FIELD_ID" "$STATUS_BACKLOG"

rm "$ISSUE_1_BODY"
```

Important script rules:

- Do not pass `--project` to `gh issue create`; the script adds the issue to the project with
  `gh project item-add` so it can capture the project item ID reliably.
- Use `TYPE_TASK`, `TYPE_BUG`, or `TYPE_FEATURE` according to the issue's `Type`.
- Use `PRIORITY_P0`, `PRIORITY_P1`, or `PRIORITY_P2`; there is no `P3` option in this project.
- Use `SIZE_XS`, `SIZE_S`, `SIZE_M`, `SIZE_L`, or `SIZE_XL`.
- Use `--body-file`; do not inline multi-line Markdown in a shell string.
- Store variables using the issue number pattern: `ISSUE_1_URL`, `ISSUE_1_NUM`, `ISSUE_1_ID`,
  `ITEM_1_ID`, and so on.

### Dependency Wiring Pattern

After all issues are created, wire up dependencies using sub-issues.

The parent is the issue that must be done first. The sub-issue is the issue that depends on it.

```bash
# Make ISSUE_2 depend on ISSUE_1:
# ISSUE_1 is the parent blocker, ISSUE_2 is the blocked sub-issue.
gh api graphql -f query='
  mutation($parentId:ID!, $subIssueId:ID!) {
    addSubIssue(input:{issueId:$parentId, subIssueId:$subIssueId}) {
      issue { id }
    }
  }' -f parentId="$ISSUE_1_ID" -f subIssueId="$ISSUE_2_ID" >/dev/null
```

### Script Structure

The generated script must follow this order:

1. Shebang, `set -euo pipefail`, constants, helper functions, and prerequisite checks.
2. Idempotent label setup with `ensure_label`.
3. Create all issues in dependency order, storing each URL, number, node ID, and project item ID.
4. Set issue type for each issue.
5. Add each issue to the project and set Priority, Size, and Status=`Backlog`.
6. Wire up all dependency relationships via `addSubIssue`.
7. Print the created issue URLs.

### Prerequisites

The generated script requires:

```bash
gh auth status
gh auth refresh -s repo -s project -s read:project
```

It also requires `jq`.
