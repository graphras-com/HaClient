<a id="haclient.domains.media_player"></a>

# haclient.domains.media\_player

``media_player`` domain implementation.

This module also contains the :class:`FavoriteItem` helper returned by
:meth:`MediaPlayer.favorites`, which recursively traverses the
``media_player/browse_media`` tree and flattens it into a list of directly
playable items.

<a id="haclient.domains.media_player.NowPlaying"></a>

## NowPlaying Objects

```python
@dataclass(frozen=True)
class NowPlaying()
```

Structured snapshot of the media currently playing on a media player.

Groups all identity-related media attributes into a single object.
Position/progress fields are intentionally excluded — they change
continuously during playback and do not represent a change in *what*
is playing.

Instances are frozen (immutable and hashable) so two snapshots can be
compared with ``==`` to detect whether the playing media changed.

<a id="haclient.domains.media_player.FavoriteItem"></a>

## FavoriteItem Objects

```python
class FavoriteItem()
```

A flattened, directly-playable entry discovered via ``browse_media``.

The item remembers which :class:`MediaPlayer` it belongs to, along with the
``media_content_id`` / ``media_content_type`` pair needed to play it. Call
:meth:`play` to start playback on the owning media player.

Extra metadata is captured to make the item easy to render in a UI:

* ``thumbnail`` – an optional image URL from Home Assistant.
* ``category`` – a human-readable label for the kind of favorite (e.g.
  ``"Radio"``, ``"Albums"``, ``"Playlists"``). It is derived from the title
  of the parent folder it was found under when available, otherwise falls
  back to ``media_class``.
* ``media_class`` – the raw ``media_class`` reported by HA (e.g.
  ``"genre"``, ``"album"``, ``"playlist"``, ``"track"``).

<a id="haclient.domains.media_player.FavoriteItem.play"></a>

#### play

```python
async def play() -> None
```

Play this favorite on its :class:`MediaPlayer`.

<a id="haclient.domains.media_player.MediaPlayer"></a>

## MediaPlayer Objects

```python
class MediaPlayer(Entity)
```

A Home Assistant media player entity.

<a id="haclient.domains.media_player.MediaPlayer.on_volume_change"></a>

#### on\_volume\_change

```python
def on_volume_change(func: Any) -> Any
```

Register a listener for volume level changes. Callback: ``(old, new)``.

<a id="haclient.domains.media_player.MediaPlayer.on_mute_change"></a>

#### on\_mute\_change

```python
def on_mute_change(func: Any) -> Any
```

Register a listener for mute state changes. Callback: ``(old, new)``.

<a id="haclient.domains.media_player.MediaPlayer.on_media_change"></a>

#### on\_media\_change

```python
def on_media_change(func: Any) -> Any
```

Register a listener for when the playing media changes.

Fires when any identity attribute changes (source, title, artist,
album, channel, content_type, content_id, duration, entity_picture,
queue_position, queue_size, playlist, repeat, next, previous)
but **not** on position/progress updates.

Callback: ``(old: NowPlaying, new: NowPlaying)``.

<a id="haclient.domains.media_player.MediaPlayer.on_play"></a>

#### on\_play

```python
def on_play(func: Any) -> Any
```

Register a listener for when playback starts. Callback: ``(old_state, new_state)``.

<a id="haclient.domains.media_player.MediaPlayer.on_pause"></a>

#### on\_pause

```python
def on_pause(func: Any) -> Any
```

Register a listener for when playback pauses. Callback: ``(old_state, new_state)``.

<a id="haclient.domains.media_player.MediaPlayer.on_stop"></a>

#### on\_stop

```python
def on_stop(func: Any) -> Any
```

Register a listener for when playback stops. Callback: ``(old_state, new_state)``.

<a id="haclient.domains.media_player.MediaPlayer.remove_granular_listener"></a>

#### remove\_granular\_listener

```python
def remove_granular_listener(func: ValueChangeHandler) -> None
```

Remove a granular listener, including media-change listeners.

<a id="haclient.domains.media_player.MediaPlayer.is_playing"></a>

