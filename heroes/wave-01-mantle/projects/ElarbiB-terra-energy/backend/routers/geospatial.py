from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.geospatial import (
    geocode,
    get_parcel,
    geojson_area_m2,
    detect_country,
    INSTALLATION_TYPES,
)

router = APIRouter(prefix="/api/geospatial", tags=["Geospatial"])


class GeocodeRequest(BaseModel):
    query: str
    country: str | None = None


class ParcelRequest(BaseModel):
    latitude: float
    longitude: float
    radius_m: float = 200.0


@router.get("/installation-types")
async def installation_types():
    return INSTALLATION_TYPES


@router.post("/geocode")
async def geocode_address(req: GeocodeRequest):
    try:
        return await geocode(req.query, country=req.country)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/parcel")
async def parcel_at_point(req: ParcelRequest):
    try:
        return await get_parcel(req.latitude, req.longitude, req.radius_m)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class PolygonRequest(BaseModel):
    coordinates: list


@router.post("/area")
async def polygon_area(req: PolygonRequest):
    """Geodesic area of a drawn polygon (WGS84 sphere, R=6378137)."""
    try:
        area = geojson_area_m2({"type": "Polygon", "coordinates": req.coordinates})
        return {"area_m2": round(area, 1), "area_ha": round(area / 10000.0, 3)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/country")
async def country_for_point(req: ParcelRequest):
    return {"country": detect_country(req.latitude, req.longitude)}
