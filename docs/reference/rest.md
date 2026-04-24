<a id="haclient.rest"></a>

# haclient.rest

Thin async wrapper around the Home Assistant REST API.

Only the endpoints needed by :class:`haclient.client.HAClient` are exposed:

* ``GET  /api/``              – ping / connectivity check
* ``GET  /api/states``        – fetch all states
* ``GET  /api/states/{id}``   – fetch a single state
* ``POST /api/services/{domain}/{service}`` – invoke a service

Internally we use :mod:`aiohttp` because the WebSocket layer already depends on
it, keeping the dependency surface minimal.

<a id="haclient.rest.RestClient"></a>

## RestClient Objects

```python
class RestClient()
```

Async client for the Home Assistant REST API.

<a id="haclient.rest.RestClient.close"></a>

#### close

```python
async def close() -> None
```

Close the underlying HTTP session (if we own it).

<a id="haclient.rest.RestClient.ping"></a>

#### ping

```python
async def ping() -> bool
```

Return ``True`` if the Home Assistant API is reachable.

<a id="haclient.rest.RestClient.get_states"></a>

#### get\_states

```python
async def get_states() -> list[dict[str, Any]]
```

Return all entity states currently known to Home Assistant.

<a id="haclient.rest.RestClient.get_state"></a>

#### get\_state

```python
async def get_state(entity_id: str) -> dict[str, Any] | None
```

Return the state object for ``entity_id`` or ``None`` if not found.

<a id="haclient.rest.RestClient.call_service"></a>

#### call\_service

```python
async def call_service(
        domain: str,
        service: str,
        data: dict[str, Any] | None = None) -> list[dict[str, Any]]
```

Invoke a Home Assistant service via REST.

Returns the list of states that were changed (if any). Home Assistant
returns this list directly in the response body.

