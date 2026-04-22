"""Synchronous convenience wrapper around :class:`HAClient`.

The wrapper runs a dedicated event loop in a background thread and submits
coroutines to it via :func:`asyncio.run_coroutine_threadsafe`. This allows
users in plain scripts / REPL sessions to consume the library without thinking
about ``asyncio`` or risking event-loop conflicts (e.g. inside Jupyter).

Example
-------
.. code-block:: python

    from ha_client import SyncHAClient

    ha = SyncHAClient("http://localhost:8123", token="...")
    ha.connect()
    player = ha.media_player("livingroom")
    player.play()
    ha.close()
"""

from __future__ import annotations

import asyncio
import inspect
import threading
from collections.abc import Awaitable
from typing import Any, TypeVar

from .client import HAClient

T = TypeVar("T")


class _LoopThread:
    """Run an asyncio event loop in a dedicated thread."""

    def __init__(self) -> None:
        self.loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run, name="ha-client-sync-loop", daemon=True)
        self._started = threading.Event()
        self._thread.start()
        self._started.wait()

    def _run(self) -> None:
        asyncio.set_event_loop(self.loop)
        self._started.set()
        try:
            self.loop.run_forever()
        finally:
            try:
                pending = asyncio.all_tasks(self.loop)
                for task in pending:
                    task.cancel()
                if pending:
                    self.loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            finally:
                self.loop.close()

    def submit(self, coro: Awaitable[T], *, timeout: float | None = None) -> T:
        if not inspect.isawaitable(coro):  # pragma: no cover - defensive
            raise TypeError("submit() expects an awaitable")
        future = asyncio.run_coroutine_threadsafe(_ensure_coro(coro), self.loop)
        return future.result(timeout=timeout)

    def stop(self) -> None:
        if not self.loop.is_closed():
            self.loop.call_soon_threadsafe(self.loop.stop)
        self._thread.join(timeout=5.0)


async def _ensure_coro(awaitable: Awaitable[T]) -> T:
    return await awaitable


class _SyncProxy:
    """Wrap an object so its async methods can be called synchronously."""

    def __init__(self, target: Any, loop_thread: _LoopThread) -> None:
        object.__setattr__(self, "_target", target)
        object.__setattr__(self, "_loop_thread", loop_thread)

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._target, name)
        if inspect.iscoroutinefunction(attr):
            loop_thread = self._loop_thread

            def wrapper(*args: Any, **kwargs: Any) -> Any:
                return loop_thread.submit(attr(*args, **kwargs))

            wrapper.__name__ = attr.__name__
            wrapper.__doc__ = attr.__doc__
            return wrapper
        return attr

    def __setattr__(self, name: str, value: Any) -> None:
        setattr(self._target, name, value)

    def __repr__(self) -> str:
        return f"<Sync {self._target!r}>"


class SyncHAClient:
    """Synchronous counterpart of :class:`HAClient`.

    All public methods of :class:`HAClient` are exposed as blocking calls. All
    async methods of returned entities are automatically wrapped in a sync
    proxy so consumers can call ``player.play()`` without ``await``.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._loop_thread = _LoopThread()

        async def _build() -> HAClient:
            return HAClient(*args, **kwargs)

        self._client: HAClient = self._loop_thread.submit(_build())

    @property
    def client(self) -> HAClient:
        """Return the underlying :class:`HAClient` instance."""
        return self._client

    # ----------------------------------------------------- connection lifecycle
    def connect(self) -> None:
        """Connect the underlying client."""
        self._loop_thread.submit(self._client.connect())

    def close(self) -> None:
        """Close the underlying client and stop the background loop."""
        try:
            self._loop_thread.submit(self._client.close())
        finally:
            self._loop_thread.stop()

    def __enter__(self) -> SyncHAClient:
        self.connect()
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()

    # ------------------------------------------------------- service helpers
    def call_service(self, domain: str, service: str, data: dict[str, Any] | None = None) -> Any:
        """Invoke a Home Assistant service synchronously."""
        return self._loop_thread.submit(self._client.call_service(domain, service, data))

    def refresh_all(self) -> None:
        """Refresh all registered entities synchronously."""
        self._loop_thread.submit(self._client.refresh_all())

    # ---------------------------------------------------- domain accessors
    def media_player(self, name: str) -> Any:
        """Return a sync proxy wrapping the async :class:`MediaPlayer`."""
        return _SyncProxy(self._client.media_player(name), self._loop_thread)

    def light(self, name: str) -> Any:
        """Return a sync proxy wrapping the async :class:`Light`."""
        return _SyncProxy(self._client.light(name), self._loop_thread)

    def switch(self, name: str) -> Any:
        """Return a sync proxy wrapping the async :class:`Switch`."""
        return _SyncProxy(self._client.switch(name), self._loop_thread)

    def climate(self, name: str) -> Any:
        """Return a sync proxy wrapping the async :class:`Climate`."""
        return _SyncProxy(self._client.climate(name), self._loop_thread)

    def cover(self, name: str) -> Any:
        """Return a sync proxy wrapping the async :class:`Cover`."""
        return _SyncProxy(self._client.cover(name), self._loop_thread)

    def sensor(self, name: str) -> Any:
        """Return a sync proxy wrapping the async :class:`Sensor`."""
        return _SyncProxy(self._client.sensor(name), self._loop_thread)

    def binary_sensor(self, name: str) -> Any:
        """Return a sync proxy wrapping the async :class:`BinarySensor`."""
        return _SyncProxy(self._client.binary_sensor(name), self._loop_thread)
