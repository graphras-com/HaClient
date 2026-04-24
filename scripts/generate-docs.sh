#!/usr/bin/env bash
# Generate API reference markdown from docstrings using pydoc-markdown.
# Usage: ./scripts/generate-docs.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DOCS_DIR="$REPO_ROOT/docs/reference"
SRC_DIR="$REPO_ROOT/src"

mkdir -p "$DOCS_DIR"

# Core modules
MODULES=(
    client
    sync
    rest
    websocket
    entity
    registry
    exceptions
)

for mod in "${MODULES[@]}"; do
    echo "  -> docs/reference/$mod.md"
    pydoc-markdown -I "$SRC_DIR" -m "haclient.$mod" > "$DOCS_DIR/$mod.md"
done

# Domain modules
DOMAIN_DIR="$SRC_DIR/haclient/domains"
for f in "$DOMAIN_DIR"/*.py; do
    name="$(basename "$f" .py)"
    [[ "$name" == "__init__" ]] && continue
    echo "  -> docs/reference/domains_$name.md"
    pydoc-markdown -I "$SRC_DIR" -m "haclient.domains.$name" > "$DOCS_DIR/domains_$name.md"
done

echo "Done. Documentation written to docs/reference/"
