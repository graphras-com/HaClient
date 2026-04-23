"""Tests for the REST client."""

from __future__ import annotations

import pytest

from haclient.exceptions import AuthenticationError, HAClientError
from haclient.rest import RestClient

from .fake_ha import FakeHA


async def test_ping(fake_ha: FakeHA) -> None:
    rc = RestClient(fake_ha.base_url, fake_ha.token)
    try:
        assert await rc.ping() is True
    finally:
        await rc.close()


async def test_ping_rejects_bad_token(fake_ha: FakeHA) -> None:
    rc = RestClient(fake_ha.base_url, "nope")
    try:
        with pytest.raises(AuthenticationError):
            await rc.ping()
    finally:
        await rc.close()


async def test_get_states(fake_ha: FakeHA) -> None:
    fake_ha.states = [
        {"entity_id": "light.kitchen", "state": "on", "attributes": {}},
        {"entity_id": "sensor.temp", "state": "22.1", "attributes": {"unit_of_measurement": "°C"}},
    ]
    rc = RestClient(fake_ha.base_url, fake_ha.token)
    try:
        states = await rc.get_states()
        assert len(states) == 2
        single = await rc.get_state("light.kitchen")
        assert single is not None
        assert single["state"] == "on"
        missing = await rc.get_state("light.missing")
        assert missing is None
    finally:
        await rc.close()


async def test_call_service(fake_ha: FakeHA) -> None:
    rc = RestClient(fake_ha.base_url, fake_ha.token)
    try:
        result = await rc.call_service("light", "turn_on", {"entity_id": "light.kitchen"})
    finally:
        await rc.close()
    assert result == []
    assert fake_ha.rest_service_calls == [("light", "turn_on", {"entity_id": "light.kitchen"})]


async def test_call_service_error(fake_ha: FakeHA) -> None:
    rc = RestClient(fake_ha.base_url, "wrong-token")
    try:
        with pytest.raises(AuthenticationError):
            await rc.call_service("light", "turn_on")
    finally:
        await rc.close()


async def test_request_server_error(fake_ha: FakeHA) -> None:
    """Trigger a non-auth error path by hitting an unknown REST endpoint."""
    rc = RestClient(fake_ha.base_url, fake_ha.token)
    try:
        with pytest.raises(HAClientError):
            await rc._request("GET", "/api/does-not-exist")
    finally:
        await rc.close()


async def test_get_state_reraises_non_404(fake_ha: FakeHA) -> None:
    rc = RestClient(fake_ha.base_url, "wrong-token")
    try:
        with pytest.raises(AuthenticationError):
            await rc.get_state("light.any")
    finally:
        await rc.close()


async def test_url_normalisation(fake_ha: FakeHA) -> None:
    rc = RestClient(fake_ha.base_url, fake_ha.token)
    try:
        await rc._request("GET", "api/")
    finally:
        await rc.close()


async def test_request_connect_error() -> None:
    """Connect failure produces HAClientError (not a raw ClientError)."""
    rc = RestClient("http://127.0.0.1:1", "t", timeout=1.0)
    try:
        with pytest.raises(HAClientError):
            await rc.ping()
    finally:
        await rc.close()


async def test_get_states_unexpected_response(
    fake_ha: FakeHA, monkeypatch: pytest.MonkeyPatch
) -> None:
    rc = RestClient(fake_ha.base_url, fake_ha.token)

    async def fake_request(*a: object, **k: object) -> object:
        return {"not": "a list"}

    monkeypatch.setattr(rc, "_request", fake_request)
    try:
        with pytest.raises(HAClientError):
            await rc.get_states()
    finally:
        await rc.close()


async def test_call_service_non_list_response(
    fake_ha: FakeHA, monkeypatch: pytest.MonkeyPatch
) -> None:
    rc = RestClient(fake_ha.base_url, fake_ha.token)

    async def fake_request(*a: object, **k: object) -> object:
        return "text response"

    monkeypatch.setattr(rc, "_request", fake_request)
    try:
        assert await rc.call_service("light", "turn_on") == []
    finally:
        await rc.close()
