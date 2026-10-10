"""NSRDB Provider - NREL National Solar Radiation Database."""

import httpx
import pandas as pd
import json
import os
from datetime import datetime
from typing import Optional

from services.weather_provider import WeatherProvider, WeatherRequest, WeatherResponse, WeatherProviderError


class NSRDBProvider(WeatherProvider):
    """NSRDB (National Solar Radiation Database) provider.
    
    Covers Americas primarily, global coverage in v2+.
    Provides 30-min or hourly data, TMY available.
    Requires free API key from developer.nrel.gov
    """

    @property
    def supported_variables(self) -> list[str]:
        return ["GHI", "DNI", "DHI", "WS", "WD", "T2M", "RH", "PS", "ALL"]

    @property
    def supported_regions(self) -> list[str]:
        return ["NA", "GLOBAL"]

    def __init__(self, name: str, config: dict, cache_dir: str, timeout: int = 30):
        super().__init__(name, config, cache_dir, timeout)
        self.api_key = os.getenv(config.get("api_key_env", "NSRDB_API_KEY"), "")
        if not self.api_key:
            raise WeatherProviderError("NSRDB_API_KEY not set in environment")

    async def _fetch_raw(self, request: WeatherRequest) -> tuple[pd.DataFrame, dict]:
        base_url = self.config.get("base_url", "https://developer.nrel.gov/api/nsrdb/v2")
        
        if request.use_tmy:
            return await self._fetch_tmy(request, base_url)
        else:
            return await self._fetch_hourly(request, base_url)

    async def _fetch_tmy(self, request: WeatherRequest, base_url: str) -> tuple[pd.DataFrame, dict]:
        """Fetch Typical Meteorological Year data."""
        params = {
            "api_key": self.api_key,
            "lat": request.latitude,
            "lon": request.longitude,
            "format": "csv",
            "attributes": "ghi,dni,dhi,wind_speed,wind_direction,air_temperature,relative_humidity,surface_pressure",
            "names": "tmy",
            "leap_day": "false",
            "interval": "60",
            "utc": "true",
        }
        
        url = f"{base_url}/solar/psm3-tmy-download"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.get(url, params=params)
            r.raise_for_status()
            
            # NSRDB returns CSV
            content = r.text
            lines = content.strip().split('\n')
            
            # Parse header (first 2 lines are metadata)
            header_line = lines[1] if len(lines) > 1 else lines[0]
            data_lines = lines[2:] if len(lines) > 2 else []
            
            import io
            df = pd.read_csv(io.StringIO('\n'.join([header_line] + data_lines)))
            
            # NSRDB TMY has Year, Month, Day, Hour, Minute columns
            if "Year" in df.columns:
                df["time"] = pd.to_datetime(df[["Year", "Month", "Day", "Hour", "Minute"]])
                df.set_index("time", inplace=True)
                df.drop(columns=["Year", "Month", "Day", "Hour", "Minute"], inplace=True, errors="ignore")

        column_map = {
            "GHI": "ghi",
            "DNI": "dni",
            "DHI": "dhi",
            "Wind Speed": "ws",
            "Wind Direction": "wd",
            "Temperature": "t2m",
            "Relative Humidity": "rh",
            "Surface Pressure": "ps",
        }
        df.rename(columns=column_map, inplace=True)

        metadata = {
            "source": "NSRDB-TMY",
            "data_type": "TMY",
            "version": "PSM3",
        }

        return df, metadata

    async def _fetch_hourly(self, request: WeatherRequest, base_url: str) -> tuple[pd.DataFrame, dict]:
        """Fetch historical hourly data."""
        params = {
            "api_key": self.api_key,
            "lat": request.latitude,
            "lon": request.longitude,
            "format": "csv",
            "attributes": "ghi,dni,dhi,wind_speed,wind_direction,air_temperature,relative_humidity,surface_pressure",
            "names": request.start_date[:4],  # Year
            "leap_day": "false",
            "interval": "30" if self.config.get("half_hourly") else "60",
            "utc": "true",
        }
        
        # For multi-year, we need to fetch each year separately
        start_year = int(request.start_date[:4])
        end_year = int(request.end_date[:4])
        
        dfs = []
        for year in range(start_year, end_year + 1):
            params["names"] = str(year)
            url = f"{base_url}/solar/psm3-download"
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                r = await client.get(url, params=params)
                r.raise_for_status()
                
                content = r.text
                lines = content.strip().split('\n')
                header_line = lines[1] if len(lines) > 1 else lines[0]
                data_lines = lines[2:] if len(lines) > 2 else []
                
                import io
                df = pd.read_csv(io.StringIO('\n'.join([header_line] + data_lines)))
                
                if "Year" in df.columns:
                    df["time"] = pd.to_datetime(df[["Year", "Month", "Day", "Hour", "Minute"]])
                    df.set_index("time", inplace=True)
                    df.drop(columns=["Year", "Month", "Day", "Hour", "Minute"], inplace=True, errors="ignore")
                
                dfs.append(df)

        if not dfs:
            raise WeatherProviderError("No data fetched from NSRDB")

        combined = pd.concat(dfs).sort_index()
        
        column_map = {
            "GHI": "ghi",
            "DNI": "dni",
            "DHI": "dhi",
            "Wind Speed": "ws",
            "Wind Direction": "wd",
            "Temperature": "t2m",
            "Relative Humidity": "rh",
            "Surface Pressure": "ps",
        }
        combined.rename(columns=column_map, inplace=True)

        metadata = {
            "source": "NSRDB",
            "data_type": "historical",
            "version": "PSM3",
            "years": list(range(start_year, end_year + 1)),
        }

        return combined, metadata

    def _transform_to_standard(self, df: pd.DataFrame, metadata: dict, request: WeatherRequest) -> pd.DataFrame:
        """Ensure standard column names and types."""
        std_cols = ["ghi", "dni", "dhi", "ws", "wd", "t2m", "rh", "ps"]
        for col in std_cols:
            if col not in df.columns:
                df[col] = pd.NA
        
        for col in std_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        
        # Resample to hourly if half-hourly
        if self.config.get("half_hourly") and len(df) > 0:
            df = df.resample("H").mean()
        
        return df[std_cols]