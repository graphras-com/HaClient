# Media Player

`ha_client.domains.media_player.MediaPlayer` — domain: `"media_player"`

Inherits from [`Entity`](base.md#ha_cliententityentity).

## Properties

| Name | Type | Description |
|---|---|---|
| `is_playing` | `bool` | Currently playing |
| `is_paused` | `bool` | Currently paused |
| `volume_level` | `float \| None` | Volume (0.0–1.0) |
| `now_playing` | `NowPlaying` | Structured snapshot of current media |

## `NowPlaying`

A frozen dataclass grouping all media identity attributes. Two instances
compare equal when the same media is playing, regardless of playback
position.

| Attribute | Type | Description |
|---|---|---|
| `source` | `str \| None` | Input source (e.g. `"TV"`, `"Spotify"`) |
| `title` | `str \| None` | Media title |
| `artist` | `str \| None` | Media artist |
| `album` | `str \| None` | Album name |
| `channel` | `str \| None` | Media channel |
| `content_type` | `str \| None` | Content type (e.g. `"music"`) |
| `content_id` | `str \| None` | HA content ID |
| `duration` | `int \| None` | Duration in seconds |
| `entity_picture` | `str \| None` | Entity picture URL |

## Methods

| Method | Signature |
|---|---|
| `play` | `async ()` |
| `pause` | `async ()` |
| `play_pause` | `async ()` |
| `stop` | `async ()` |
| `next` | `async ()` |
| `previous` | `async ()` |
| `set_volume` | `async (level: float)` |
| `mute` | `async (muted: bool = True)` |
| `turn_on` | `async ()` |
| `turn_off` | `async ()` |
| `select_source` | `async (source: str)` |
| `play_media` | `async (media_content_type: str, media_content_id: str, **extra)` |
| `browse_media` | `async (media_content_type: str, media_content_id: str) -> dict` |
| `favorites` | `async (*, max_depth=6, max_nodes=2000) -> list[FavoriteItem]` |

## Event Decorators

| Decorator | Fires when | Callback signature |
|---|---|---|
| `@on_volume_change` | `volume_level` attribute changes | `(old, new)` |
| `@on_mute_change` | `is_volume_muted` attribute changes | `(old, new)` |
| `@on_media_change` | Any media identity attribute changes | `(old: NowPlaying, new: NowPlaying)` |
| `@on_play` | State transitions to `"playing"` | `(old_state, new_state)` |
| `@on_pause` | State transitions to `"paused"` | `(old_state, new_state)` |
| `@on_stop` | State transitions to `"idle"` | `(old_state, new_state)` |

`on_media_change` fires when any of `source`, `title`, `artist`, `album`,
`channel`, `content_type`, `content_id`, `duration`, or `entity_picture`
changes, but **not** when only `media_position` or
`media_position_updated_at` changes.

---

## `FavoriteItem`

Returned by `MediaPlayer.favorites()`.

| Attribute | Type | Description |
|---|---|---|
| `title` | `str` | Display name |
| `media_content_id` | `str` | HA content ID |
| `media_content_type` | `str` | HA content type |
| `thumbnail` | `str \| None` | Image URL |
| `category` | `str \| None` | Parent folder title |
| `media_class` | `str \| None` | Raw HA media class |

### Methods

| Method | Signature |
|---|---|
| `play` | `async () -> None` |