#### is\_playing

```python
@property
def is_playing() -> bool
```

``True`` if the media player is currently playing.

<a id="haclient.domains.media_player.MediaPlayer.is_paused"></a>

#### is\_paused

```python
@property
def is_paused() -> bool
```

``True`` if the media player is currently paused.

<a id="haclient.domains.media_player.MediaPlayer.is_muted"></a>

#### is\_muted

```python
@property
def is_muted() -> bool
```

``True`` if the media player is currently muted.

<a id="haclient.domains.media_player.MediaPlayer.volume_level"></a>

#### volume\_level

```python
@property
def volume_level() -> float | None
```

Current volume level (``0.0`` – ``1.0``) or ``None`` if unknown.

<a id="haclient.domains.media_player.MediaPlayer.now_playing"></a>

#### now\_playing

```python
@property
def now_playing() -> NowPlaying
```

Structured snapshot of the currently playing media.

<a id="haclient.domains.media_player.MediaPlayer.play"></a>

#### play

```python
async def play() -> None
```

Resume / start playback.

<a id="haclient.domains.media_player.MediaPlayer.pause"></a>

#### pause

```python
async def pause() -> None
```

Pause playback.

<a id="haclient.domains.media_player.MediaPlayer.play_pause"></a>

#### play\_pause

```python
async def play_pause() -> None
```

Toggle play/pause.

<a id="haclient.domains.media_player.MediaPlayer.stop"></a>

#### stop

```python
async def stop() -> None
```

Stop playback.

<a id="haclient.domains.media_player.MediaPlayer.next"></a>

#### next

```python
async def next() -> None
```

Skip to the next track.

<a id="haclient.domains.media_player.MediaPlayer.previous"></a>

#### previous

```python
async def previous() -> None
```

Skip to the previous track.

<a id="haclient.domains.media_player.MediaPlayer.set_volume"></a>

#### set\_volume

```python
async def set_volume(level: float) -> None
```

Set the volume level (``0.0`` – ``1.0``).

<a id="haclient.domains.media_player.MediaPlayer.mute"></a>

#### mute

```python
async def mute(muted: bool = True) -> None
```

Mute or unmute the media player.

<a id="haclient.domains.media_player.MediaPlayer.turn_on"></a>

#### turn\_on

```python
async def turn_on() -> None
```

Power the media player on.

<a id="haclient.domains.media_player.MediaPlayer.turn_off"></a>

#### turn\_off

```python
async def turn_off() -> None
```

Power the media player off.

<a id="haclient.domains.media_player.MediaPlayer.select_source"></a>

#### select\_source

```python
async def select_source(source: str) -> None
```

Select an input source.

<a id="haclient.domains.media_player.MediaPlayer.play_media"></a>

#### play\_media

```python
async def play_media(media_content_type: str, media_content_id: str,
                     **extra: Any) -> None
```

Play a specific media item (by content type / id).

<a id="haclient.domains.media_player.MediaPlayer.browse_media"></a>

#### browse\_media

```python
async def browse_media(media_content_type: str | None = None,
                       media_content_id: str | None = None) -> dict[str, Any]
```

Issue a single ``media_player/browse_media`` WebSocket command.

Returns the raw result dictionary from Home Assistant. Raises
:class:`HAClientError` if the command fails.

<a id="haclient.domains.media_player.MediaPlayer.favorites"></a>

#### favorites

```python
async def favorites(*,
                    max_depth: int = _MAX_BROWSE_DEPTH,
                    max_nodes: int = _MAX_BROWSE_NODES) -> list[FavoriteItem]
```

Return a flattened list of playable items in the media tree.

The method recursively walks the ``browse_media`` tree rooted at the
entity and collects every entry that Home Assistant marks as
``can_play`` (and that has a ``media_content_id``).

If the media player doesn't support browsing, an empty list is
returned (no exception is raised).

Parameters
----------
max_depth:
    Maximum recursion depth. Defaults to a sensible cap to avoid
    pathological trees.
max_nodes:
    Hard upper bound on total nodes visited (also a safety net).

