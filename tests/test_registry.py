"""Tests for the EntityRegistry and name resolution."""

from __future__ import annotations

import pytest

from haclient import HAClient
from haclient.exceptions import EntityNotFoundError
from haclient.registry import EntityRegistry


def test_resolve_short_name() -> None:
    reg = EntityRegistry()
    assert reg.resolve("light", "kitchen") == "light.kitchen"


def test_resolve_rejects_fully_qualified() -> None:
    reg = EntityRegistry()
    with pytest.raises(ValueError, match="short object-id"):
        reg.resolve("light", "light.kitchen")
    with pytest.raises(ValueError, match="short object-id"):
        reg.resolve("light", "switch.hall")


def test_require_missing() -> None:
    reg = EntityRegistry()
    with pytest.raises(EntityNotFoundError):
        reg.require("light.unknown")


def test_register_and_lookup() -> None:
    reg = EntityRegistry()
    client = HAClient("http://x", "t")
    client.registry = reg

    from haclient import Light

    light = Light("light.kitchen", client)
    assert reg.get("light.kitchen") is light
    assert "light.kitchen" in reg
    assert len(reg) == 1
    assert light in reg.in_domain("light")
    reg.unregister("light.kitchen")
    assert reg.get("light.kitchen") is None
    reg.clear()
    assert len(reg) == 0
