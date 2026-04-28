"""Synchronous convenience wrapper around `HAClient`.

The wrapper runs a dedicated event loop in a background thread and submits
coroutines to it via `asyncio.run_coroutine_threadsafe`. This allows
users in plain scripts / REPL sessions to consume the library without thinking
about ``asyncio`` or risking event-loop conflicts (e.g. inside Jupyter).

Examples
--------
::

    from haclient import SyncHAClient

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
        self._thread = threading.Thread(target=self._run, name="haclient-sync-loop", daemon=True)
        self._started = threading.Event()
        self._thread.start()
        self._started.wait()

    def _run(self) -> None:
        """Execute the event loop until stopped."""
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
        """Submit an awaitable to the background loop and block for the result.

        Parameters
        ----------
        coro : Awaitable[T]
            The awaitable to execute.
        timeout : float or None, optional
            Maximum seconds to wait for the result.

        Returns
        -------
        T
            The result of the awaitable.
        """
        if not inspect.isawaitable(coro):  # pragma: no cover - defensive
            raise TypeError("submit() expects an awaitable")
        future = asyncio.run_coroutine_threadsafe(_ensure_coro(coro), self.loop)
        return future.result(timeout=timeout)

    def stop(self) -> None:
        """Stop the event loop and join the background thread."""
        if not self.loop.is_closed():
            self.loop.call_soon_threadsafe(self.loop.stop)
        self._thread.join(timeout=5.0)


async def _ensure_coro(awaitable: Awaitable[T]) -> T:
    """Wrap an arbitrary awaitable into a proper coroutine."""
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
    """Synchronous counterpart of `HAClient`.

    All public domain accessors are exposed as blocking calls. All async
    methods of returned entities are automatically wrapped in a sync proxy
    so consumers can call ``player.play()`` without ``await``.

    Parameters
    ----------
    *args : Any
        Positional arguments forwarded to `HAClient`.
    **kwargs : Any
        Keyword arguments forwarded to `HAClient`.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._loop_thread = _LoopThread()

        async def _build() -> HAClient:
            return HAClient(*args, **kwargs)

        self._client: HAClient = self._loop_thread.submit(_build())

    @property
    def client(self) -> HAClient:
        """Return the underlying `HAClient` instance.

        Returns
        -------
        HAClient
            The wrapped async client.
        """
        return self._client

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

    def refresh_all(self) -> None:
        """Refresh all registered entities synchronously."""
        self._loop_thread.submit(self._client.refresh_all())

    # -- Domain accessors --

    def media_player(self, name: str) -> Any:
        """Return a sync proxy wrapping the async `MediaPlayer`.

        Parameters
        ----------
        name : str
            Short object-id (e.g. ``"livingroom"``).  The domain prefix
            is added automatically.
        """
        return _SyncProxy(self._client.media_player(name), self._loop_thread)

    def light(self, name: str) -> Any:
        """Return a sync proxy wrapping the async `Light`.

        Parameters
        ----------
        name : str
            Short object-id (e.g. ``"livingroom"``).  The domain prefix
            is added automatically.
        """
        return _SyncProxy(self._client.light(name), self._loop_thread)

    def switch(self, name: str) -> Any:
        """Return a sync proxy wrapping the async `Switch`.

        Parameters
        ----------
        name : str
            Short object-id (e.g. ``"livingroom"``).  The domain prefix
            is added automatically.
        """
        return _SyncProxy(self._client.switch(name), self._loop_thread)

    def climate(self, name: str) -> Any:
        """Return a sync proxy wrapping the async `Climate`.

        Parameters
        ----------
        name : str
            Short object-id (e.g. ``"livingroom"``).  The domain prefix
            is added automatically.
        """
        return _SyncProxy(self._client.climate(name), self._loop_thread)

    def cover(self, name: str) -> Any:
        """Return a sync proxy wrapping the async `Cover`.

        Parameters
        ----------
        name : str
            Short object-id (e.g. ``"livingroom"``).  The domain prefix
            is added automatically.
        """
        return _SyncProxy(self._client.cover(name), self._loop_thread)

    def sensor(self, name: str) -> Any:
        """Return a sync proxy wrapping the async `Sensor`.

        Parameters
        ----------
        name : str
            Short object-id (e.g. ``"livingroom"``).  The domain prefix
            is added automatically.
        """
        return _SyncProxy(self._client.sensor(name), self._loop_thread)

    def binary_sensor(self, name: str) -> Any:
        """Return a sync proxy wrapping the async `BinarySensor`.

        Parameters
        ----------
        name : str
            Short object-id (e.g. ``"livingroom"``).  The domain prefix
            is added automatically.
        """
        return _SyncProxy(self._client.binary_sensor(name), self._loop_thread)

    def scene(self, name: str) -> Any:
        """Return a sync proxy wrapping the async `Scene`.

        Parameters
        ----------
        name : str
            Short object-id (e.g. ``"livingroom"``).  The domain prefix
            is added automatically.
        """
        return _SyncProxy(self._client.scene(name), self._loop_thread)

    def create_scene(
        self,
        scene_id: str,
        entities: dict[str, dict[str, Any]],
        *,
        snapshot_entities: list[str] | None = None,
    ) -> Any:
        """Create a dynamic scene synchronously.

        Parameters
        ----------
        scene_id : str
            The object-id for the new scene.
        entities : dict[str, dict[str, Any]]
            Mapping of entity IDs to desired state/attribute dicts.
        snapshot_entities : list of str or None, optional
            Entity IDs whose current state should be captured.

        Returns
        -------
        Any
            A sync proxy wrapping the new `Scene`.
        """
        scene = self._loop_thread.submit(
            self._client.create_scene(scene_id, entities, snapshot_entities=snapshot_entities)
        )
        return _SyncProxy(scene, self._loop_thread)

    def apply_scene(
        self,
        entities: dict[str, dict[str, Any]],
        *,
        transition: float | None = None,
    ) -> None:
        """Apply entity states without creating a persistent scene.

        Parameters
        ----------
        entities : dict[str, dict[str, Any]]
            Mapping of entity IDs to desired state/attribute dicts.
        transition : float or None, optional
            Transition time in seconds.
        """
        self._loop_thread.submit(self._client.apply_scene(entities, transition=transition))

    def timer(self, name: str) -> Any:
        """Return a sync proxy wrapping the async `Timer`.

        Parameters
        ----------
        name : str
            Short object-id (e.g. ``"livingroom"``).  The domain prefix
            is added automatically.
        """
        return _SyncProxy(self._client.timer(name), self._loop_thread)
