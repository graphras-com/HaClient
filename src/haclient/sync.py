"""Synchronous convenience wrapper around `HAClient`.

The wrapper runs a dedicated event loop in a background thread and
submits coroutines to it via `asyncio.run_coroutine_threadsafe`. This
allows users in plain scripts / REPL sessions to consume the library
without thinking about ``asyncio``.

Examples
--------
::

    from haclient import SyncHAClient

    with SyncHAClient.from_url("http://localhost:8123", token=TOKEN) as ha:
        light = ha.light("kitchen")
        light.set_brightness(200)
"""

from __future__ import annotations

import asyncio
import inspect
import threading
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from haclient.api import HAClient
from haclient.config import ConnectionConfig, ServicePolicy
from haclient.core.plugins import DomainAccessor

T = TypeVar("T")


class _LoopThread:
    """Run an asyncio event loop in a dedicated thread."""

    def __init__(self) -> None:
        """Start the background loop and block until it is running.

        Spawns a daemon thread that owns a fresh event loop and waits
        on a `threading.Event` until the loop has signalled that it is
        ready to accept work.
        """
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
        """Submit an awaitable and block for the result.

        Parameters
        ----------
        coro : Awaitable
            The awaitable to execute.
        timeout : float or None, optional
            Maximum seconds to wait.

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
        """Forward attribute access, blocking-wrapping coroutine functions.

        When the wrapped target's attribute is a coroutine function, a
        sync wrapper is returned that submits the coroutine to the
        background loop and waits for the result. Non-coroutine
        attributes are passed through unchanged.
        """
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
        """Forward attribute writes to the wrapped target."""
        setattr(self._target, name, value)

    def __repr__(self) -> str:
        """Return a debug representation that highlights the wrapper."""
        return f"<Sync {self._target!r}>"


class _SyncDomainAccessor:
    """Sync wrapper around a `DomainAccessor`.

    Returns sync proxies for entities and exposes the accessor's
    operations as blocking calls.
    """

    def __init__(self, accessor: DomainAccessor[Any], loop_thread: _LoopThread) -> None:
        object.__setattr__(self, "_accessor", accessor)
        object.__setattr__(self, "_loop_thread", loop_thread)

    def __call__(self, name: str) -> Any:
        """Look up an entity by *name* and return a sync proxy."""
        return _SyncProxy(self._accessor(name), self._loop_thread)

    def __getitem__(self, name: str) -> Any:
        """Look up an entity by *name* using ``[]`` syntax."""
        return _SyncProxy(self._accessor[name], self._loop_thread)

    def __getattr__(self, name: str) -> Any:
        """Forward attribute access, blocking-wrapping coroutine functions.

        Mirrors `_SyncProxy.__getattr__` but additionally wraps any
        returned object that exposes ``entity_id`` in a `_SyncProxy`,
        so that domain-level operations (e.g. ``ha.scene.create(...)``)
        return blocking entities just like direct lookups do.
        """
        attr = getattr(self._accessor, name)
        if inspect.iscoroutinefunction(attr):
            loop_thread = self._loop_thread

            def wrapper(*args: Any, **kwargs: Any) -> Any:
                result = loop_thread.submit(attr(*args, **kwargs))
                # Wrap entity returns in sync proxies for ergonomics.
                if hasattr(result, "entity_id"):
                    return _SyncProxy(result, loop_thread)
                return result

            wrapper.__name__ = attr.__name__
            wrapper.__doc__ = attr.__doc__
            return wrapper
        return attr


class SyncHAClient:
    """Synchronous counterpart of `HAClient`.

    Parameters
    ----------
    config : ConnectionConfig
        Resolved connection settings.
    """

    def __init__(
        self,
        config: ConnectionConfig,
        **kwargs: Any,
    ) -> None:
        self._loop_thread = _LoopThread()

        async def _build() -> HAClient:
            return HAClient(config, **kwargs)

        self._client: HAClient = self._loop_thread.submit(_build())

    @classmethod
    def from_url(
        cls,
        base_url: str,
        *,
        token: str,
        ws_url: str | None = None,
        reconnect: bool = True,
        ping_interval: float = 30.0,
        request_timeout: float = 30.0,
        verify_ssl: bool = True,
        service_policy: ServicePolicy = "auto",
        domains: list[str] | None = None,
        load_plugins: bool = True,
    ) -> SyncHAClient:
        """Build a `SyncHAClient` from a base URL and token.

        Parameters
        ----------
        base_url : str
            Home Assistant base URL.
        token : str
            Long-lived access token.
        ws_url : str or None, optional
            Explicit WebSocket URL (derived from *base_url* when omitted).
        reconnect : bool, optional
            Whether the WebSocket should reconnect automatically.
        ping_interval : float, optional
            Seconds between WebSocket keepalive pings.
        request_timeout : float, optional
            Default timeout for individual requests.
        verify_ssl : bool, optional
            Verify TLS certificates.
        service_policy : ServicePolicy, optional
            Default service-call routing policy.
        domains : list of str or None, optional
            Restrict loaded domains. ``None`` loads all registered
            domains.
        load_plugins : bool, optional
            Discover third-party plugins via the ``haclient.domains``
            entry-point group.

        Returns
        -------
        SyncHAClient
            The configured sync client (not yet connected).
        """
        config = ConnectionConfig.from_url(
            base_url,
            token,
            ws_url=ws_url,
            reconnect=reconnect,
            ping_interval=ping_interval,
            request_timeout=request_timeout,
            verify_ssl=verify_ssl,
            service_policy=service_policy,
        )
        return cls(config, domains=domains, load_plugins=load_plugins)

    @property
    def client(self) -> HAClient:
        """Return the underlying `HAClient` instance."""
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
        """Enter the sync context manager by calling `connect`."""
        self.connect()
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        """Exit the sync context manager by calling `close`."""
        self.close()

    def refresh_all(self) -> None:
        """Refresh all registered entities synchronously."""
        self._loop_thread.submit(self._client.state.refresh_all())

    def on_reconnect(
        self, handler: Callable[[], Awaitable[None] | None]
    ) -> Callable[[], Awaitable[None] | None]:
        """Register a reconnect listener.

        Parameters
        ----------
        handler : callable
            Sync or async zero-argument callable invoked after the
            WebSocket reconnects.

        Returns
        -------
        callable
            The same *handler*, returned so the method can be used as a
            decorator.
        """
        return self._client.on_reconnect(handler)

    def on_disconnect(
        self, handler: Callable[[], Awaitable[None] | None]
    ) -> Callable[[], Awaitable[None] | None]:
        """Register a disconnect listener.

        Parameters
        ----------
        handler : callable
            Sync or async zero-argument callable invoked when the
            WebSocket connection drops.

        Returns
        -------
        callable
            The same *handler*, returned so the method can be used as a
            decorator.
        """
        return self._client.on_disconnect(handler)

    # -- Domain accessors --

    def domain(self, name: str) -> _SyncDomainAccessor:
        """Return a sync accessor for *name*.

        Parameters
        ----------
        name : str
            HA domain name (e.g. ``"light"`` or a third-party domain).

        Returns
        -------
        _SyncDomainAccessor
            Blocking accessor wrapping the underlying async accessor.
        """
        return _SyncDomainAccessor(self._client.domain(name), self._loop_thread)

    def __getattr__(self, name: str) -> _SyncDomainAccessor:
        """Return a sync domain accessor for any registered domain.

        Enables ``ha.light("kitchen")``, ``ha.scene.create(...)``, etc.
        identically to `HAClient.__getattr__`, but wrapping everything
        in blocking proxies.

        Parameters
        ----------
        name : str
            The domain or accessor name.

        Returns
        -------
        _SyncDomainAccessor
            Blocking accessor wrapping the underlying async accessor.

        Raises
        ------
        AttributeError
            If *name* does not match any active domain.
        """
        # Delegate to HAClient.__getattr__ which returns a DomainAccessor
        # or raises AttributeError.
        accessor = getattr(self._client, name)
        return _SyncDomainAccessor(accessor, self._loop_thread)
