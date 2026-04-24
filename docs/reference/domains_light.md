<a id="haclient.domains.light"></a>

# haclient.domains.light

``light`` domain implementation.

<a id="haclient.domains.light.Light"></a>

## Light Objects

```python
class Light(Entity)
```

A Home Assistant light entity.

<a id="haclient.domains.light.Light.on_turn_on"></a>

#### on\_turn\_on

```python
def on_turn_on(func: Any) -> Any
```

Register a listener for when the light turns on. Callback: ``(old_state, new_state)``.

<a id="haclient.domains.light.Light.on_turn_off"></a>

#### on\_turn\_off

```python
def on_turn_off(func: Any) -> Any
```

Register a listener for when the light turns off.

Callback: ``(old_state, new_state)``.

<a id="haclient.domains.light.Light.on_brightness_change"></a>

#### on\_brightness\_change

```python
def on_brightness_change(func: Any) -> Any
```

Register a listener for brightness changes. Callback: ``(old, new)``.

<a id="haclient.domains.light.Light.on_color_change"></a>

#### on\_color\_change

```python
def on_color_change(func: Any) -> Any
```

Register a listener for RGB color changes. Callback: ``(old, new)``.

<a id="haclient.domains.light.Light.on_kelvin_change"></a>

#### on\_kelvin\_change

```python
def on_kelvin_change(func: Any) -> Any
```

Register a listener for color temperature (Kelvin) changes. Callback: ``(old, new)``.

<a id="haclient.domains.light.Light.is_on"></a>

#### is\_on

```python
@property
def is_on() -> bool
```

``True`` if the light is currently on.

<a id="haclient.domains.light.Light.brightness"></a>

#### brightness

```python
@property
def brightness() -> int | None
```

Current brightness (0–255) or ``None`` if unsupported/unknown.

<a id="haclient.domains.light.Light.min_kelvin"></a>

#### min\_kelvin

```python
@property
def min_kelvin() -> int | None
```

Minimum supported color temperature in Kelvin, or ``None``.

<a id="haclient.domains.light.Light.max_kelvin"></a>

#### max\_kelvin

```python
@property
def max_kelvin() -> int | None
```

Maximum supported color temperature in Kelvin, or ``None``.

<a id="haclient.domains.light.Light.kelvin"></a>

#### kelvin

```python
@property
def kelvin() -> int | None
```

Current color temperature in Kelvin, or ``None``.

<a id="haclient.domains.light.Light.rgb_color"></a>

#### rgb\_color

```python
@property
def rgb_color() -> tuple[int, int, int] | None
```

Current RGB color tuple or ``None``.

<a id="haclient.domains.light.Light.turn_on"></a>

#### turn\_on

```python
async def turn_on(*,
                  brightness: int | None = None,
                  rgb_color: tuple[int, int, int] | list[int] | None = None,
                  color_temp: int | None = None,
                  kelvin: int | None = None,
                  transition: float | None = None,
                  **extra: Any) -> None
```

Turn the light on, optionally setting brightness/color/transition.

<a id="haclient.domains.light.Light.turn_off"></a>

#### turn\_off

```python
async def turn_off(*, transition: float | None = None) -> None
```

Turn the light off.

<a id="haclient.domains.light.Light.toggle"></a>

#### toggle

```python
async def toggle() -> None
```

Toggle the on/off state of the light.

