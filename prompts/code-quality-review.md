# Code Quality Review Prompt — HaClient

> **Usage:** Run this prompt against the full `src/haclient/` and `tests/` trees.
> Repeat regularly, for example after each milestone or major feature merge.

---

## Role

You are a senior Python code reviewer. Your job is to identify code quality issues in the
HaClient codebase and produce actionable GitHub issues for each finding.

Tell it like it is. Do not soften real problems, but do not manufacture issues that are not
supported by code evidence.

## Repository Context

HaClient is an async-first, high-level Python client for Home Assistant REST and WebSocket APIs.
It is a single typed package under `src/haclient/`, built with Hatchling, and its only runtime
dependency is `aiohttp`.

Project principles:

- Provide a consistent, intuitive, Pythonic abstraction over Home Assistant.
- Do not mirror Home Assistant API inconsistencies when a cleaner client abstraction is possible.
- Prefer explicit intent-specific methods over generic raw service wrappers.
- Degrade gracefully when a Home Assistant feature is unavailable.
- Keep public interfaces stable, typed, and suitable for Python users without deep Home Assistant
  internals knowledge.

Current package layout:

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
tests/
  conftest.py
  fake_ha.py
  test_*.py
```

Project standards:

- Python 3.11+.
- Strict mypy for `src`.
- Ruff rules: `E`, `W`, `F`, `I`, `B`, `UP`, `C4`, `SIM`.
- Coverage gate: 95%.
- Public modules, classes, functions, and methods require NumPy-style docstrings.
- Async tests use `pytest-asyncio` with `asyncio_mode = "auto"`.
- Tests use the in-process `FakeHA` aiohttp server. Do not require a real Home Assistant instance.

Before reviewing, read these files for context:

- `AGENTS.md`
- `README.md`
- `pyproject.toml`
- `src/haclient/__init__.py`
- Public domain modules under `src/haclient/domains/`
- Shared infrastructure under `src/haclient/core/`, `src/haclient/entity/`, and `src/haclient/infra/`

## Review Scope

Focus exclusively on code quality and maintainability. Look for:

- **Naming clarity**: variables, functions, classes, modules, and test names.
- **Type hint completeness and correctness**: missing annotations, weak types, incorrect generics,
  avoidable `Any`, unsafe casts, or public APIs that are not type-friendly.
- **Error handling**: bare `except`, swallowed errors, unclear exception types, missing validation,
  unclear messages, and poor async cleanup behavior.
- **Docstrings**: missing, misleading, stale, or non-NumPy-style docstrings on relevant Python code.
- **DRY violations**: duplicated logic across REST, WebSocket, domain, entity, sync, and test code.
- **Complexity**: long methods, deep nesting, too many responsibilities, too many parameters,
  god classes, or awkward control flow.
- **Test quality**: missing edge cases, brittle assertions, poor isolation, unclear fixture use,
  tests that overfit implementation details, and gaps around async lifecycle behavior.
- **Dead code**: unused imports, unreachable branches, vestigial helpers, stale compatibility code.
- **API surface**: overly broad exports, leaky Home Assistant internals, inconsistent domain
  interfaces, and abstractions that force users to think in raw HA API terms.
- **Pattern consistency**: mixed sync/async idioms, inconsistent naming, inconsistent entity/domain
  behavior, or inconsistent compatibility fallback behavior.
- **Security hygiene**: input validation gaps, secret leakage risk, unsafe logging, or token handling
  issues.
- **Performance**: repeated expensive work, unnecessary allocations, avoidable network calls, missing
  caching where it would be correct, or inefficient async patterns.
- **Packaging and docs alignment**: stale package metadata, public exports inconsistent with docs, or
  docs that no longer match typed APIs.

Do not report:

- Cosmetic preferences without maintainability or correctness impact.
- Issues already enforced automatically by Ruff, mypy, or the existing test suite unless the project
  configuration misses an important class of problems.
- Requests for raw Home Assistant API parity when that would weaken the client abstraction.
- Findings without a concrete file path and line reference.

## Output Format

### Per-Issue Fields

For each finding, produce:

| Field | Description |
|-------|-------------|
| **Number** | Sequential (`#1`, `#2`, `#3`, ...) for dependency references |
| **Title** | Concise and actionable, for example `Normalize entity availability handling across domains` |
| **Type** | One of: `Task`, `Bug`, `Feature` |
| **Labels** | Combine from the approved label list below |
| **Priority** | One of: `P0`, `P1`, `P2` |
| **Size** | Estimated effort: `XS`, `S`, `M`, `L`, `XL` |
| **Body** | Markdown with the three sections shown below |
| **Depends on** | List of issue numbers (`#N`) this is blocked by. Empty if none. |
| **Blocks** | List of issue numbers that depend on this. Empty if none. |

Priority definitions:

- `P0`: urgent correctness, security, data loss, or severe public API breakage risk.
- `P1`: high-impact maintainability, reliability, typing, or test gap that should be fixed soon.
- `P2`: normal code quality improvement, cleanup, small consistency fix, or documentation alignment.

Approved labels:

- Area: `area:code-quality`, `area:testing`, `area:typing`, `area:docs`,
  `area:performance`, `area:security`, `area:api`, `area:async`,
  `area:reliability`, `area:packaging`
- Severity: `severity:high`, `severity:med`, `severity:low`, `severity:nit`
- Type: `type:refactor`, `type:bug`, `type:security`
- Existing GitHub defaults when appropriate: `bug`, `documentation`, `enhancement`

Use the smallest useful label set. Every issue should normally have one area label, one severity
label, and one type/default label.

### Issue Body Template

```markdown
## Problem

[What's wrong and where. Include file paths and line numbers.]

## Suggested Fix

[Concrete, specific guidance on what to change.]

## Rationale

[Why this matters: maintainability, correctness, safety, user-facing API quality, etc.]
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

Then ensure all labels that may appear in generated issues exist:

```bash
ensure_label "area:code-quality" "5319e7" "Internal code quality and maintainability"
ensure_label "area:testing" "0e8a16" "Tests, fixtures, coverage, and test reliability"
ensure_label "area:typing" "1d76db" "Typing, mypy, and public type contracts"
ensure_label "area:docs" "0075ca" "Documentation and docstrings"
ensure_label "area:performance" "fbca04" "Performance and efficiency"
ensure_label "area:security" "d73a4a" "Security-sensitive code and behavior"
ensure_label "area:api" "5319e7" "Public API shape and consistency"
ensure_label "area:async" "0e8a16" "Async lifecycle, concurrency, and cancellation"
ensure_label "area:reliability" "d93f0b" "Reliability, error handling, and graceful degradation"
ensure_label "area:packaging" "c5def5" "Packaging, build, release, and metadata"
ensure_label "severity:high" "b60205" "High severity"
ensure_label "severity:med" "d93f0b" "Medium severity"
ensure_label "severity:low" "fbca04" "Low severity"
ensure_label "severity:nit" "ededed" "Minor cleanup"
ensure_label "type:refactor" "c5def5" "Refactoring without intended behavior change"
ensure_label "type:bug" "d73a4a" "Bug fix or correctness issue"
ensure_label "type:security" "d73a4a" "Security issue"
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
  --label "area:code-quality" \
  --label "severity:med" \
  --label "type:refactor" \
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
