"""Open-Meteo Provider - Free Weather API."""

import httpx
import pandas as pd
import json
from datetime import datetime
from typing import Optional

from services.weather_provider import WeatherProvider, WeatherRequest, WeatherResponse, WeatherProviderError


class OpenMeteoProvider(WeatherProvider):
    """Open-Meteo provider - free, no API key required.
    
    Global coverage, hourly data, good for real-time/recent data.
    Aggregates multiple models (ECMWF, GFS, ICON, etc.)
    """

    @property
    def supported_variables(self) -> list[str]:
        return ["GHI", "DNI", "WS", "WD", "T2M", "RH", "PS", "ALL"]

    @property
    def supported_regions(self) -> list[str]:
        return ["GLOBAL"]

    async def _fetch_raw(self, request: WeatherRequest) -> tuple[pd.DataFrame, dict]:
        base_url = self.config.get("base_url", "https://archive-api.open-meteo.com/v1/archive")
        
        # Map variables to Open-Meteo parameters
        param_map = {
            "GHI": "shortwave_radiation",
            "DNI": "direct_normal_irradiance",
            "WS": "windspeed_10m",
            "WD": "winddirection_10m",
            "T2M": "temperature_2m",
            "RH": "relativehumidity_2m",
            "PS": "surface_pressure",
        }
        
        if "ALL" in request.variables:
            hourly_params = list(param_map.values())
        else:
            hourly_params = [param_map.get(v, v) for v in request.variables if v in param_map]
        
        params = {
            "latitude": request.latitude,
            "longitude": request.longitude,
            "start_date": f"{request.start_date[:4]}-{request.start_date[4:6]}-{request.start_date[6:8]}",
            "end_date": f"{request.end_date[:4]}-{request.end_date[4:6]}-{request.end_date[6:8]}",
            "hourly": ",".join(hourly_params),
            "timezone": "UTC",
            "format": "json",
        }
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.get(base_url, params=params)
            r.raise_for_status()
            data = r.json()

        hourly = data.get("hourly", {})
        if not hourly:
            raise WeatherProviderError("No hourly data in Open-Meteo response")

        # Build DataFrame
        df = pd.DataFrame(hourly)
        df["time"] = pd.to_datetime(df["time"])
        df.set_index("time", inplace=True)

        # Rename to standard
        reverse_map = {v: k.lower() for k, v in param_map.items()}
        df.rename(columns=reverse_map, inplace=True)

        metadata = {
            "source": "Open-Meteo",
            "data_type": "archive",
            "models": data.get("generationtime_ms", 0),
            "utc_offset": data.get("utc_offset_seconds", 0),
        }

        return df, metadata

    def _transform_to_standard(self, df: pd.DataFrame, metadata: dict, request: WeatherRequest) -> pd.DataFrame:
        """Ensure standard column names and types."""
        std_cols = ["ghi", "dni", "dhi", "ws", "wd", "t2m", "rh", "ps"]
        for col in std_cols:
            if col not in df.columns:
                df[col] = pd.NA
        
        for col in std_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        
        # Open-Meteo doesn't provide DHI directly, estimate from GHI and DNI
        if "ghi" in df.columns and "dni" in df.columns and "dhi" not in df.columns:
            # Approximate DHI = GHI - DNI * cos(zenith)
            # Simplified: DHI ≈ GHI - DNI * 0.5 (rough average)
            df["dhi"] = df["ghi"] - df["dni"] * 0.5
            df["dhi"] = df["dhi"].clip(lower=0)
        
        return df[std_cols]