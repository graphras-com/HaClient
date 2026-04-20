"""Domain-specific :class:`~ha_client.entity.Entity` subclasses."""

from .binary_sensor import BinarySensor
from .climate import Climate
from .cover import Cover
from .light import Light
from .media_player import FavoriteItem, MediaPlayer, NowPlaying
from .sensor import Sensor
from .switch import Switch

__all__ = [
    "BinarySensor",
    "Climate",
    "Cover",
    "FavoriteItem",
    "Light",
    "MediaPlayer",
    "NowPlaying",
    "Sensor",
    "Switch",
]
