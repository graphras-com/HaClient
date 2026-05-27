"""Packaging metadata tests.

Ensures the package version is single-sourced via ``hatch-vcs`` and not
hand-maintained in multiple places (see issue #78).
"""

from __future__ import annotations

import re
from importlib.metadata import version as pkg_version
from pathlib import Path

import haclient


def test_version_is_single_sourced_from_vcs() -> None:
    """``haclient.__version__`` must come from the generated ``_version.py``.

    With ``hatch-vcs`` the version is derived from git tags at build time and
    written into ``src/haclient/_version.py``. ``pyproject.toml`` must not
    declare a static ``[project].version`` and ``__init__.py`` must not embed
    a literal version string.
    """
    pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
    contents = pyproject.read_text(encoding="utf-8")
    assert 'dynamic = ["version"]' in contents
    # No static ``version = "x.y.z"`` line under [project].
    assert '\nversion = "' not in contents

    init_file = Path(haclient.__file__)
    init_text = init_file.read_text(encoding="utf-8")
    # No hand-maintained release version literal (e.g. ``__version__ = "1.2.3"``).
    assert not re.search(r'__version__\s*=\s*"\d+\.\d+\.\d+"', init_text)


def test_version_is_non_empty_string() -> None:
    """``__version__`` must be a non-empty PEP 440-ish string."""
    assert isinstance(haclient.__version__, str)
    assert haclient.__version__
    # Must at least start with a digit (PEP 440 release segment).
    assert haclient.__version__[0].isdigit()


def test_installed_metadata_is_available() -> None:
    """The package must expose a version via ``importlib.metadata``.

    This does not require equality with ``__version__`` because an editable
    install records the version at install time while ``_version.py`` is
    regenerated on every build; the two can legitimately differ between
    rebuilds. We only assert that metadata is present and non-empty.
    """
    meta_version = pkg_version("haclient")
    assert isinstance(meta_version, str)
    assert meta_version
