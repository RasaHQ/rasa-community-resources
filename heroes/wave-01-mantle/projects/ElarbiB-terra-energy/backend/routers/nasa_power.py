from fastapi import APIRouter, HTTPException

from models.schemas import SiteRequest
from services.nasa_client import fetch_power_data, fetch_solar_data, fetch_wind_data

router = APIRouter(prefix="/api/nasa", tags=["NASA POWER"])


@router.get("/point")
async def get_power_point(
    latitude: float,
    longitude: float,
    start: str,
    end: str,
    resolution: str = "daily",
    params: str = "ALLSKY_SFC_SW_DWN,WS2M,WS50M,T2M",
):
    try:
        data = await fetch_power_data(latitude, longitude, start, end, resolution, params)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/solar")
async def get_solar(
    latitude: float,
    longitude: float,
    start: str,
    end: str,
    resolution: str = "daily",
):
    try:
        return await fetch_solar_data(latitude, longitude, start, end, resolution)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/wind")
async def get_wind(
    latitude: float,
    longitude: float,
    start: str,
    end: str,
    resolution: str = "daily",
):
    try:
        return await fetch_wind_data(latitude, longitude, start, end, resolution)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
