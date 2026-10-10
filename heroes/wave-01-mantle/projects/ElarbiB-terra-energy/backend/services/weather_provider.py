"""Weather Provider Abstraction Layer.

Unified interface for all weather data sources (PVGIS, NSRDB, ERA5, Open-Meteo, NASA POWER).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Optional
import pandas as pd


@dataclass
class WeatherRequest:
    """Request parameters for weather data."""
    latitude: float
    longitude: float
    start_date: str  # YYYYMMDD
    end_date: str    # YYYYMMDD
    variables: list[str] = field(default_factory=lambda: ["ALL"])
    resolution: str = "hourly"
    use_tmy: bool = False


@dataclass
class QualityMetadata:
    """Quality metrics for a specific variable from a source."""
    score: float  # 0-1
    uncertainty_pct: float
    bias_corrected: bool = False
    validation_flags: list[str] = field(default_factory=list)
    source_specific: dict = field(default_factory=dict)


@dataclass
class WeatherResponse:
    """Standardized response from any weather provider."""
    source: str
    data: pd.DataFrame
    metadata: dict = field(default_factory=dict)
    quality: dict[str, QualityMetadata] = field(default_factory=dict)
    fetched_at: datetime = field(default_factory=datetime.utcnow)
    request: Optional[WeatherRequest] = None
    raw_response: Optional[dict] = None

    def to_dict(self) -> dict:
        """Serialize for caching."""
        return {
            "source": self.source,
            "data": self.data.to_json(orient="split", date_format="iso"),
            "metadata": self.metadata,
            "quality": {
                k: {
                    "score": v.score,
                    "uncertainty_pct": v.uncertainty_pct,
                    "bias_corrected": v.bias_corrected,
                    "validation_flags": v.validation_flags,
                    "source_specific": v.source_specific,
                }
                for k, v in self.quality.items()
            },
            "fetched_at": self.fetched_at.isoformat(),
            "request": {
                "latitude": self.request.latitude,
                "longitude": self.request.longitude,
                "start_date": self.request.start_date,
                "end_date": self.request.end_date,
                "variables": self.request.variables,
                "resolution": self.request.resolution,
                "use_tmy": self.request.use_tmy,
            } if self.request else None,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "WeatherResponse":
        """Deserialize from cache."""
        data = pd.read_json(d["data"], orient="split")
        quality = {
            k: QualityMetadata(**v) for k, v in d.get("quality", {}).items()
        }
        request = None
        if d.get("request"):
            request = WeatherRequest(**d["request"])
        return cls(
            source=d["source"],
            data=data,
            metadata=d.get("metadata", {}),
            quality=quality,
            fetched_at=datetime.fromisoformat(d["fetched_at"]),
            request=request,
        )


class WeatherProvider(ABC):
    """Abstract base class for weather data providers."""

    def __init__(
        self,
        name: str,
        config: dict,
        cache_dir: str,
        timeout: int = 30,
    ):
        self.name = name
        self.config = config
        self.cache_dir = cache_dir
        self.timeout = timeout
        self._rate_limit_remaining = config.get("rate_limit", 1000)

    @property
    @abstractmethod
    def supported_variables(self) -> list[str]:
        """List of variable names this provider supports."""
        ...

    @property
    @abstractmethod
    def supported_regions(self) -> list[str]:
        """List of region codes this provider covers."""
        ...

    @abstractmethod
    async def _fetch_raw(self, request: WeatherRequest) -> tuple[pd.DataFrame, dict]:
        """Fetch raw data from the source. Returns (DataFrame, metadata)."""
        ...

    def _transform_to_standard(self, df: pd.DataFrame, metadata: dict, request: WeatherRequest) -> pd.DataFrame:
        """Transform provider-specific format to standard format.
        
        Standard columns: ghi, dni, dhi, ws, wd, t2m, rh, ps, time (index)
        """
        return df

    def _calculate_quality(self, df: pd.DataFrame, request: WeatherRequest) -> dict[str, QualityMetadata]:
        """Calculate quality metrics for the response."""
        quality = {}
        base_quality = self.config.get("quality_base", 0.8)
        
        for var in request.variables:
            if var == "ALL":
                # Check all standard columns
                std_cols = ["ghi", "dni", "dhi", "ws", "wd", "t2m", "rh", "ps"]
                for col in std_cols:
                    if col in df.columns:
                        completeness = 1.0 - df[col].isna().mean()
                        quality[col] = QualityMetadata(
                            score=base_quality * completeness,
                            uncertainty_pct=(1.0 - completeness) * 100 + 5.0,
                            source_specific={"completeness": completeness},
                        )
                continue
            
            col = var.lower()
            if col in df.columns:
                # Simple quality: completeness + base quality
                completeness = 1.0 - df[col].isna().mean()
                quality[col] = QualityMetadata(
                    score=base_quality * completeness,
                    uncertainty_pct=(1.0 - completeness) * 100 + 5.0,
                    source_specific={"completeness": completeness},
                )
        return quality

    async def fetch(self, request: WeatherRequest) -> WeatherResponse:
        """Main fetch method with caching and error handling."""
        cache_key = self._get_cache_key(request)
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        try:
            raw_df, metadata = await self._fetch_raw(request)
            std_df = self._transform_to_standard(raw_df, metadata, request)
            quality = self._calculate_quality(std_df, request)

            response = WeatherResponse(
                source=self.name,
                data=std_df,
                metadata=metadata,
                quality=quality,
                request=request,
            )

            self._set_cached(cache_key, response)
            return response

        except Exception as e:
            raise WeatherProviderError(f"{self.name}: {str(e)}") from e

    def _get_cache_key(self, request: WeatherRequest) -> str:
        """Generate cache key for request."""
        import hashlib
        raw = f"{self.name}:{request.latitude}:{request.longitude}:{request.start_date}:{request.end_date}:{request.resolution}:{','.join(sorted(request.variables))}:{request.use_tmy}"
        return hashlib.md5(raw.encode()).hexdigest()

    def _get_cached(self, key: str) -> Optional[WeatherResponse]:
        """Retrieve cached response if valid."""
        import os
        import json
        path = os.path.join(self.cache_dir, f"{key}.json")
        if not os.path.exists(path):
            return None
        
        ttl_days = self.config.get("cache_ttl_days", 7)
        mtime = os.path.getmtime(path)
        age_hours = (datetime.now().timestamp() - mtime) / 3600
        if age_hours > ttl_days * 24:
            return None

        try:
            with open(path, 'r') as f:
                data = json.load(f)
            return WeatherResponse.from_dict(data)
        except Exception:
            return None

    def _set_cached(self, key: str, response: WeatherResponse):
        """Save response to cache."""
        import os
        import json
        os.makedirs(self.cache_dir, exist_ok=True)
        path = os.path.join(self.cache_dir, f"{key}.json")
        with open(path, 'w') as f:
            json.dump(response.to_dict(), f)

    def supports_region(self, region: str) -> bool:
        """Check if provider supports a region."""
        return region in self.supported_regions or "GLOBAL" in self.supported_regions

    def get_region(self, lat: float, lon: float) -> str:
        """Determine region code from coordinates."""
        # Simplified region detection
        if -25 <= lat <= 70 and -30 <= lon <= 60:
            return "EU"
        elif -35 <= lat <= 37 and -20 <= lon <= 55:
            return "AF"
        elif -60 <= lat <= 30 and -120 <= lon <= -30:
            return "LATAM"
        elif 10 <= lat <= 55 and 60 <= lon <= 150:
            return "ASIA"
        elif 15 <= lat <= 70 and -170 <= lon <= -50:
            return "NA"
        return "GLOBAL"


class WeatherProviderError(Exception):
    """Exception raised by weather providers."""
    pass