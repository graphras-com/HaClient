"""MkDocs hooks for the HaClient documentation build.

This module is wired into ``mkdocs.yml`` via the ``hooks`` setting so that
every documentation build regenerates the architecture diagrams from source
before MkDocs validates inter-page links.

If the system prerequisites for diagram generation (``pyreverse`` and the
Graphviz ``dot`` binary) are missing, the hook writes minimal placeholder
SVG files instead of failing.  This keeps ``mkdocs build --strict`` working
in environments that do not have Graphviz installed while still producing
real diagrams in CI and in normal development setups.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mkdocs.config.defaults import MkDocsConfig

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "docs" / "architecture"
EXPECTED_FILES = ("classes.svg", "packages.svg")

_PLACEHOLDER_SVG = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<svg xmlns="http://www.w3.org/2000/svg" width="480" height="80" '
    'viewBox="0 0 480 80">\n'
    '  <rect width="100%" height="100%" fill="#f5f5f5" stroke="#999"/>\n'
    '  <text x="50%" y="50%" font-family="sans-serif" font-size="14" '
    'fill="#555" text-anchor="middle" dominant-baseline="middle">'
    "Architecture diagram placeholder - install Graphviz to regenerate"
    "</text>\n"
    "</svg>\n"
)


def _write_placeholders() -> None:
    """Write minimal placeholder SVGs for each expected diagram."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for name in EXPECTED_FILES:
        target = OUTPUT_DIR / name
        if not target.exists():
            target.write_text(_PLACEHOLDER_SVG, encoding="utf-8")


def _has_prerequisites() -> bool:
    """Return ``True`` when both pyreverse and Graphviz ``dot`` are available."""
    if shutil.which("dot") is None:
        return False
    try:
        subprocess.run(  # noqa: S603
            [sys.executable, "-c", "import pylint.pyreverse.main"],
            check=True,
            capture_output=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False
    return True


def _run_generator() -> bool:
    """Invoke ``tools/generate_diagrams.py`` as a subprocess.

    Returns
    -------
    bool
        ``True`` if generation succeeded, ``False`` otherwise.
    """
    script = REPO_ROOT / "tools" / "generate_diagrams.py"
    try:
        subprocess.run(  # noqa: S603
            [sys.executable, str(script)],
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        print(f"[mkdocs_hooks] diagram generation failed: {exc}", file=sys.stderr)
        return False
    return True


def on_pre_build(config: MkDocsConfig, **_: Any) -> None:
    """Generate architecture diagrams before MkDocs validates the site.

    Parameters
    ----------
    config : MkDocsConfig
        The active MkDocs configuration (unused but required by the hook
        signature).
    **_ : Any
        Additional keyword arguments supplied by MkDocs that are ignored
        here.

    Side Effects
    ------------
    Writes SVG files under ``docs/architecture/``.  When the diagram
    toolchain is unavailable, writes placeholder SVGs so that
    ``mkdocs build --strict`` does not fail on missing image links.
    """
    del config  # unused

    if _has_prerequisites() and _run_generator():
        return

    print(
        "[mkdocs_hooks] Graphviz/pyreverse unavailable; writing placeholder "
        "architecture diagrams. Install the 'docs' extra and Graphviz to "
        "regenerate real diagrams.",
        file=sys.stderr,
    )
    _write_placeholders()
