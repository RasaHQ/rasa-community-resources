"""Weather API Router - Endpoints for weather data sources and quality."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional

from services.weather_service import get_weather_service


router = APIRouter(prefix="/api/weather", tags=["Weather Data"])


class WeatherRequest(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    start_date: str = Field(..., pattern=r"^\d{8}$")
    end_date: str = Field(..., pattern=r"^\d{8}$")
    variables: Optional[list[str]] = None
    resolution: str = "hourly"
    use_tmy: bool = False
    strategy: Optional[str] = None
    topography: str = "flat"


class SourceInfo(BaseModel):
    name: str
    enabled: bool
    priority: int
    regions: list[str]
    variables: list[str]
    quality_base: float


@router.get("/sources", response_model=list[SourceInfo])
async def list_sources():
    """List all available weather data sources."""
    service = get_weather_service()
    return service.get_available_sources()


@router.get("/sources/{source_name}")
async def get_source_info(source_name: str):
    """Get detailed configuration for a specific source."""
    service = get_weather_service()
    info = service.get_source_info(source_name)
    if not info:
        raise HTTPException(status_code=404, detail=f"Source '{source_name}' not found")
    return info


@router.post("/fetch")
async def fetch_weather(request: WeatherRequest):
    """Fetch weather data with full quality pipeline."""
    try:
        service = get_weather_service()
        response = await service.get_weather(
            latitude=request.latitude,
            longitude=request.longitude,
            start_date=request.start_date,
            end_date=request.end_date,
            variables=request.variables,
            resolution=request.resolution,
            use_tmy=request.use_tmy,
            strategy=request.strategy,
            topography=request.topography,
        )
        
        # Convert DataFrame to JSON-serializable format
        data_json = response.data.to_json(orient="split", date_format="iso")
        
        return {
            "source": response.source,
            "data": data_json,
            "metadata": response.metadata,
            "quality": {
                k: {
                    "score": v.score,
                    "uncertainty_pct": v.uncertainty_pct,
                    "bias_corrected": v.bias_corrected,
                    "validation_flags": v.validation_flags,
                    "source_specific": v.source_specific,
                }
                for k, v in response.quality.items()
            },
            "fetched_at": response.fetched_at.isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/quality/{latitude}/{longitude}")
async def get_quality_info(
    latitude: float,
    longitude: float,
    start_date: str = Query(..., pattern=r"^\d{8}$"),
    end_date: str = Query(..., pattern=r"^\d{8}$"),
):
    """Get quality comparison between sources for a location."""
    try:
        service = get_weather_service()
        
        # Fetch from all available sources for comparison
        response = await service.get_weather(
            latitude=latitude,
            longitude=longitude,
            start_date=start_date,
            end_date=end_date,
            variables=["ALL"],
            strategy="cross_validate",
        )
        
        return {
            "location": {"latitude": latitude, "longitude": longitude},
            "period": f"{start_date}-{end_date}",
            "primary_source": response.source,
            "sources_used": response.metadata.get("sources_used", []),
            "validation_results": response.metadata.get("validation_results", []),
            "fusion_flags": response.metadata.get("fusion_flags", []),
            "quality": {
                k: {
                    "score": v.score,
                    "uncertainty_pct": v.uncertainty_pct,
                    "bias_corrected": v.bias_corrected,
                    "validation_flags": v.validation_flags,
                }
                for k, v in response.quality.items()
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))