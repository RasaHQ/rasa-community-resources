"""NASA POWER Client - Backward Compatibility Wrapper.

This module wraps the new WeatherService to maintain compatibility
with existing code that uses fetch_power_data, fetch_solar_data, fetch_wind_data.
"""

import json
import os
from typing import Optional

from .weather_service import get_weather_service, WeatherService
from .weather_provider import WeatherRequest


# Legacy parameter mappings
SOLAR_PARAMS = "ALLSKY_SFC_SW_DWN,ALLSKY_SFC_SW_DIFF,ALLSKY_SFC_SW_DNI,CLRSKY_SFC_SW_DWN,ALLSKY_KT,T2M,WS10M,PS"
WIND_PARAMS = "WS2M,WS10M,WS50M,WD50M,U10M,V10M,U50M,V50M,T2M,RHOA,PS"
ALL_PARAMS = "ALLSKY_SFC_SW_DWN,ALLSKY_SFC_SW_DIFF,ALLSKY_SFC_SW_DNI,CLRSKY_SFC_SW_DWN,ALLSKY_KT,WS2M,WS10M,WS50M,WD50M,U10M,V10M,U50M,V50M,T2M,RH2M,PS,PRECTOTCORR,RHOA"


# Legacy cache directory
CACHE_DIR = os.path.join(os.path.dirname(__file__), '..', 'cache')


def _params_to_variables(params: str) -> list[str]:
    """Convert NASA POWER parameter string to standard variable list."""
    param_map = {
        "ALLSKY_SFC_SW_DWN": "GHI",
        "ALLSKY_SFC_SW_DIFF": "DHI",
        "ALLSKY_SFC_SW_DNI": "DNI",
        "CLRSKY_SFC_SW_DWN": "CLRSKY_GHI",
        "ALLSKY_KT": "KT",
        "T2M": "T2M",
        "WS10M": "WS",
        "WS2M": "WS2M",
        "WS50M": "WS50M",
        "WD50M": "WD",
        "U10M": "U10M",
        "V10M": "V10M",
        "U50M": "U50M",
        "V50M": "V50M",
        "RH2M": "RH",
        "PS": "PS",
        "PRECTOTCORR": "PRECIP",
        "RHOA": "RHOA",
    }
    return [param_map.get(p.strip(), p.strip()) for p in params.split(",")]


def _dataframe_to_nasa_format(df, variables: list[str]) -> dict:
    """Convert standardized DataFrame to NASA POWER response format."""
    result = {"properties": {"parameter": {}}}
    
    for var in variables:
        std_var = var.lower()
        if std_var in df.columns:
            series = df[std_var].dropna()
            # Format dates as YYYYMMDDHH for hourly
            data_dict = {}
            for idx, val in series.items():
                if hasattr(idx, 'strftime'):
                    date_str = idx.strftime("%Y%m%d%H")
                else:
                    date_str = str(idx)
                data_dict[date_str] = float(val) if val is not None else -999
            result["properties"]["parameter"][var] = data_dict
    
    return result


async def fetch_power_data(
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str,
    resolution: str = "daily",
    params: str = ALL_PARAMS,
    community: str = "re",
) -> dict:
    """Legacy fetch_power_data - now uses WeatherService."""
    service = get_weather_service()
    
    variables = _params_to_variables(params)
    
    response = await service.get_weather(
        latitude=latitude,
        longitude=longitude,
        start_date=start_date,
        end_date=end_date,
        variables=variables,
        resolution="hourly" if resolution == "hourly" else "daily",
    )
    
    return _dataframe_to_nasa_format(response.data, variables)


async def fetch_solar_data(lat: float, lon: float, start: str, end: str, resolution: str = "hourly") -> dict:
    """Legacy fetch_solar_data - now uses WeatherService."""
    return await fetch_power_data(lat, lon, start, end, resolution, SOLAR_PARAMS)


async def fetch_wind_data(lat: float, lon: float, start: str, end: str, resolution: str = "hourly") -> dict:
    """Legacy fetch_wind_data - now uses WeatherService."""
    return await fetch_power_data(lat, lon, start, end, resolution, WIND_PARAMS)


# For backward compatibility - direct WeatherService access
async def fetch_weather_modern(
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str,
    variables: Optional[list[str]] = None,
    resolution: str = "hourly",
    use_tmy: bool = False,
) -> WeatherRequest:
    """Modern interface returning WeatherResponse."""
    service = get_weather_service()
    return await service.get_weather(
        latitude=latitude,
        longitude=longitude,
        start_date=start_date,
        end_date=end_date,
        variables=variables,
        resolution=resolution,
        use_tmy=use_tmy,
    )