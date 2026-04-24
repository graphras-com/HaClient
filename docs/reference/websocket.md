<a id="haclient.websocket"></a>

# haclient.websocket

Home Assistant WebSocket API client.

The implementation focuses on being robust and test-friendly:

* A single background task (``_reader_task``) consumes the WebSocket.
* All outgoing commands get a monotonically increasing ``id`` and resolve
  through an :class:`asyncio.Future` when the matching ``result`` frame
  arrives.
* A separate ``_keepalive_task`` periodically sends ``ping`` messages.
* If the socket drops unexpectedly an exponential back-off reconnect loop
  restarts the connection, and any previously registered subscriptions are
  re-established transparently.

<a id="haclient.websocket.WebSocketClient"></a>

## WebSocketClient Objects

```python
class WebSocketClient()
```

Async Home Assistant WebSocket client.

Parameters
----------
url:
    Fully-qualified WebSocket URL (e.g. ``ws://localhost:8123/api/websocket``).
token:
    Long-lived access token.
session:
    Optional pre-existing :class:`aiohttp.ClientSession`. If not provided
    one will be created and closed automatically.
reconnect:
    Whether to reconnect automatically when the socket drops.
ping_interval:
    Seconds between keepalive pings. Set to ``0`` to disable.
request_timeout:
    Default timeout (seconds) for individual WebSocket commands.

<a id="haclient.websocket.WebSocketClient.connected"></a>

#### connected

```python
@property
def connected() -> bool
```

Return ``True`` while the underlying socket is open.

<a id="haclient.websocket.WebSocketClient.connect"></a>

#### connect

```python
async def connect() -> None
```

Establish the WebSocket connection and authenticate.

<a id="haclient.websocket.WebSocketClient.close"></a>

#### close

```python
async def close() -> None
```

Close the WebSocket and stop background tasks.

<a id="haclient.websocket.WebSocketClient.on_disconnect"></a>

#### on\_disconnect

```python
def on_disconnect(
    handler: Callable[[], Awaitable[None] | None]
) -> Callable[[], Awaitable[None] | None]
```

Register ``handler`` to be called when the connection drops.

<a id="haclient.websocket.WebSocketClient.send_command"></a>

#### send\_command

```python
async def send_command(payload: dict[str, Any],
                       *,
                       timeout: float | None = None) -> Any
```

Send a command and await its ``result`` frame.

Returns the ``result`` payload (the value of the ``result`` key in the
response). Raises :class:`CommandError` if Home Assistant returns a
``success: false`` response, and :class:`HATimeoutError` if no reply
arrives within ``timeout`` seconds.

<a id="haclient.websocket.WebSocketClient.subscribe_events"></a>

#### subscribe\_events

```python
async def subscribe_events(handler: EventHandler,
                           event_type: str | None = None) -> int
```

Subscribe to Home Assistant events.

Returns the subscription id (needed for :meth:`unsubscribe`).

<a id="haclient.websocket.WebSocketClient.unsubscribe"></a>

#### unsubscribe

```python
async def unsubscribe(subscription_id: int) -> None
```

Unsubscribe a previously registered subscription.

<a id="haclient.websocket.WebSocketClient.ping"></a>

#### ping

```python
async def ping(*, timeout: float | None = None) -> None
```

Send a ``ping`` frame and wait for the matching ``pong``.

Home Assistant replies with ``{"type": "pong"}`` rather than a
``result`` frame, so this is implemented as a separate code path.

