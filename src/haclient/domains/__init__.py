"""Domain-specific `Entity` subclasses.

Importing this package registers every built-in `DomainSpec` with the
shared `DomainRegistry`. Domains that are not imported are simply
unavailable; this is the basis for opt-in / opt-out loading.
"""

from haclient.domains.air_quality import AirQuality
from haclient.domains.binary_sensor import BinarySensor
from haclient.domains.climate import Climate
from haclient.domains.cover import Cover
from haclient.domains.event import Event
from haclient.domains.fan import Fan
from haclient.domains.humidifier import Humidifier
from haclient.domains.light import Light
from haclient.domains.lock import Lock
from haclient.domains.media_player import FavoriteItem, MediaPlayer, NowPlaying
from haclient.domains.scene import Scene
from haclient.domains.sensor import Sensor
from haclient.domains.switch import Switch
from haclient.domains.timer import Timer
from haclient.domains.vacuum import Vacuum
from haclient.domains.valve import Valve

__all__ = [
    "AirQuality",
    "BinarySensor",
    "Climate",
    "Cover",
    "Event",
    "Fan",
    "FavoriteItem",
    "Humidifier",
    "Light",
    "Lock",
    "MediaPlayer",
    "NowPlaying",
    "Scene",
    "Sensor",
    "Switch",
    "Timer",
    "Vacuum",
    "Valve",
]
