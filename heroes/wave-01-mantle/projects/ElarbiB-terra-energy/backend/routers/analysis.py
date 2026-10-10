from fastapi import APIRouter, HTTPException

from models.schemas import SiteRequest, RegionCompareRequest
from services.site_scorer import full_site_analysis, compare_sites

router = APIRouter(prefix="/api/analysis", tags=["Analysis"])


@router.post("/site")
async def analyze_site(req: SiteRequest):
    try:
        result = await full_site_analysis(
            req.latitude, req.longitude,
            req.start_date, req.end_date,
            req.resolution.value,
            solar_config=req.solar_config,
            wind_config=req.wind_config,
            site_context=req.site_context,
            lang=req.lang,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compare")
async def compare(req: RegionCompareRequest):
    try:
        sites = [s.model_dump(mode='json') for s in req.sites]
        result = await compare_sites(sites, lang=sites[0].get("lang", "fr") if sites else "fr")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
