# API Reference

The `haclient` package re-exports its public API at the top level. The
table below maps every name in `haclient.__all__` to the reference page
where it is documented.

## Public exports

| Name | Kind | Reference |
| --- | --- | --- |
| `HAClient` | Async client facade | [HAClient (facade)](api.md) |
| `SyncHAClient` | Blocking wrapper | [Sync Client](sync.md) |
| `ConnectionConfig` | Configuration | [Configuration](config.md) |
| `ServicePolicy` | Configuration | [Configuration](config.md) |
| `Entity` | Entity base class | [Entity](entity.md) |
| `Connection` | Core | [Connection](core/connection.md) |
| `EventBus` | Core | [Event Bus](core/events.md) |
| `ServiceCaller` | Core | [Service Caller](core/services.md) |
| `StateStore` | Core | [State Store](core/state.md) |
| `EntityRegistry` | Core | [Entity Registry](core/registry.md) |
| `EntityFactory` | Core | [Entity Factory](core/factory.md) |
| `DomainAccessor` | Plugins | [Plugins](core/plugins.md) |
| `DomainRegistry` | Plugins | [Plugins](core/plugins.md) |
| `DomainSpec` | Plugins | [Plugins](core/plugins.md) |
| `register_domain` | Plugins | [Plugins](core/plugins.md) |
| `Clock` | Port protocol | [Ports](ports.md) |
| `RestPort` | Port protocol | [Ports](ports.md) |
| `WebSocketPort` | Port protocol | [Ports](ports.md) |
| `HAClientError` | Exception | [Exceptions](exceptions.md) |
| `AuthenticationError` | Exception | [Exceptions](exceptions.md) |
| `CommandError` | Exception | [Exceptions](exceptions.md) |
| `ConnectionClosedError` | Exception | [Exceptions](exceptions.md) |
| `EntityNotFoundError` | Exception | [Exceptions](exceptions.md) |
| `HTTPError` | Exception | [Exceptions](exceptions.md) |
| `TimeoutError` | Exception | [Exceptions](exceptions.md) |

## Package

::: haclient
    options:
      show_submodules: false
      members: false
