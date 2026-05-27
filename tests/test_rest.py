"""Tests for the aiohttp REST adapter."""

from __future__ import annotations

import pytest

from haclient.exceptions import AuthenticationError, HAClientError, HTTPError
from haclient.infra.rest_aiohttp import AiohttpRestAdapter

from .fake_ha import FakeHA


async def test_ping(fake_ha: FakeHA) -> None:
    rc = AiohttpRestAdapter(fake_ha.base_url, fake_ha.token)
    try:
        assert await rc.ping() is True
    finally:
        await rc.close()


async def test_ping_rejects_bad_token(fake_ha: FakeHA) -> None:
    rc = AiohttpRestAdapter(fake_ha.base_url, "nope")
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
    rc = AiohttpRestAdapter(fake_ha.base_url, fake_ha.token)
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
    rc = AiohttpRestAdapter(fake_ha.base_url, fake_ha.token)
    try:
        result = await rc.call_service("light", "turn_on", {"entity_id": "light.kitchen"})
    finally:
        await rc.close()
    assert result == []
    assert fake_ha.rest_service_calls == [("light", "turn_on", {"entity_id": "light.kitchen"})]


async def test_call_service_error(fake_ha: FakeHA) -> None:
    rc = AiohttpRestAdapter(fake_ha.base_url, "wrong-token")
    try:
        with pytest.raises(AuthenticationError):
            await rc.call_service("light", "turn_on")
    finally:
        await rc.close()


async def test_request_server_error(fake_ha: FakeHA) -> None:
    """Non-auth HTTP errors are raised as HTTPError (subclass of HAClientError)."""
    rc = AiohttpRestAdapter(fake_ha.base_url, fake_ha.token)
    try:
        with pytest.raises(HTTPError) as exc_info:
            await rc._request("GET", "/api/does-not-exist")
        assert exc_info.value.status == 404
        assert exc_info.value.method == "GET"
        assert exc_info.value.path == "/api/does-not-exist"
        # HTTPError is still a HAClientError
        assert isinstance(exc_info.value, HAClientError)
    finally:
        await rc.close()


async def test_http_error_attributes(fake_ha: FakeHA) -> None:
    """HTTPError exposes status, method, path, and body as structured attributes."""
    rc = AiohttpRestAdapter(fake_ha.base_url, fake_ha.token)
    try:
        with pytest.raises(HTTPError) as exc_info:
            await rc._request("GET", "/api/does-not-exist")
        err = exc_info.value
        assert err.status == 404
        assert err.method == "GET"
        assert err.path == "/api/does-not-exist"
        assert isinstance(err.body, str)
        # String representation should include status code
        assert "404" in str(err)
    finally:
        await rc.close()


async def test_get_state_returns_none_only_for_404(fake_ha: FakeHA) -> None:
    """get_state() returns None for a real 404, not for other HTTP errors."""
    fake_ha.states = [{"entity_id": "light.kitchen", "state": "on", "attributes": {}}]
    rc = AiohttpRestAdapter(fake_ha.base_url, fake_ha.token)
    try:
        # Known entity returns state dict
        state = await rc.get_state("light.kitchen")
        assert state is not None
        assert state["state"] == "on"

        # Unknown entity → 404 → None (not an exception)
        missing = await rc.get_state("light.does_not_exist")
        assert missing is None
    finally:
        await rc.close()


async def test_get_state_reraises_non_404_http_error(
    fake_ha: FakeHA, monkeypatch: pytest.MonkeyPatch
) -> None:
    """get_state() re-raises HTTPError for status codes other than 404."""
    rc = AiohttpRestAdapter(fake_ha.base_url, fake_ha.token)

    async def fake_request(method: str, path: str, **_: object) -> object:
        raise HTTPError(500, method, path, "internal server error")

    monkeypatch.setattr(rc, "_request", fake_request)
    try:
        with pytest.raises(HTTPError) as exc_info:
            await rc.get_state("light.kitchen")
        assert exc_info.value.status == 500
    finally:
        await rc.close()


async def test_get_state_reraises_non_404(fake_ha: FakeHA) -> None:
    rc = AiohttpRestAdapter(fake_ha.base_url, "wrong-token")
    try:
        with pytest.raises(AuthenticationError):
            await rc.get_state("light.any")
    finally:
        await rc.close()


async def test_url_normalisation(fake_ha: FakeHA) -> None:
    rc = AiohttpRestAdapter(fake_ha.base_url, fake_ha.token)
    try:
        await rc._request("GET", "api/")
    finally:
        await rc.close()


async def test_request_connect_error() -> None:
    """Connect failure produces HAClientError (not a raw ClientError)."""
    rc = AiohttpRestAdapter("http://127.0.0.1:1", "t", timeout=1.0)
    try:
        with pytest.raises(HAClientError):
            await rc.ping()
    finally:
        await rc.close()


async def test_get_states_unexpected_response(
    fake_ha: FakeHA, monkeypatch: pytest.MonkeyPatch
) -> None:
    rc = AiohttpRestAdapter(fake_ha.base_url, fake_ha.token)

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
    rc = AiohttpRestAdapter(fake_ha.base_url, fake_ha.token)

    async def fake_request(*a: object, **k: object) -> object:
        return "text response"

    monkeypatch.setattr(rc, "_request", fake_request)
    try:
        assert await rc.call_service("light", "turn_on") == []
    finally:
        await rc.close()


def test_base_url_property(fake_ha: FakeHA) -> None:
    rc = AiohttpRestAdapter(fake_ha.base_url + "/", "t")
    assert rc.base_url == fake_ha.base_url
