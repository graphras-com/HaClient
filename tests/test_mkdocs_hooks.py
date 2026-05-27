"""Tests for the MkDocs ``on_pre_build`` hook.

The hook in ``tools/mkdocs_hooks.py`` generates architecture diagrams
before MkDocs validates inter-page links.  These tests exercise the
hook's two code paths: successful generation and graceful fallback to
placeholder SVGs when the diagram toolchain is unavailable.

The module under test lives outside the ``haclient`` package, so it is
loaded directly from its file path.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOK_PATH = REPO_ROOT / "tools" / "mkdocs_hooks.py"


def _load_hook_module() -> ModuleType:
    """Import ``tools/mkdocs_hooks.py`` as a standalone module."""
    spec = importlib.util.spec_from_file_location("haclient_mkdocs_hooks", HOOK_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def hook(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """Load the hook module with ``OUTPUT_DIR`` redirected to a temp dir."""
    module = _load_hook_module()
    monkeypatch.setattr(module, "OUTPUT_DIR", tmp_path / "architecture")
    return module


def test_placeholders_written_when_toolchain_missing(
    hook: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``on_pre_build`` writes placeholder SVGs if prerequisites are missing."""
    monkeypatch.setattr(hook, "_has_prerequisites", lambda: False)

    hook.on_pre_build(config=None)

    for name in hook.EXPECTED_FILES:
        target = hook.OUTPUT_DIR / name
        assert target.exists(), f"expected placeholder {name}"
        content = target.read_text(encoding="utf-8")
        assert "<svg" in content
        assert "placeholder" in content.lower()


def test_placeholders_written_when_generator_fails(
    hook: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If the generator fails at runtime, the hook still writes placeholders."""
    monkeypatch.setattr(hook, "_has_prerequisites", lambda: True)
    monkeypatch.setattr(hook, "_run_generator", lambda: False)

    hook.on_pre_build(config=None)

    for name in hook.EXPECTED_FILES:
        assert (hook.OUTPUT_DIR / name).exists()


def test_generator_invoked_when_toolchain_available(
    hook: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When prerequisites exist the generator runs and no placeholders are needed."""
    calls: list[str] = []

    def fake_run_generator() -> bool:
        calls.append("ran")
        return True

    def fail_placeholders() -> None:  # pragma: no cover - must not be called
        raise AssertionError("placeholders must not be written on success")

    monkeypatch.setattr(hook, "_has_prerequisites", lambda: True)
    monkeypatch.setattr(hook, "_run_generator", fake_run_generator)
    monkeypatch.setattr(hook, "_write_placeholders", fail_placeholders)

    hook.on_pre_build(config=None)

    assert calls == ["ran"]


def test_placeholder_writer_does_not_overwrite_existing(hook: ModuleType) -> None:
    """``_write_placeholders`` must preserve existing files (real diagrams)."""
    hook.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    real_file = hook.OUTPUT_DIR / hook.EXPECTED_FILES[0]
    real_file.write_text("REAL DIAGRAM", encoding="utf-8")

    hook._write_placeholders()

    assert real_file.read_text(encoding="utf-8") == "REAL DIAGRAM"
    # The other expected file should be created as a placeholder.
    other = hook.OUTPUT_DIR / hook.EXPECTED_FILES[1]
    assert other.exists()
    assert "placeholder" in other.read_text(encoding="utf-8").lower()


def test_has_prerequisites_false_when_dot_missing(
    hook: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``_has_prerequisites`` returns False when ``dot`` is not on PATH."""
    monkeypatch.setattr(hook.shutil, "which", lambda _name: None)

    assert hook._has_prerequisites() is False


def test_has_prerequisites_false_when_pyreverse_missing(
    hook: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``_has_prerequisites`` returns False when ``pylint.pyreverse`` is missing."""
    monkeypatch.setattr(hook.shutil, "which", lambda _name: "/usr/bin/dot")

    def fake_run(*_args: Any, **_kwargs: Any) -> None:
        raise hook.subprocess.CalledProcessError(returncode=1, cmd=["python"])

    monkeypatch.setattr(hook.subprocess, "run", fake_run)

    assert hook._has_prerequisites() is False


def test_run_generator_reports_failure(hook: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    """``_run_generator`` returns False when the subprocess errors out."""

    def fake_run(*_args: Any, **_kwargs: Any) -> None:
        raise hook.subprocess.CalledProcessError(returncode=2, cmd=["script"])

    monkeypatch.setattr(hook.subprocess, "run", fake_run)

    assert hook._run_generator() is False
