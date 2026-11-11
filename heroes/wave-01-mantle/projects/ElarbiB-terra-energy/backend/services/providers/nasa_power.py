"""NASA POWER Provider - Legacy provider, kept for fallback."""

import httpx
import pandas as pd
import json
import hashlib
import os
from datetime import datetime
from typing import Optional

from services.weather_provider import WeatherProvider, WeatherRequest, WeatherResponse, WeatherProviderError


class NASAPowerProvider(WeatherProvider):
    """NASA POWER provider - global satellite-derived data.
    
    Coarse resolution (0.5° ≈ 50km), good for fallback only.
    Free, no API key required.
    """

    @property
    def supported_variables(self) -> list[str]:
        return ["ALL", "GHI", "DNI", "DHI", "WS", "WD", "T2M", "RH", "PS", "WS2M", "WS10M", "WS50M", "WD50M"]

    @property
    def supported_regions(self) -> list[str]:
        return ["GLOBAL"]

    # NASA POWER parameter names
    PARAM_MAP = {
        "GHI": "ALLSKY_SFC_SW_DWN",
        "DNI": "ALLSKY_SFC_SW_DNI",
        "DHI": "ALLSKY_SFC_SW_DIFF",
        "WS": "WS10M",
        "WD": "WD50M",
        "T2M": "T2M",
        "RH": "RH2M",
        "PS": "PS",
        "WS2M": "WS2M",
        "WS10M": "WS10M",
        "WS50M": "WS50M",
        "WD50M": "WD50M",
    }

    async def _fetch_raw(self, request: WeatherRequest) -> tuple[pd.DataFrame, dict]:
        base_url = self.config.get("base_url", "https://power.larc.nasa.gov/api/temporal")
        
        # Determine parameters to request
        if "ALL" in request.variables:
            params_list = list(self.PARAM_MAP.values())
        else:
            params_list = [self.PARAM_MAP.get(v, v) for v in request.variables if v in self.PARAM_MAP]
        
        params_str = ",".join(params_list)
        
        params = {
            "parameters": params_str,
            "community": "re",
            "latitude": request.latitude,
            "longitude": request.longitude,
            "start": request.start_date,
            "end": request.end_date,
            "format": "JSON",
        }
        
        if request.resolution == "hourly":
            endpoint = f"{base_url}/hourly/point"
        else:
            endpoint = f"{base_url}/daily/point"
        
        async with httpx.AsyncClient(timeout=self.timeout, verify=False) as client:
            r = await client.get(endpoint, params=params)
            r.raise_for_status()
            data = r.json()

        # Parse NASA POWER response format
        df = self._parse_nasa_response(data, params_list)
        
        metadata = {
            "source": "NASA POWER",
            "resolution": request.resolution,
            "parameters": params_list,
            "header": data.get("header", {}),
        }

        return df, metadata

    def _parse_nasa_response(self, data: dict, params_list: list) -> pd.DataFrame:
        """Parse NASA POWER JSON response to DataFrame."""
        properties = data.get("properties", {})
        parameter_data = properties.get("parameter", {})
        
        if not parameter_data:
            raise WeatherProviderError("No parameter data in NASA POWER response")

        # Build DataFrame from parameter data
        dfs = []
        for param, values in parameter_data.items():
            # values is dict with date strings as keys
            dates = list(values.keys())
            vals = list(values.values())
            
            # Parse dates
            if len(dates[0]) == 8:  # YYYYMMDD
                dates_parsed = pd.to_datetime(dates, format="%Y%m%d")
            elif len(dates[0]) == 10:  # YYYYMMDDHH
                dates_parsed = pd.to_datetime(dates, format="%Y%m%d%H")
            else:
                dates_parsed = pd.to_datetime(dates)
            
            s = pd.Series(vals, index=dates_parsed, name=param.lower())
            dfs.append(s)

        if not dfs:
            raise WeatherProviderError("No valid data series parsed")

        df = pd.concat(dfs, axis=1)
        df.index.name = "time"
        
        return df

    def _transform_to_standard(self, df: pd.DataFrame, metadata: dict, request: WeatherRequest) -> pd.DataFrame:
        """Transform NASA POWER columns to standard names."""
        reverse_map = {v.lower(): k.lower() for k, v in self.PARAM_MAP.items()}
        df.rename(columns=reverse_map, inplace=True)
        
        std_cols = ["ghi", "dni", "dhi", "ws", "wd", "t2m", "rh", "ps"]
        for col in std_cols:
            if col not in df.columns:
                df[col] = pd.NA
        
        for col in std_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        
        # NASA POWER uses -999 for missing
        df.replace(-999, pd.NA, inplace=True)
        
        return df[std_cols]