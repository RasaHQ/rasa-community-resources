"""Weather Providers Package."""

from .pvgis import PVGISProvider
from .nsrdb import NSRDBProvider
from .era5 import ERA5Provider
from .open_meteo import OpenMeteoProvider
from .nasa_power import NASAPowerProvider

__all__ = [
    "PVGISProvider",
    "NSRDBProvider",
    "ERA5Provider",
    "OpenMeteoProvider",
    "NASAPowerProvider",
]

# Provider registry mapping
PROVIDER_CLASSES = {
    "pvgis": PVGISProvider,
    "nsrdb": NSRDBProvider,
    "era5": ERA5Provider,
    "open_meteo": OpenMeteoProvider,
    "nasa_power": NASAPowerProvider,
}