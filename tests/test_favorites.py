"""Tests for MediaPlayer.favorites() recursive traversal."""

from __future__ import annotations

from typing import Any

from aiohttp import web

from haclient import HAClient

from .fake_ha import FakeHA


def _make_tree() -> dict[str, Any]:
    """Return a multi-level browse_media root used by the browse handler."""
    return {
        "title": "root",
        "media_content_id": "root",
        "media_content_type": "root",
        "can_expand": True,
        "can_play": False,
        "children": [
            {
                "title": "Favorites",
                "media_content_id": "favs",
                "media_content_type": "directory",
                "can_expand": True,
                "can_play": False,
            },
            {
                "title": "Single Track",
                "media_content_id": "track://1",
                "media_content_type": "track",
                "can_expand": False,
                "can_play": True,
            },
            {
                "title": "Single Track dup",
                "media_content_id": "track://1",
                "media_content_type": "track",
                "can_expand": False,
                "can_play": True,
            },
        ],
    }


def _make_subtree() -> dict[str, Any]:
    return {
        "title": "Favorites",
        "media_content_id": "favs",
        "media_content_type": "directory",
        "can_expand": True,
        "can_play": False,
        "children": [
            {
                "title": "Playlist A",
                "media_content_id": "playlist://a",
                "media_content_type": "playlist",
                "can_expand": True,
                "can_play": True,
            },
            {
                "title": "BadItem",
                "media_content_type": "track",
                "can_play": True,
                "can_expand": False,
            },
            "not-a-dict",
        ],
    }


def _make_playlist_a() -> dict[str, Any]:
    return {
        "title": "Playlist A",
        "media_content_id": "playlist://a",
        "media_content_type": "playlist",
        "can_expand": True,
        "can_play": True,
        "children": [
            {
                "title": "Song 1",
                "media_content_id": "song://1",
                "media_content_type": "track",
                "can_expand": False,
                "can_play": True,
            },
            {
                "title": "Song 2",
                "media_content_id": "song://2",
                "media_content_type": "track",
                "can_expand": False,
                "can_play": True,
            },
        ],
    }


async def _browse_handler(server: FakeHA, ws: web.WebSocketResponse, msg: dict[str, Any]) -> None:
    content_id = msg.get("media_content_id")
    if content_id is None:
        result = _make_tree()
    elif content_id == "favs":
        result = _make_subtree()
    elif content_id == "playlist://a":
        result = _make_playlist_a()
    else:
        result = {"children": []}
    await ws.send_json({"id": msg["id"], "type": "result", "success": True, "result": result})


async def test_favorites_flattens_tree(client: HAClient, fake_ha: FakeHA) -> None:
    fake_ha.handlers["media_player/browse_media"] = _browse_handler
    mp = client.media_player("livingroom")
    favs = await mp.favorites()
    titles = [f.title for f in favs]
    ids = [f.media_content_id for f in favs]
    assert "Single Track" in titles
    assert "Playlist A" in titles
    assert "Song 1" in titles
    assert "Song 2" in titles
    assert len(ids) == len(set(ids))
    assert "BadItem" not in titles


async def test_favorites_item_play(client: HAClient, fake_ha: FakeHA) -> None:
    fake_ha.handlers["media_player/browse_media"] = _browse_handler
    mp = client.media_player("livingroom")
    favs = await mp.favorites()
    assert favs
    playlist = next(f for f in favs if f.title == "Playlist A")
    await playlist.play()
    call = fake_ha.ws_service_calls[-1]
    assert call["service"] == "play_media"
    assert call["service_data"]["media_content_id"] == "playlist://a"
    assert call["service_data"]["media_content_type"] == "playlist"
    assert "FavoriteItem" in repr(playlist)


async def test_favorites_returns_empty_when_unsupported(client: HAClient, fake_ha: FakeHA) -> None:
    async def not_supported(server: FakeHA, ws: web.WebSocketResponse, msg: dict[str, Any]) -> None:
        await ws.send_json(
            {
                "id": msg["id"],
                "type": "result",
                "success": False,
                "error": {"code": "not_supported", "message": "nope"},
            }
        )

    fake_ha.handlers["media_player/browse_media"] = not_supported
    mp = client.media_player("livingroom")
    result = await mp.favorites()
    assert result == []


async def test_favorites_max_depth(client: HAClient, fake_ha: FakeHA) -> None:
    """Guard: max_depth stops recursion."""
    fake_ha.handlers["media_player/browse_media"] = _browse_handler
    mp = client.media_player("livingroom")
    favs = await mp.favorites(max_depth=1)
    titles = [f.title for f in favs]
    assert "Single Track" in titles
    assert "Song 1" not in titles


async def test_favorites_max_nodes(client: HAClient, fake_ha: FakeHA) -> None:
    fake_ha.handlers["media_player/browse_media"] = _browse_handler
    mp = client.media_player("livingroom")
    result = await mp.favorites(max_nodes=1)
    assert all(isinstance(f.title, str) for f in result)


async def test_favorites_subtree_failure_is_tolerated(client: HAClient, fake_ha: FakeHA) -> None:
    async def partial(server: FakeHA, ws: web.WebSocketResponse, msg: dict[str, Any]) -> None:
        content_id = msg.get("media_content_id")
        if content_id is None:
            await ws.send_json(
                {
                    "id": msg["id"],
                    "type": "result",
                    "success": True,
                    "result": _make_tree(),
                }
            )
        else:
            await ws.send_json(
                {
                    "id": msg["id"],
                    "type": "result",
                    "success": False,
                    "error": {"code": "fail", "message": "no"},
                }
            )

    fake_ha.handlers["media_player/browse_media"] = partial
    mp = client.media_player("livingroom")
    favs = await mp.favorites()
    titles = [f.title for f in favs]
    assert "Single Track" in titles
    assert "Song 1" not in titles


