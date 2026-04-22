"""``media_player`` domain implementation.

This module also contains the :class:`FavoriteItem` helper returned by
:meth:`MediaPlayer.favorites`, which recursively traverses the
``media_player/browse_media`` tree and flattens it into a list of directly
playable items.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from ..entity import Entity, ValueChangeHandler
from ..exceptions import CommandError, HAClientError

_LOGGER = logging.getLogger(__name__)

# Safety cap so that misbehaving integrations cannot send us into a huge tree.
_MAX_BROWSE_NODES = 2000
_MAX_BROWSE_DEPTH = 6


def _now_playing_from_attrs(attrs: dict[str, Any]) -> NowPlaying:
    """Build a :class:`NowPlaying` from a raw HA attributes dict."""
    features = attrs.get("supported_features") or 0
    return NowPlaying(
        source=attrs.get("source"),
        title=attrs.get("media_title"),
        artist=attrs.get("media_artist"),
        album=attrs.get("media_album_name"),
        channel=attrs.get("media_channel"),
        content_type=attrs.get("media_content_type"),
        content_id=attrs.get("media_content_id"),
        duration=attrs.get("media_duration"),
        entity_picture=attrs.get("entity_picture"),
        queue_position=attrs.get("queue_position"),
        queue_size=attrs.get("queue_size"),
        playlist=attrs.get("media_playlist"),
        repeat=attrs.get("repeat"),
        next=bool(features & 32),
        previous=bool(features & 16),
    )


@dataclass(frozen=True)
class NowPlaying:
    """Structured snapshot of the media currently playing on a media player.

    Groups all identity-related media attributes into a single object.
    Position/progress fields are intentionally excluded — they change
    continuously during playback and do not represent a change in *what*
    is playing.

    Instances are frozen (immutable and hashable) so two snapshots can be
    compared with ``==`` to detect whether the playing media changed.
    """

    source: str | None = None
    title: str | None = None
    artist: str | None = None
    album: str | None = None
    channel: str | None = None
    content_type: str | None = None
    content_id: str | None = None
    duration: int | None = None
    entity_picture: str | None = None
    queue_position: int | None = None
    queue_size: int | None = None
    playlist: str | None = None
    repeat: str | None = None
    next: bool = False
    previous: bool = False


class FavoriteItem:
    """A flattened, directly-playable entry discovered via ``browse_media``.

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
    """

    __slots__ = (
        "title",
        "media_content_id",
        "media_content_type",
        "thumbnail",
        "category",
        "media_class",
        "_player",
    )

    def __init__(
        self,
        *,
        title: str,
        media_content_id: str,
        media_content_type: str,
        player: MediaPlayer,
        thumbnail: str | None = None,
        category: str | None = None,
        media_class: str | None = None,
    ) -> None:
        self.title = title
        self.media_content_id = media_content_id
        self.media_content_type = media_content_type
        self.thumbnail = thumbnail
        self.category = category
        self.media_class = media_class
        self._player = player

    async def play(self) -> None:
        """Play this favorite on its :class:`MediaPlayer`."""
        await self._player.play_media(self.media_content_type, self.media_content_id)

    def __repr__(self) -> str:
        return (
            f"FavoriteItem(title={self.title!r}, "
            f"category={self.category!r}, "
            f"media_class={self.media_class!r}, "
            f"media_content_type={self.media_content_type!r}, "
            f"media_content_id={self.media_content_id!r}, "
            f"thumbnail={self.thumbnail!r})"
        )


class MediaPlayer(Entity):
    """A Home Assistant media player entity."""

    domain = "media_player"

    def __init__(self, entity_id: str, client: Any) -> None:
        super().__init__(entity_id, client)
        self._media_change_listeners: list[ValueChangeHandler] = []

    # --------------------------------------------------------------- events
    def on_volume_change(self, func: Any) -> Any:
        """Register a listener for volume level changes. Callback: ``(old, new)``."""
        return self._register_attr_listener("volume_level", func)

    def on_mute_change(self, func: Any) -> Any:
        """Register a listener for mute state changes. Callback: ``(old, new)``."""
        return self._register_attr_listener("is_volume_muted", func)

    def on_media_change(self, func: Any) -> Any:
        """Register a listener for when the playing media changes.

        Fires when any identity attribute changes (source, title, artist,
        album, channel, content_type, content_id, duration, entity_picture,
        queue_position, queue_size, playlist, repeat, next, previous)
        but **not** on position/progress updates.

        Callback: ``(old: NowPlaying, new: NowPlaying)``.
        """
        self._media_change_listeners.append(func)
        return func

    def on_play(self, func: Any) -> Any:
        """Register a listener for when playback starts. Callback: ``(old_state, new_state)``."""
        return self._register_state_transition_listener("playing", func)

    def on_pause(self, func: Any) -> Any:
        """Register a listener for when playback pauses. Callback: ``(old_state, new_state)``."""
        return self._register_state_transition_listener("paused", func)

    def on_stop(self, func: Any) -> Any:
        """Register a listener for when playback stops. Callback: ``(old_state, new_state)``."""
        return self._register_state_transition_listener("idle", func)

    def _dispatch_granular_events(
        self,
        old_state: dict[str, Any] | None,
        new_state: dict[str, Any] | None,
    ) -> None:
        """Dispatch base events plus :meth:`on_media_change`."""
        super()._dispatch_granular_events(old_state, new_state)
        old_attrs = (old_state or {}).get("attributes") or {}
        new_attrs = (new_state or {}).get("attributes") or {}
        old_np = _now_playing_from_attrs(old_attrs)
        new_np = _now_playing_from_attrs(new_attrs)
        if old_np != new_np:
            for listener in list(self._media_change_listeners):
                self._schedule_value(listener, old_np, new_np)

    def remove_granular_listener(self, func: ValueChangeHandler) -> None:
        """Remove a granular listener, including media-change listeners."""
        import contextlib

        with contextlib.suppress(ValueError):
            self._media_change_listeners.remove(func)
            return
        super().remove_granular_listener(func)

    # ------------------------------------------------------------------ state
    @property
    def is_playing(self) -> bool:
        """``True`` if the media player is currently playing."""
        return self.state == "playing"

    @property
    def is_paused(self) -> bool:
        """``True`` if the media player is currently paused."""
        return self.state == "paused"

    @property
    def is_muted(self) -> bool:
        """``True`` if the media player is currently muted."""
        return bool(self.attributes.get("is_volume_muted"))

    @property
    def volume_level(self) -> float | None:
        """Current volume level (``0.0`` – ``1.0``) or ``None`` if unknown."""
        value = self.attributes.get("volume_level")
        return float(value) if isinstance(value, (int, float)) else None

    @property
    def now_playing(self) -> NowPlaying:
        """Structured snapshot of the currently playing media."""
        return _now_playing_from_attrs(self.attributes)

    # ------------------------------------------------------------- playback
    async def play(self) -> None:
        """Resume / start playback."""
        await self.call_service("media_play")

    async def pause(self) -> None:
        """Pause playback."""
        await self.call_service("media_pause")

    async def play_pause(self) -> None:
        """Toggle play/pause."""
        await self.call_service("media_play_pause")

    async def stop(self) -> None:
        """Stop playback."""
        await self.call_service("media_stop")

    async def next(self) -> None:
        """Skip to the next track."""
        await self.call_service("media_next_track")

    async def previous(self) -> None:
        """Skip to the previous track."""
        await self.call_service("media_previous_track")

    async def set_volume(self, level: float) -> None:
        """Set the volume level (``0.0`` – ``1.0``)."""
        if not 0.0 <= level <= 1.0:
            raise ValueError("Volume level must be between 0.0 and 1.0")
        await self.call_service("volume_set", {"volume_level": float(level)})

    async def mute(self, muted: bool = True) -> None:
        """Mute or unmute the media player."""
        await self.call_service("volume_mute", {"is_volume_muted": bool(muted)})

    async def turn_on(self) -> None:
        """Power the media player on."""
        await self.call_service("turn_on")

    async def turn_off(self) -> None:
        """Power the media player off."""
        await self.call_service("turn_off")

    async def select_source(self, source: str) -> None:
        """Select an input source."""
        await self.call_service("select_source", {"source": source})

    async def play_media(
        self,
        media_content_type: str,
        media_content_id: str,
        **extra: Any,
    ) -> None:
        """Play a specific media item (by content type / id)."""
        data: dict[str, Any] = {
            "media_content_type": media_content_type,
            "media_content_id": media_content_id,
            **extra,
        }
        await self.call_service("play_media", data)

    # ------------------------------------------------------------- favorites
    async def browse_media(
        self,
        media_content_type: str | None = None,
        media_content_id: str | None = None,
    ) -> dict[str, Any]:
        """Issue a single ``media_player/browse_media`` WebSocket command.

        Returns the raw result dictionary from Home Assistant. Raises
        :class:`HAClientError` if the command fails.
        """
        payload: dict[str, Any] = {
            "type": "media_player/browse_media",
            "entity_id": self.entity_id,
        }
        if media_content_type is not None:
            payload["media_content_type"] = media_content_type
        if media_content_id is not None:
            payload["media_content_id"] = media_content_id
        result = await self._client.ws.send_command(payload)
        if not isinstance(result, dict):
            raise HAClientError("Unexpected browse_media response")
        return result

    async def favorites(
        self,
        *,
        max_depth: int = _MAX_BROWSE_DEPTH,
        max_nodes: int = _MAX_BROWSE_NODES,
    ) -> list[FavoriteItem]:
        """Return a flattened list of playable items in the media tree.

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
        """
        try:
            root = await self.browse_media()
        except CommandError as err:
            _LOGGER.debug("browse_media unsupported for %s: %s", self.entity_id, err)
            return []
        except HAClientError as err:
            _LOGGER.debug("browse_media failed for %s: %s", self.entity_id, err)
            return []

        collected: list[FavoriteItem] = []
        seen: set[tuple[str, str]] = set()
        node_count = 0

        # The "root" node for a favorites browse is typically a generic
        # "Favorites" directory; its title is not useful as a category. We
        # therefore only start inheriting the parent's title as the category
        # once we are at least one level deep.
        async def walk(node: dict[str, Any], depth: int, category: str | None) -> None:
            nonlocal node_count
            if node_count >= max_nodes:
                return
            node_count += 1

            children = node.get("children")
            if not isinstance(children, list):
                return

            for child in children:
                if not isinstance(child, dict):
                    continue
                content_id = child.get("media_content_id")
                content_type = child.get("media_content_type")
                title = child.get("title") or child.get("name") or ""
                can_play = bool(child.get("can_play"))
                can_expand = bool(child.get("can_expand"))
                thumbnail = child.get("thumbnail")
                media_class = child.get("media_class")

                if can_play and isinstance(content_id, str) and isinstance(content_type, str):
                    key = (content_type, content_id)
                    if key not in seen:
                        seen.add(key)
                        collected.append(
                            FavoriteItem(
                                title=str(title),
                                media_content_id=content_id,
                                media_content_type=content_type,
                                player=self,
                                thumbnail=(thumbnail if isinstance(thumbnail, str) else None),
                                category=category
                                or (media_class if isinstance(media_class, str) else None),
                                media_class=(media_class if isinstance(media_class, str) else None),
                            )
                        )

                if (
                    can_expand
                    and depth + 1 < max_depth
                    and isinstance(content_id, str)
                    and isinstance(content_type, str)
                ):
                    try:
                        sub = await self.browse_media(content_type, content_id)
                    except (CommandError, HAClientError) as err:
                        _LOGGER.debug(
                            "browse_media sublevel failed (%s/%s): %s",
                            content_type,
                            content_id,
                            err,
                        )
                        continue
                    except asyncio.CancelledError:
                        raise
                    # Pass the child's title as category for its descendants.
                    # At depth 0 the child *is* a top-level folder like
                    # "Radio" / "Albums" / "Playlists" and its title becomes
                    # the category for everything underneath.
                    child_category = str(title) if title else category
                    await walk(sub, depth + 1, child_category)

        await walk(root, 0, None)
        return collected
