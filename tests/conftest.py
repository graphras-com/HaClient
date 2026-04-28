"""Shared pytest fixtures for the haclient test suite."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio

from haclient import HAClient

from .fake_ha import FakeHA


@pytest_asyncio.fixture
async def fake_ha() -> AsyncIterator[FakeHA]:
    """Start a `FakeHA` server and tear it down after the test.

    Yields
    ------
    FakeHA
        A running in-process server bound to a free local port. Tests
        may register custom command handlers via ``server.handlers`` or
        push events with ``server.push_event``.
    """
    server = FakeHA()
    await server.start()
    try:
        yield server
    finally:
        await server.stop()


@pytest_asyncio.fixture
async def client(fake_ha: FakeHA) -> AsyncIterator[HAClient]:
    """Return a connected `HAClient` talking to the fake server.

    Parameters
    ----------
    fake_ha : FakeHA
        Active fake server provided by the `fake_ha` fixture.

    Yields
    ------
    HAClient
        Connected client. ``ping_interval`` is disabled and the request
        timeout is shortened to keep the test suite snappy.
    """
    ha = HAClient.from_url(
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
    """Force the ``anyio`` plugin to run on the asyncio backend.

    Returns
    -------
    str
        The backend identifier consumed by ``pytest-anyio``.
    """
    return "asyncio"
