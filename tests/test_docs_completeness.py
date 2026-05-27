"""Documentation completeness tests.

Guards against drift between registered built-in domains and the
documentation surface (MkDocs nav and reference pages). See issue #90.
"""

from __future__ import annotations

from pathlib import Path

import haclient.domains  # noqa: F401  -- registers built-in domains
from haclient.core.plugins import DomainRegistry

REPO_ROOT = Path(__file__).resolve().parents[1]
DOMAINS_DIR = REPO_ROOT / "docs" / "reference" / "domains"
MKDOCS_YML = REPO_ROOT / "mkdocs.yml"


def _registered_builtin_domains() -> set[str]:
    """Return the set of built-in domain names registered at import time.

    Returns
    -------
    set of str
        Names registered via ``haclient.domains.__init__`` imports.
    """
    return set(DomainRegistry.shared().names())


def test_every_builtin_domain_has_reference_page() -> None:
    """Every registered built-in domain must have a Markdown reference page."""
    expected = _registered_builtin_domains()
    existing = {p.stem for p in DOMAINS_DIR.glob("*.md")}
    missing = expected - existing
    assert not missing, f"Missing domain reference pages: {sorted(missing)}"


def test_every_builtin_domain_listed_in_mkdocs_nav() -> None:
    """Every registered built-in domain must appear in the MkDocs nav."""
    nav_text = MKDOCS_YML.read_text(encoding="utf-8")
    expected = _registered_builtin_domains()
    missing = {name for name in expected if f"reference/domains/{name}.md" not in nav_text}
    assert not missing, f"Domains missing from mkdocs.yml nav: {sorted(missing)}"
