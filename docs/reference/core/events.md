# Event Bus

User-facing pub/sub façade over Home Assistant's WebSocket event
stream. Subscriptions automatically survive reconnects — see
[Reconnect handling](../../guides/reconnect.md). For typical
per-entity reactions prefer the listener decorators described in
[State and value listeners](../../guides/listeners.md).

::: haclient.core.events
