<a id="haclient.domains.climate"></a>

# haclient.domains.climate

``climate`` domain implementation.

<a id="haclient.domains.climate.Climate"></a>

## Climate Objects

```python
class Climate(Entity)
```

A Home Assistant climate (thermostat / HVAC) entity.

<a id="haclient.domains.climate.Climate.on_hvac_mode_change"></a>

#### on\_hvac\_mode\_change

```python
def on_hvac_mode_change(func: Any) -> Any
```

Register a listener for HVAC mode changes. Callback: ``(old_mode, new_mode)``.

<a id="haclient.domains.climate.Climate.on_temperature_change"></a>

#### on\_temperature\_change

```python
def on_temperature_change(func: Any) -> Any
```

Register a listener for current temperature changes. Callback: ``(old, new)``.

<a id="haclient.domains.climate.Climate.on_target_temperature_change"></a>

#### on\_target\_temperature\_change

```python
def on_target_temperature_change(func: Any) -> Any
```

Register a listener for target temperature changes. Callback: ``(old, new)``.

<a id="haclient.domains.climate.Climate.current_temperature"></a>

#### current\_temperature

```python
@property
def current_temperature() -> float | None
```

The current measured temperature, if reported.

<a id="haclient.domains.climate.Climate.target_temperature"></a>

#### target\_temperature

```python
@property
def target_temperature() -> float | None
```

The current target temperature set-point.

<a id="haclient.domains.climate.Climate.hvac_mode"></a>

#### hvac\_mode

```python
@property
def hvac_mode() -> str
```

The active HVAC mode (same as :attr:`state`).

<a id="haclient.domains.climate.Climate.hvac_modes"></a>

#### hvac\_modes

```python
@property
def hvac_modes() -> list[str]
```

Supported HVAC modes reported by Home Assistant.

<a id="haclient.domains.climate.Climate.set_temperature"></a>

#### set\_temperature

```python
async def set_temperature(temperature: float,
                          *,
                          hvac_mode: str | None = None,
                          **extra: Any) -> None
```

Set the target temperature (optionally changing HVAC mode).

<a id="haclient.domains.climate.Climate.set_hvac_mode"></a>

#### set\_hvac\_mode

```python
async def set_hvac_mode(hvac_mode: str) -> None
```

Change the HVAC mode (e.g. ``"heat"``, ``"cool"``, ``"off"``).

<a id="haclient.domains.climate.Climate.set_fan_mode"></a>

#### set\_fan\_mode

```python
async def set_fan_mode(fan_mode: str) -> None
```

Set the fan mode.

<a id="haclient.domains.climate.Climate.turn_off"></a>

#### turn\_off

```python
async def turn_off() -> None
```

Turn off the climate entity.

<a id="haclient.domains.climate.Climate.turn_on"></a>

#### turn\_on

```python
async def turn_on() -> None
```

Turn on the climate entity (resumes last HVAC mode).

