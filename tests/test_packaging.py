"""Packaging metadata tests.

Ensures the package version is single-sourced from installed metadata
(see issue #78).
"""

from __future__ import annotations

from importlib.metadata import version as pkg_version

import haclient


def test_version_matches_package_metadata() -> None:
    """``haclient.__version__`` must match installed package metadata.

    This guards against the previous drift where ``pyproject.toml`` and
    ``haclient/__init__.py`` declared different versions.
    """
    assert haclient.__version__ == pkg_version("haclient")


def test_version_is_non_empty_string() -> None:
    """``__version__`` must be a non-empty string."""
    assert isinstance(haclient.__version__, str)
    assert haclient.__version__
