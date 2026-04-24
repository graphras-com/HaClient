<a id="haclient.sync"></a>

# haclient.sync

Synchronous convenience wrapper around :class:`HAClient`.

The wrapper runs a dedicated event loop in a background thread and submits
coroutines to it via :func:`asyncio.run_coroutine_threadsafe`. This allows
users in plain scripts / REPL sessions to consume the library without thinking
about ``asyncio`` or risking event-loop conflicts (e.g. inside Jupyter).

Example
-------
.. code-block:: python

    from haclient import SyncHAClient

    ha = SyncHAClient("http://localhost:8123", token="...")
    ha.connect()
    player = ha.media_player("livingroom")
    player.play()
    ha.close()

<a id="haclient.sync._LoopThread"></a>

## \_LoopThread Objects

```python
class _LoopThread()
```

Run an asyncio event loop in a dedicated thread.

<a id="haclient.sync._LoopThread.submit"></a>

#### submit

```python
def submit(coro: Awaitable[T], *, timeout: float | None = None) -> T
```

Submit an awaitable to the background loop and block for the result.

<a id="haclient.sync._LoopThread.stop"></a>

#### stop

```python
def stop() -> None
```

Stop the event loop and join the background thread.

<a id="haclient.sync.SyncHAClient"></a>

## SyncHAClient Objects

```python
class SyncHAClient()
```

Synchronous counterpart of :class:`HAClient`.

All public methods of :class:`HAClient` are exposed as blocking calls. All
async methods of returned entities are automatically wrapped in a sync
proxy so consumers can call ``player.play()`` without ``await``.

<a id="haclient.sync.SyncHAClient.client"></a>

#### client

```python
@property
def client() -> HAClient
```

Return the underlying :class:`HAClient` instance.

<a id="haclient.sync.SyncHAClient.connect"></a>

#### connect

```python
def connect() -> None
```

Connect the underlying client.

<a id="haclient.sync.SyncHAClient.close"></a>

#### close

```python
def close() -> None
```

Close the underlying client and stop the background loop.

<a id="haclient.sync.SyncHAClient.call_service"></a>

#### call\_service

```python
def call_service(domain: str,
                 service: str,
                 data: dict[str, Any] | None = None) -> Any
```

Invoke a Home Assistant service synchronously.

<a id="haclient.sync.SyncHAClient.refresh_all"></a>

#### refresh\_all

```python
def refresh_all() -> None
```

Refresh all registered entities synchronously.

<a id="haclient.sync.SyncHAClient.media_player"></a>

#### media\_player

```python
def media_player(name: str) -> Any
```

Return a sync proxy wrapping the async :class:`MediaPlayer`.

<a id="haclient.sync.SyncHAClient.light"></a>

#### light

```python
def light(name: str) -> Any
```

Return a sync proxy wrapping the async :class:`Light`.

<a id="haclient.sync.SyncHAClient.switch"></a>

#### switch

```python
def switch(name: str) -> Any
```

Return a sync proxy wrapping the async :class:`Switch`.

<a id="haclient.sync.SyncHAClient.climate"></a>

#### climate

```python
def climate(name: str) -> Any
```

Return a sync proxy wrapping the async :class:`Climate`.

<a id="haclient.sync.SyncHAClient.cover"></a>

#### cover

```python
def cover(name: str) -> Any
```

Return a sync proxy wrapping the async :class:`Cover`.

<a id="haclient.sync.SyncHAClient.sensor"></a>

#### sensor

```python
def sensor(name: str) -> Any
```

Return a sync proxy wrapping the async :class:`Sensor`.

<a id="haclient.sync.SyncHAClient.binary_sensor"></a>

#### binary\_sensor

```python
def binary_sensor(name: str) -> Any
```

Return a sync proxy wrapping the async :class:`BinarySensor`.

