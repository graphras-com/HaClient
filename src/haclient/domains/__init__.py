"""Domain-specific `Entity` subclasses.

Importing this package registers every built-in `DomainSpec` with the
shared `DomainRegistry`. Domains that are not imported are simply
unavailable; this is the basis for opt-in / opt-out loading.
"""

from haclient.domains.binary_sensor import BinarySensor
from haclient.domains.climate import Climate
from haclient.domains.cover import Cover
from haclient.domains.light import Light
from haclient.domains.lock import Lock
from haclient.domains.media_player import FavoriteItem, MediaPlayer, NowPlaying
from haclient.domains.scene import Scene
from haclient.domains.sensor import Sensor
from haclient.domains.switch import Switch
from haclient.domains.timer import Timer

__all__ = [
    "BinarySensor",
    "Climate",
    "Cover",
    "FavoriteItem",
    "Light",
    "Lock",
    "MediaPlayer",
    "NowPlaying",
    "Scene",
    "Sensor",
    "Switch",
    "Timer",
]
