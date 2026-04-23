"""Shared pytest fixtures for the haclient test suite."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio

from haclient import HAClient

from .fake_ha import FakeHA


@pytest_asyncio.fixture
async def fake_ha() -> AsyncIterator[FakeHA]:
    """Start a :class:`FakeHA` server and tear it down after the test."""
    server = FakeHA()
    await server.start()
    try:
        yield server
    finally:
        await server.stop()


@pytest_asyncio.fixture
async def client(fake_ha: FakeHA) -> AsyncIterator[HAClient]:
    """Return a connected :class:`HAClient` talking to the fake server."""
    ha = HAClient(
        fake_ha.base_url,
        token=fake_ha.token,
        ping_interval=0,
        request_timeout=5.0,
    )
    await ha.connect()
    try:
        yield ha
    finally:
        await ha.close()


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
