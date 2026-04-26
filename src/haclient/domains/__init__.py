"""Domain-specific `Entity` subclasses."""

from .binary_sensor import BinarySensor
from .climate import Climate
from .cover import Cover
from .light import Light
from .media_player import FavoriteItem, MediaPlayer, NowPlaying
from .scene import Scene
from .sensor import Sensor
from .switch import Switch
from .timer import Timer

__all__ = [
    "BinarySensor",
    "Climate",
    "Cover",
    "FavoriteItem",
    "Light",
    "MediaPlayer",
    "NowPlaying",
    "Scene",
    "Sensor",
    "Switch",
    "Timer",
]
