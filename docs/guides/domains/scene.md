# Scene

Scenes capture a set of entity states under a single name. HaClient
exposes both entity-level activation and collection-level
create / apply operations.

## Activating an existing scene

```python
scene = ha.scene("movie_night")
await scene.activate()
await scene.activate(transition=2.0)
```

The optional `transition` (seconds) is forwarded to HA and applied
on devices that support it.

## Scene metadata

```python
print(scene.name)              # friendly name, if any
print(scene.icon)              # MDI icon string, if any
print(scene.entity_ids)        # entities this scene controls
print(scene.last_activated)    # ISO timestamp or None
```

## Reacting to activation

```python
@scene.on_activate
def activated(old: str | None, new: str | None) -> None:
    print("movie_night activated")
```

`on_activate` fires whenever the scene's state string updates —
typically when HA records a fresh activation timestamp.

## Applying an ad-hoc scene

`ha.scene.apply(...)` is a *one-shot* state combination — it does not
create or update a persistent scene helper. Use it when you want the
"scene" semantics (multiple entities, transition, single call) but
do not need to keep the definition around:

```python
await ha.scene.apply(
    {
        "light.kitchen": {"state": "on", "brightness": 120},
        "light.hallway": {"state": "on", "brightness": 60},
        "switch.fan": {"state": "off"},
    },
    transition=1.5,
)
```

The dict maps entity ids to a `state` (plus any attributes HA
accepts for that entity type).

## Creating a persistent scene helper

To register a new scene helper in HA that you can activate later:

```python
new_scene = await ha.scene.create(
    scene_id="late_night",
    entities={
        "light.bedroom": {"state": "on", "brightness": 20},
        "light.hallway": {"state": "off"},
    },
)

# Later — same accessor reaches it because `entity_cls=Scene` was
# registered against the spec.
await new_scene.activate()
```

You can also snapshot the current state of selected entities at
creation time instead of (or in addition to) declaring them
explicitly:

```python
await ha.scene.create(
    scene_id="snapshot_now",
    entities={},
    snapshot_entities=["light.kitchen", "light.hallway"],
)
```

## Deleting a scene

```python
await scene.delete()
```

Deletes the helper from HA. Only applicable to user-created scene
helpers.

## Common patterns

### Toggle scene by tap

```python
@ha.switch("scene_button").on_turn_on
async def tapped(old, new):
    await ha.scene("movie_night").activate()
```

### Apply, then revert

`scene.apply` does not snapshot — to revert you need to capture the
previous values yourself or use `scene.create(..., snapshot_entities=...)`
and `activate()` to swap back.
