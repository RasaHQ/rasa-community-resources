from fastapi import APIRouter, HTTPException, Query, Response

from services.tile_proxy import PROVIDERS, get_tile

router = APIRouter(prefix="/api/map", tags=["Map"])


@router.get("/providers")
async def map_providers():
    return {name: {"fallback": cfg["fallback"]} for name, cfg in PROVIDERS.items()}


@router.get("/tile")
async def map_tile(
    provider: str = Query(...),
    z: int = Query(..., ge=0, le=20),
    x: int = Query(..., ge=0),
    y: int = Query(..., ge=0),
):
    """Proxy a keyless tile, swapping provider error images for a reliable fallback."""
    try:
        body, content_type, source = await get_tile(provider, z, x, y)
    except KeyError:
        raise HTTPException(status_code=400, detail=f"unknown provider: {provider}")
    except RuntimeError:
        raise HTTPException(status_code=502, detail="no tile provider available")
    if not body:
        raise HTTPException(status_code=502, detail="no tile provider available")
    return Response(
        content=body,
        media_type=content_type,
        headers={
            "Cache-Control": "public, max-age=86400, stale-while-revalidate=86400",
            "X-Tile-Provider": source,
        },
    )