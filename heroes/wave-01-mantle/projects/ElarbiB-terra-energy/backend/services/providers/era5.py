"""ERA5 Provider - ECMWF Reanalysis v5 via CDS API."""

import httpx
import pandas as pd
import json
import os
import tempfile
from datetime import datetime
from typing import Optional

from services.weather_provider import WeatherProvider, WeatherRequest, WeatherResponse, WeatherProviderError


class ERA5Provider(WeatherProvider):
    """ERA5 (ECMWF Reanalysis v5) provider via CDS API.
    
    Global coverage, hourly data, all variables.
    Requires CDS API key (free registration at cds.climate.copernicus.eu).
    Batch processing - can take minutes to hours.
    """

    @property
    def supported_variables(self) -> list[str]:
        return ["ALL", "GHI", "DNI", "DHI", "WS", "WD", "T2M", "RH", "PS", "U", "V"]

    @property
    def supported_regions(self) -> list[str]:
        return ["GLOBAL"]

    def __init__(self, name: str, config: dict, cache_dir: str, timeout: int = 3600):
        super().__init__(name, config, cache_dir, timeout)
        self.api_key = os.getenv(config.get("api_key_env", "CDS_API_KEY"), "")
        self.cds_url = "https://cds.climate.copernicus.eu/api/v2"
        if not self.api_key:
            raise WeatherProviderError("CDS_API_KEY not set in environment")

    async def _fetch_raw(self, request: WeatherRequest) -> tuple[pd.DataFrame, dict]:
        if self.config.get("batch_async", True):
            return await self._fetch_batch_async(request)
        else:
            return await self._fetch_batch_sync(request)

    async def _fetch_batch_async(self, request: WeatherRequest) -> tuple[pd.DataFrame, dict]:
        """Submit batch job and poll for completion."""
        # Prepare request for CDS
        cds_request = self._build_cds_request(request)
        
        # Submit job
        job_id = await self._submit_job(cds_request)
        
        # Poll for completion
        result_url = await self._poll_job(job_id)
        
        # Download and parse
        return await self._download_and_parse(result_url, request)

    async def _fetch_batch_sync(self, request: WeatherRequest) -> tuple[pd.DataFrame, dict]:
        """Synchronous fetch (for small requests only)."""
        cds_request = self._build_cds_request(request)
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.post(
                f"{self.cds_url}/resources/reanalysis-era5-single-levels",
                json={"request": cds_request},
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            r.raise_for_status()
            data = r.json()
            
            if "location" in data:
                return await self._download_and_parse(data["location"], request)
            
        raise WeatherProviderError("No data returned from CDS")

    def _build_cds_request(self, request: WeatherRequest) -> dict:
        """Build CDS API request dictionary."""
        start_year = int(request.start_date[:4])
        end_year = int(request.end_date[:4])
        years = [str(y) for y in range(start_year, end_year + 1)]
        
        # Determine variables needed
        var_map = {
            "GHI": "surface_solar_radiation_downwards",
            "DNI": "direct_solar_radiation",
            "DHI": "diffuse_solar_radiation",
            "WS": "10m_wind_speed",
            "WD": "10m_wind_direction",
            "T2M": "2m_temperature",
            "RH": "2m_relative_humidity",
            "PS": "surface_pressure",
            "U": "10m_u_component_of_wind",
            "V": "10m_v_component_of_wind",
        }
        
        if "ALL" in request.variables:
            variables = list(var_map.values())
        else:
            variables = [var_map.get(v, v) for v in request.variables if v in var_map]
        
        return {
            "product_type": "reanalysis",
            "variable": variables,
            "year": years,
            "month": [f"{m:02d}" for m in range(1, 13)],
            "day": [f"{d:02d}" for d in range(1, 32)],
            "time": [f"{h:02d}:00" for h in range(24)],
            "area": [
                request.latitude + 0.125,  # North
                request.longitude - 0.125,  # West
                request.latitude - 0.125,  # South
                request.longitude + 0.125,  # East
            ],
            "format": "netcdf",
        }

    async def _submit_job(self, cds_request: dict) -> str:
        """Submit batch job to CDS."""
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                f"{self.cds_url}/resources/reanalysis-era5-single-levels",
                json={"request": cds_request},
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            r.raise_for_status()
            data = r.json()
            return data.get("job_id", data.get("uid", ""))

    async def _poll_job(self, job_id: str, max_wait: int = 3600) -> str:
        """Poll job until completion."""
        import asyncio
        waited = 0
        interval = 30
        
        while waited < max_wait:
            async with httpx.AsyncClient(timeout=60) as client:
                r = await client.get(
                    f"{self.cds_url}/jobs/{job_id}",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                r.raise_for_status()
                data = r.json()
                
                status = data.get("status", "unknown")
                if status == "completed":
                    return data.get("location", data.get("download_url", ""))
                elif status == "failed":
                    raise WeatherProviderError(f"CDS job failed: {data.get('message', 'Unknown error')}")
                
            await asyncio.sleep(interval)
            waited += interval
        
        raise WeatherProviderError(f"CDS job timeout after {max_wait}s")

    async def _download_and_parse(self, download_url: str, request: WeatherRequest) -> tuple[pd.DataFrame, dict]:
        """Download NetCDF and convert to DataFrame."""
        async with httpx.AsyncClient(timeout=300) as client:
            r = await client.get(download_url)
            r.raise_for_status()
            content = r.content
        
        # Save to temp file and parse with xarray
        with tempfile.NamedTemporaryFile(suffix=".nc", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        
        try:
            import xarray as xr
            ds = xr.open_dataset(tmp_path)
            
            # Convert to DataFrame
            df = ds.to_dataframe().reset_index()
            
            # Standardize column names
            column_map = {
                "ssrd": "ghi",
                "fdir": "dni",  # Approximate
                "t2m": "t2m",
                "rh": "rh",
                "sp": "ps",
                "si10": "ws",
                "u10": "u",
                "v10": "v",
            }
            df.rename(columns=column_map, inplace=True)
            
            # Calculate derived variables
            if "u" in df.columns and "v" in df.columns:
                df["ws"] = (df["u"]**2 + df["v"]**2)**0.5
                df["wd"] = (180 + pd.np.arctan2(df["u"], df["v"]) * 180 / pd.np.pi) % 360
            
            # DNI approximation from GHI and diffuse
            if "ghi" in df.columns and "dni" not in df.columns and "diffuse" in df.columns:
                df["dni"] = df["ghi"] - df["diffuse"]
            
            # Set time index
            if "time" in df.columns:
                df["time"] = pd.to_datetime(df["time"])
                df.set_index("time", inplace=True)
            
            metadata = {
                "source": "ERA5",
                "resolution": "hourly",
                "grid_resolution": self.config.get("land_resolution", 0.1),
                "variables_requested": list(column_map.values()),
            }
            
            return df, metadata
            
        finally:
            import os
            os.unlink(tmp_path)

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