# Media Player

The `media_player` accessor returns `MediaPlayer` entities for
speakers, TVs, receivers, and software media players.

## Playback control

```python
mp = ha.media_player("living_room_speaker")

await mp.play()
await mp.pause()
await mp.play_pause()   # toggle
await mp.stop()
await mp.next()
await mp.previous()
```

State helpers:

```python
print(mp.is_playing)
print(mp.is_paused)
```

## Volume and mute

```python
await mp.set_volume(0.4)         # 0.0 - 1.0
await mp.mute()                  # mute=True by default
await mp.mute(False)             # unmute

print(mp.volume_level, mp.is_muted)
```

Volume is normalised to a float in `[0.0, 1.0]` regardless of the
underlying device's native range.

## Power

```python
await mp.power_on()
await mp.power_off()
```

## Source / input selection

```python
await mp.select_source("HDMI 1")
```

The available source list is reported by HA on the entity's
attributes; consult `mp.attributes` (or `now_playing`) for the
current set on each device.

## Now-playing metadata

`now_playing` returns a typed snapshot of what HA reports:

```python
np = mp.now_playing
print(np.title, np.artist, np.album)
print(np.duration, np.position)
```

Use the dedicated decorator instead of polling:

```python
@mp.on_media_change
def media(old, new):
    print(f"now playing: {mp.now_playing.title}")
```

## Browsing and playing media

For services that take an explicit content reference:

```python
await mp.play_media(
    media_content_type="music",
    media_content_id="spotify:playlist:37i9dQZF1DXcBWIGoYBM5M",
)
```

For exploring the media library (Spotify, Plex, local files, etc.),
use `browse_media` and `favorites`:

```python
# Raw browse — same shape HA returns.
tree = await mp.browse_media()
print(tree["children"])

# Flattened, playable items only — recursive.
favs = await mp.favorites(max_depth=2, max_nodes=200)
for item in favs:
    print(item.title)

await favs[0].play()
```

`favorites()` returns `FavoriteItem` objects, each of which knows
how to play itself against the originating media player.

## Reacting to changes

```python
@mp.on_play
def playing(old, new): ...

@mp.on_pause
def paused(old, new): ...

@mp.on_stop
def stopped(old, new): ...

@mp.on_volume_change
def volume(old: float | None, new: float | None) -> None:
    print(f"volume {old} -> {new}")

@mp.on_mute_change
def muted(old: bool | None, new: bool | None) -> None: ...

@mp.on_media_change
def media(old, new): ...
```

## Common patterns

### Resume only if paused

```python
if mp.is_paused:
    await mp.play()
```

### Volume ramp

```python
import asyncio

target = 0.6
step = 0.05
while (mp.volume_level or 0) < target:
    await mp.set_volume(min(target, (mp.volume_level or 0) + step))
    await asyncio.sleep(0.5)
```

### Whole-house pause

```python
for name in ("kitchen_speaker", "living_room_speaker", "bedroom_speaker"):
    await ha.media_player(name).pause()
```