def _make_sonos_root() -> dict[str, Any]:
    """Root favorites tree mirroring what Sonos/HA returns in the wild."""
    return {
        "title": "Favorites",
        "media_class": "directory",
        "media_content_type": "favorites",
        "media_content_id": "",
        "can_play": False,
        "can_expand": True,
        "thumbnail": None,
        "children": [
            {
                "title": "Albums",
                "media_class": "album",
                "media_content_type": "favorites_folder",
                "media_content_id": "object.container.album.musicAlbum",
                "can_play": False,
                "can_expand": True,
                "thumbnail": None,
            },
            {
                "title": "Playlists",
                "media_class": "playlist",
                "media_content_type": "favorites_folder",
                "media_content_id": "object.container.playlistContainer",
                "can_play": False,
                "can_expand": True,
                "thumbnail": None,
            },
            {
                "title": "Radio",
                "media_class": "genre",
                "media_content_type": "favorites_folder",
                "media_content_id": "object.item.audioItem.audioBroadcast",
                "can_play": False,
                "can_expand": True,
                "thumbnail": None,
            },
        ],
    }


def _make_sonos_radio() -> dict[str, Any]:
    return {
        "title": "Radio",
        "media_class": "directory",
        "media_content_type": "favorites",
        "can_play": False,
        "can_expand": True,
        "children": [
            {
                "title": "Arthur Olsen's Station",
                "media_class": "genre",
                "media_content_type": "favorite_item_id",
                "media_content_id": "FV:2/2",
                "can_play": True,
                "can_expand": False,
                "thumbnail": "https://example.com/arthur.jpg",
            },
            {
                "title": "Kringvarp Foroya",
                "media_class": "genre",
                "media_content_type": "favorite_item_id",
                "media_content_id": "FV:2/0",
                "can_play": True,
                "can_expand": False,
                "thumbnail": "https://example.com/kringvarp.png",
            },
        ],
    }


def _make_sonos_albums() -> dict[str, Any]:
    return {
        "title": "Albums",
        "media_class": "directory",
        "media_content_type": "favorites",
        "can_play": False,
        "can_expand": True,
        "children": [
            {
                "title": "Abbey Road",
                "media_class": "album",
                "media_content_type": "favorite_item_id",
                "media_content_id": "FV:2/10",
                "can_play": True,
                "can_expand": False,
                "thumbnail": "https://example.com/abbey.jpg",
            },
        ],
    }


def _make_sonos_playlists() -> dict[str, Any]:
    return {
        "title": "Playlists",
        "media_class": "directory",
        "media_content_type": "favorites",
        "can_play": False,
        "can_expand": True,
        "children": [
            {
                "title": "Chill Vibes",
                "media_class": "playlist",
                "media_content_type": "favorite_item_id",
                "media_content_id": "FV:2/20",
                "can_play": True,
                "can_expand": False,
                "thumbnail": None,
            },
        ],
    }


async def _sonos_browse_handler(
    server: FakeHA, ws: web.WebSocketResponse, msg: dict[str, Any]
) -> None:
    content_id = msg.get("media_content_id")
    if content_id is None or content_id == "":
        result = _make_sonos_root()
    elif content_id == "object.item.audioItem.audioBroadcast":
        result = _make_sonos_radio()
    elif content_id == "object.container.album.musicAlbum":
        result = _make_sonos_albums()
    elif content_id == "object.container.playlistContainer":
        result = _make_sonos_playlists()
    else:
        result = {"children": []}
    await ws.send_json({"id": msg["id"], "type": "result", "success": True, "result": result})


async def test_favorites_captures_category_and_thumbnail(client: HAClient, fake_ha: FakeHA) -> None:
    """Each favorite should expose thumbnail + category (parent folder title)."""
    fake_ha.handlers["media_player/browse_media"] = _sonos_browse_handler
    mp = client.media_player("livingroom")
    favs = await mp.favorites()

    by_title = {f.title: f for f in favs}

    arthur = by_title["Arthur Olsen's Station"]
    assert arthur.category == "Radio"
    assert arthur.thumbnail == "https://example.com/arthur.jpg"
    assert arthur.media_class == "genre"

    abbey = by_title["Abbey Road"]
    assert abbey.category == "Albums"
    assert abbey.thumbnail == "https://example.com/abbey.jpg"
    assert abbey.media_class == "album"

    chill = by_title["Chill Vibes"]
    assert chill.category == "Playlists"
    assert chill.thumbnail is None
    assert chill.media_class == "playlist"


async def test_favorites_repr_includes_new_fields(client: HAClient, fake_ha: FakeHA) -> None:
    fake_ha.handlers["media_player/browse_media"] = _sonos_browse_handler
    mp = client.media_player("livingroom")
    favs = await mp.favorites()
    arthur = next(f for f in favs if f.title == "Arthur Olsen's Station")
    text = repr(arthur)
    assert "category='Radio'" in text
    assert "thumbnail=" in text
    assert "https://example.com/arthur.jpg" in text


async def test_browse_media_malformed_response(client: HAClient, fake_ha: FakeHA) -> None:
    async def bad(server: FakeHA, ws: web.WebSocketResponse, msg: dict[str, Any]) -> None:
        await ws.send_json(
            {
                "id": msg["id"],
                "type": "result",
                "success": True,
                "result": "not-a-dict",
            }
        )

    fake_ha.handlers["media_player/browse_media"] = bad
    mp = client.media_player("livingroom")
    assert await mp.favorites() == []
