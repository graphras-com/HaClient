<a id="haclient.exceptions"></a>

# haclient.exceptions

Exception hierarchy for the Home Assistant client.

All library-specific exceptions derive from :class:`HAClientError` so callers
can catch a single base type if they do not care about the specific failure.

<a id="haclient.exceptions.HAClientError"></a>

## HAClientError Objects

```python
class HAClientError(Exception)
```

Base class for all exceptions raised by ``haclient``.

<a id="haclient.exceptions.AuthenticationError"></a>

## AuthenticationError Objects

```python
class AuthenticationError(HAClientError)
```

Raised when authentication with Home Assistant fails.

<a id="haclient.exceptions.ConnectionClosedError"></a>

## ConnectionClosedError Objects

```python
class ConnectionClosedError(HAClientError)
```

Raised when the WebSocket connection is unexpectedly closed.

<a id="haclient.exceptions.CommandError"></a>

## CommandError Objects

```python
class CommandError(HAClientError)
```

Raised when Home Assistant returns an error for a WebSocket command.

<a id="haclient.exceptions.TimeoutError"></a>

## TimeoutError Objects

```python
class TimeoutError(HAClientError)
```

Raised when a request to Home Assistant does not complete in time.

<a id="haclient.exceptions.EntityNotFoundError"></a>

## EntityNotFoundError Objects

```python
class EntityNotFoundError(HAClientError)
```

Raised when a requested entity cannot be resolved.

<a id="haclient.exceptions.UnsupportedOperationError"></a>

## UnsupportedOperationError Objects

```python
class UnsupportedOperationError(HAClientError)
```

Raised when an operation is not supported by an entity.

