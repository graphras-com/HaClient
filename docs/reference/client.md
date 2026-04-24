<a id="haclient.client"></a>

# haclient.client

High-level Home Assistant client.

This module ties together the REST and WebSocket layers, the entity registry
and the domain helper classes into a single coherent API:

.. code-block:: python

    async with HAClient("http://localhost:8123", token="...") as ha:
        light = ha.light("kitchen")
        await light.turn_on(brightness=200)

The client exposes one accessor per supported domain (``media_player``,
``light``, ``switch``, ...). The accessor performs name resolution, creates a
domain object lazily if needed and returns the registered instance.

<a id="haclient.client.HAClient"></a>

## HAClient Objects

```python
class HAClient()
```

High-level async Home Assistant client.

Parameters
----------
base_url:
    The Home Assistant base URL (e.g. ``http://homeassistant.local:8123``).
token:
    Long-lived access token.
ws_url:
    Optional explicit WebSocket URL. If omitted it is derived from
    ``base_url``.
session:
    Optional shared :class:`aiohttp.ClientSession`.
reconnect:
    Whether to reconnect the WebSocket automatically.
ping_interval:
    Seconds between keepalive pings (set to ``0`` to disable).
request_timeout:
    Default timeout for WebSocket/REST operations.
verify_ssl:
    Verify TLS certificates (``True`` by default).

<a id="haclient.client.HAClient.loop"></a>

#### loop

```python
@property
def loop() -> asyncio.AbstractEventLoop | None
```

Return the event loop the client is bound to (if running).

<a id="haclient.client.HAClient.connect"></a>

#### connect

```python
async def connect() -> None
```

Connect the WebSocket, subscribe to state changes and prime the cache.

<a id="haclient.client.HAClient.close"></a>

#### close

```python
async def close() -> None
```

Close the WebSocket and any owned HTTP session.

<a id="haclient.client.HAClient.call_service"></a>

#### call\_service

```python
async def call_service(domain: str,
                       service: str,
                       data: dict[str, Any] | None = None,
                       *,
                       use_websocket: bool = True) -> Any
```

Invoke a Home Assistant service.

By default the call is made via the WebSocket API (which gives richer
error information). Set ``use_websocket=False`` to use the REST API
instead – useful before the WS connection is established.

<a id="haclient.client.HAClient.refresh_all"></a>

#### refresh\_all

```python
async def refresh_all() -> None
```

Refresh all registered entities from the REST API.

<a id="haclient.client.HAClient.media_player"></a>

#### media\_player

```python
def media_player(name: str) -> MediaPlayer
```

Return the :class:`MediaPlayer` for ``name`` (creating it if needed).

<a id="haclient.client.HAClient.light"></a>

#### light

```python
def light(name: str) -> Light
```

Return the :class:`Light` for ``name``.

<a id="haclient.client.HAClient.switch"></a>

#### switch

```python
def switch(name: str) -> Switch
```

Return the :class:`Switch` for ``name``.

<a id="haclient.client.HAClient.climate"></a>

#### climate

```python
def climate(name: str) -> Climate
```

Return the :class:`Climate` for ``name``.

<a id="haclient.client.HAClient.cover"></a>

#### cover

```python
def cover(name: str) -> Cover
```

Return the :class:`Cover` for ``name``.

<a id="haclient.client.HAClient.sensor"></a>

#### sensor

```python
def sensor(name: str) -> Sensor
```

Return the :class:`Sensor` for ``name`` (read-only).

<a id="haclient.client.HAClient.binary_sensor"></a>

#### binary\_sensor

```python
def binary_sensor(name: str) -> BinarySensor
```

Return the :class:`BinarySensor` for ``name`` (read-only).

