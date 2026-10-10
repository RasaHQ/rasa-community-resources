"""PVGIS Provider - European Commission Joint Research Centre."""

import httpx
import pandas as pd
import json
from datetime import datetime
from typing import Optional

from services.weather_provider import WeatherProvider, WeatherRequest, WeatherResponse, WeatherProviderError


class PVGISProvider(WeatherProvider):
    """PVGIS (Photovoltaic Geographical Information System) provider.
    
    Covers Europe, Africa, Latin America, Asia.
    Provides SARAH2 (satellite) solar data and ERA5 (reanalysis) meteo data.
    """

    @property
    def supported_variables(self) -> list[str]:
        return ["GHI", "DNI", "DHI", "WS", "WD", "T2M", "RH", "PS", "ALL"]

    @property
    def supported_regions(self) -> list[str]:
        return ["EU", "AF", "LATAM", "ASIA", "GLOBAL"]

    async def _fetch_raw(self, request: WeatherRequest) -> tuple[pd.DataFrame, dict]:
        base_url = self.config.get("base_url", "https://re.jrc.ec.europa.eu/api/v5_2")
        
        if request.use_tmy:
            return await self._fetch_tmy(request, base_url)
        else:
            return await self._fetch_hourly(request, base_url)

    async def _fetch_tmy(self, request: WeatherRequest, base_url: str) -> tuple[pd.DataFrame, dict]:
        """Fetch Typical Meteorological Year data."""
        params = {
            "lat": request.latitude,
            "lon": request.longitude,
            "outputformat": "json",
            "browser": 0,
        }
        
        url = f"{base_url}/PVcalc"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.get(url, params=params)
            r.raise_for_status()
            data = r.json()

        hourly = data.get("outputs", {}).get("hourly", [])
        if not hourly:
            raise WeatherProviderError("No hourly data in TMY response")

        df = pd.DataFrame(hourly)
        df["time"] = pd.to_datetime(df["time"], format="%Y%m%d:%H%M")
        df.set_index("time", inplace=True)

        column_map = {
            "G(h)": "ghi",
            "Gb(n)": "dni",
            "Gd(h)": "dhi",
            "WS10m": "ws",
            "WD10m": "wd",
            "T2m": "t2m",
            "RH": "rh",
            "SP": "ps",
        }
        df.rename(columns=column_map, inplace=True)

        std_cols = ["ghi", "dni", "dhi", "ws", "wd", "t2m", "rh", "ps"]
        available = [c for c in std_cols if c in df.columns]
        df = df[available]

        metadata = {
            "source": "PVGIS-TMY",
            "data_type": "TMY",
            "location": data.get("inputs", {}).get("location", {}),
            "horizon": data.get("inputs", {}).get("horizon", {}),
        }

        return df, metadata

    async def _fetch_hourly(self, request: WeatherRequest, base_url: str) -> tuple[pd.DataFrame, dict]:
        """Fetch hourly time series data from seriescalc endpoint.
        
        The seriescalc endpoint returns both SARAH2 solar data and ERA5 meteo data
        in a single response when pvcalculation=0.
        """
        # Determine date range - PVGIS uses year_min/year_max for historical
        start_year = int(request.start_date[:4])
        end_year = int(request.end_date[:4])

        # PVGIS seriescalc works with a year range, not specific dates.
        # SARAH2 covers 2005-2020: fetch exactly the requested span, clamped to
        # what PVGIS supports. Never expand beyond the request (a 16-year dump
        # makes the whole analysis ~60s and skews the averages).
        year_min = max(2005, min(start_year, end_year))
        year_max = min(2020, max(start_year, end_year))

        if year_min > year_max:
            # Requested years are entirely outside PVGIS availability (e.g. 2023):
            # return the single closest available year instead of the full archive.
            year_min = year_max = min(2020, max(2005, start_year))

        params = {
            "lat": request.latitude,
            "lon": request.longitude,
            "startyear": year_min,
            "endyear": year_max,
            "outputformat": "json",
            "browser": 0,
            "pvcalculation": 0,
            "usehorizon": 1,
            "peakpower": 1,
            "loss": 14,
            "mountingplace": "free",
            "angle": 30,
            "aspect": 0,
        }
        
        url = f"{base_url}/seriescalc"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.get(url, params=params)
            r.raise_for_status()
            data = r.json()

        hourly = data.get("outputs", {}).get("hourly", [])
        if not hourly:
            raise WeatherProviderError("No hourly data in PVGIS seriescalc response")

        df = pd.DataFrame(hourly)
        df["time"] = pd.to_datetime(df["time"], format="%Y%m%d:%H%M")
        df.set_index("time", inplace=True)

        # Column mapping for seriescalc output
        column_map = {
            "G(i)": "ghi",        # Global irradiance on inclined plane
            "Gb(i)": "dni",       # Beam irradiance on inclined plane  
            "Gd(i)": "dhi",       # Diffuse irradiance on inclined plane
            "G(h)": "ghi_h",      # Global horizontal irradiance
            "Gb(n)": "dni_h",     # Direct normal irradiance
            "Gd(h)": "dhi_h",     # Diffuse horizontal irradiance
            "T2m": "t2m",
            "WS10m": "ws",
            "WD10m": "wd",
            "RH": "rh",
            "SP": "ps",
        }
        df.rename(columns=column_map, inplace=True)

        # Use horizontal irradiance for standard GHI/DNI/DHI if available
        if "ghi_h" in df.columns:
            df["ghi"] = df["ghi_h"]
        if "dni_h" in df.columns:
            df["dni"] = df["dni_h"]
        if "dhi_h" in df.columns:
            df["dhi"] = df["dhi_h"]

        metadata = {
            "source": "PVGIS-SARAH2",
            "data_type": "historical",
            "year_range": f"{year_min}-{year_max}",
            "radiation_db": data.get("inputs", {}).get("meteo_data", {}).get("radiation_db", "PVGIS-SARAH2"),
            "meteo_db": data.get("inputs", {}).get("meteo_data", {}).get("meteo_db", "ERA5"),
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
        
        return df[std_cols]