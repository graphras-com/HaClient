# Custom domains and plugins

HaClient ships with typed accessors for the most common Home
Assistant domains: `light`, `switch`, `climate`, `cover`, `fan`,
`humidifier`, `lock`, `media_player`, `scene`, `sensor`,
`binary_sensor`, `air_quality`, `event`, `timer`, `vacuum`, `valve`.

When you need something we do not ship, the same plugin model that
built-ins use is available to you.

## In-process registration

The fastest path is to define an `Entity` subclass and register it
before constructing your client:

```python
from haclient import HAClient, DomainSpec, Entity, register_domain

class Sprinkler(Entity):
    domain = "sprinkler"

    async def start(self, duration: int) -> None:
        await self._call_service("start", {"duration": duration})

    async def stop(self) -> None:
        await self._call_service("stop")

register_domain(DomainSpec(name="sprinkler", entity_cls=Sprinkler))

async with HAClient.from_url(url, token=token) as ha:
    sprinkler = ha.domain("sprinkler")["lawn"]
    await sprinkler.start(600)
```

A few important details:

- **Register before construction.** Active domains are snapshotted
  when `HAClient` is constructed. Registering a new spec on the
  shared registry *after* a client exists will not retroactively add
  the domain to that client. Register first, then construct.
- **`Entity` subclasses must set `domain`** to the HA domain string
  (matching the `name` you give the spec). It is used by
  `_call_service` to route service invocations to the right HA
  domain.
- **Use `_call_service`** for entity-scoped actions. It automatically
  injects `entity_id` and routes through the shared `ServiceCaller`.

The accessor for a custom domain is reached via
`ha.domain("sprinkler")` or — once you have ensured the domain name
does not collide with a built-in attribute — via attribute access
`ha.sprinkler("lawn")`.

## Adding listener decorators

Custom domains can expose typed listener decorators in exactly the
same way the built-ins do:

```python
from typing import TypeVar
from haclient import Entity

V = TypeVar("V")  # ValueChangeHandler

class Sprinkler(Entity):
    domain = "sprinkler"

    def on_start(self, func: V) -> V:
        """Decorator: fire when state transitions to 'running'."""
        return self._register_state_transition_listener("running", func)

    def on_remaining_change(self, func: V) -> V:
        """Decorator: fire when the 'remaining' attribute changes."""
        return self._register_attr_listener("remaining", func)
```

See the [listeners guide](listeners.md) for the three built-in
categories you can wrap.

## Collection-level operations

If your domain has actions that are not tied to a single entity —
analogous to `scene.apply(...)` or `timer.create(...)` — subclass
`DomainAccessor` and attach it to the spec:

```python
from typing import Any
from haclient import DomainSpec, DomainAccessor, Entity, register_domain

class IrrigationAccessor(DomainAccessor["Sprinkler"]):
    async def run_program(self, program_id: str, *, zones: list[str]) -> None:
        await self.factory.services.call(
            "sprinkler",
            "run_program",
            {"program_id": program_id, "zones": zones},
        )

register_domain(
    DomainSpec(
        name="sprinkler",
        entity_cls=Sprinkler,
        accessor_cls=IrrigationAccessor,
    )
)
```

Use `self.factory.services` and `self.factory.state` from inside the
accessor. These are the public hooks; do not reach into the private
underscore-prefixed attributes.

## Routing custom HA events

If your domain emits HA events other than `state_changed` (the way
`timer.finished` works for the built-in `timer` domain), declare them
on the spec:

```python
def on_sprinkler_event(entity: Entity, event_type: str, data: dict[str, Any]) -> None:
    print(f"{entity.entity_id} got {event_type}: {data}")

register_domain(
    DomainSpec(
        name="sprinkler",
        entity_cls=Sprinkler,
        event_subscriptions=("sprinkler.zone_finished",),
        on_event=on_sprinkler_event,
    )
)
```

The client subscribes to each listed event type when it starts and
routes each event to the registered entity via the
`on_event` callback. Events whose `data.entity_id` is unknown are
silently dropped.

## Shipping a plugin via an entry point

If you maintain a separate Python package and want HaClient users to
get your domain automatically, expose an entry point under
`haclient.domains` in your package metadata:

```toml
# pyproject.toml of your plugin package
[project.entry-points."haclient.domains"]
sprinkler = "my_haclient_sprinkler.plugin"
```

The module referenced (`my_haclient_sprinkler.plugin`) should
register the spec at import time:

```python
# my_haclient_sprinkler/plugin.py
from haclient import DomainSpec, Entity, register_domain

class Sprinkler(Entity):
    domain = "sprinkler"
    ...

register_domain(DomainSpec(name="sprinkler", entity_cls=Sprinkler))
```

`HAClient.from_url(..., load_plugins=True)` is the default and
discovers your entry point. Each plugin is loaded inside a try /
except so one broken plugin cannot prevent the rest from loading;
failures are logged but do not raise.

To opt out of plugin discovery for a specific client (useful in
tests):

```python
ha = HAClient.from_url(url, token=token, load_plugins=False)
```

## Restricting active domains

If you only need a subset of domains for a particular client, pass
`domains=`:

```python
ha = HAClient.from_url(url, token=token, domains=["light", "switch"])
```

Unlisted domains are not exposed on the client even though they
remain in the shared registry.

## Replacing a built-in domain

This is not supported. Re-registering an existing domain name with a
different `entity_cls` raises `HAClientError`. Re-registering the
same class is a no-op (so importing the same plugin twice is safe).

If you want to *extend* a built-in domain — for example, add a
custom method on `Light` — subclass it in your own code and use it
from your own helpers; do not try to monkey-patch the registry.
