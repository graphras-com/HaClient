# Service Caller

Routes raw HA service invocations between the WebSocket and REST
transports according to a `ServicePolicy` (`"ws"`, `"rest"`, or
`"auto"`). Most users should call services through the domain
entity methods (e.g. `ha.light("kitchen").set_brightness(...)`) and
treat `ServiceCaller.call` as an escape hatch — see
[Service routing (advanced)](../../guides/service-routing.md).

::: haclient.core.services
