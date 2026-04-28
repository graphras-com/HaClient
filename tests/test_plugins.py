"""Tests for `DomainRegistry`, `DomainSpec`, and entry-point loading."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from haclient import HAClient
from haclient.core.plugins import DomainAccessor, DomainRegistry, DomainSpec, register_domain
from haclient.entity.base import Entity
from haclient.exceptions import HAClientError


class _Custom(Entity):
    """Tiny custom-domain `Entity` used as a registration fixture."""

    domain = "custom_domain"

    async def fire(self) -> None:
        """Issue a no-op service call so the test can assert routing."""
        await self._call_service("noop")


def test_register_returns_spec() -> None:
    reg = DomainRegistry()
    spec = DomainSpec(name="dummy_a", entity_cls=_Custom)
    reg.register(spec)
    assert reg.get("dummy_a") is spec
    assert "dummy_a" in reg
    assert "dummy_a" in reg.names()


def test_register_collision_same_class_is_noop() -> None:
    reg = DomainRegistry()
    spec1 = DomainSpec(name="dup", entity_cls=_Custom)
    spec2 = DomainSpec(name="dup", entity_cls=_Custom, accessor="dup_alt")
    reg.register(spec1)
    reg.register(spec2)
    assert reg.get("dup") is spec2  # latest wins for same class


def test_register_collision_different_class_raises() -> None:
    reg = DomainRegistry()

    class Other(Entity):
        domain = "x"

    reg.register(DomainSpec(name="conflict", entity_cls=_Custom))
    with pytest.raises(HAClientError, match="already registered"):
        reg.register(DomainSpec(name="conflict", entity_cls=Other))


def test_unregister_removes_spec() -> None:
    reg = DomainRegistry()
    reg.register(DomainSpec(name="ephemeral", entity_cls=_Custom))
    reg.unregister("ephemeral")
    assert "ephemeral" not in reg
    reg.unregister("ephemeral")  # noop


def test_get_unknown_raises() -> None:
    reg = DomainRegistry()
    with pytest.raises(HAClientError, match="Unknown domain"):
        reg.get("nope")


def test_filter_by_name() -> None:
    reg = DomainRegistry()
    reg.register(DomainSpec(name="filter_a", entity_cls=_Custom))
    reg.register(DomainSpec(name="filter_b", entity_cls=_Custom))
    selected = reg.filter(["filter_a"])
    assert [s.name for s in selected] == ["filter_a"]


def test_iter_yields_specs() -> None:
    reg = DomainRegistry()
    reg.register(DomainSpec(name="iter_a", entity_cls=_Custom))
    reg.register(DomainSpec(name="iter_b", entity_cls=_Custom))
    names = sorted(s.name for s in reg)
    assert names == ["iter_a", "iter_b"]


def test_shared_registry_is_singleton() -> None:
    a = DomainRegistry.shared()
    b = DomainRegistry.shared()
    assert a is b


def test_register_domain_helper_uses_shared() -> None:
    """The `register_domain` module helper writes to the shared registry."""
    spec = DomainSpec(name="helper_test", entity_cls=_Custom)
    register_domain(spec)
    try:
        assert DomainRegistry.shared().get("helper_test") is spec
    finally:
        DomainRegistry.shared().unregister("helper_test")


def test_load_entry_points_skips_broken() -> None:
    """A broken plugin's exception is logged, not propagated."""

    class _FakeEP:
        name = "broken"

        def load(self) -> Any:
            raise RuntimeError("plugin failed")

    class _FakeWorking:
        name = "ok"

        def load(self) -> Any:
            return None

    fake_eps = [_FakeEP(), _FakeWorking()]
    reg = DomainRegistry()
    with patch("haclient.core.plugins.metadata.entry_points", return_value=fake_eps):
        loaded = reg.load_entry_points()
    assert loaded == ["ok"]


def test_load_entry_points_handles_enumerate_failure() -> None:
    """If enumerating entry points itself raises, we still return empty list."""
    reg = DomainRegistry()
    with patch(
        "haclient.core.plugins.metadata.entry_points",
        side_effect=RuntimeError("metadata broken"),
    ):
        loaded = reg.load_entry_points()
    assert loaded == []


def test_accessor_factory_protocol_raises_not_implemented() -> None:
    """The default protocol stub raises NotImplementedError."""
    from haclient.core.plugins import EntityFactoryProtocol

    proto = EntityFactoryProtocol()
    with pytest.raises(NotImplementedError):
        proto.get_or_create(DomainSpec(name="x", entity_cls=_Custom), "n")
    with pytest.raises(NotImplementedError):
        proto.in_domain(DomainSpec(name="x", entity_cls=_Custom))


async def test_third_party_domain_via_haclient_domain() -> None:
    """Generic ``ha.domain('custom')`` works for plugins registered ad-hoc."""

    class CustomEntity(Entity):
        domain = "third_party_custom"

        async def fire(self) -> None:
            await self._call_service("noop")

    reg = DomainRegistry()
    reg.register(DomainSpec(name="third_party_custom", entity_cls=CustomEntity))

    ha = HAClient.from_url("http://x", token="t", load_plugins=False, registry=reg)
    try:
        accessor = ha.domain("third_party_custom")
        assert isinstance(accessor, DomainAccessor)
        ent = accessor("foo")
        assert ent.entity_id == "third_party_custom.foo"
        assert isinstance(ent, CustomEntity)
        # Generic accessor lookup by attribute should also work.
        assert ha.domain("third_party_custom") is accessor
    finally:
        await ha.close()


async def test_domain_filter_restricts_active_domains() -> None:
    """Passing ``domains=[...]`` restricts which accessors are present."""
    ha = HAClient.from_url("http://x", token="t", load_plugins=False, domains=["light"])
    try:
        # Light accessor should still work.
        ha.light("kitchen")
        # Other domains should not be active.
        with pytest.raises(KeyError, match="not active"):
            ha.domain("switch")
    finally:
        await ha.close()


async def test_accessor_all_returns_registered_entities() -> None:
    ha = HAClient.from_url("http://x", token="t", load_plugins=False)
    try:
        a = ha.light("a")
        b = ha.light("b")
        all_lights = ha.domain("light").all()
        assert a in all_lights
        assert b in all_lights
    finally:
        await ha.close()


async def test_domain_accessor_spec_property() -> None:
    ha = HAClient.from_url("http://x", token="t", load_plugins=False)
    try:
        accessor = ha.domain("light")
        assert accessor.spec.name == "light"
    finally:
        await ha.close()
