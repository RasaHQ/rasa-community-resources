from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.equipment_catalog import get_modules, get_inverters, propose_system

router = APIRouter(prefix="/api/equipment", tags=["Equipment"])


class ModulesRequest(BaseModel):
    query: str | None = None
    limit: int = 50
    min_power_w: float = 0.0


class InvertersRequest(BaseModel):
    query: str | None = None
    limit: int = 50
    min_pac_w: float = 0.0


class SizingRequest(BaseModel):
    area_m2: float
    support: str = "roof"
    module_name: str | None = None
    inverter_name: str | None = None


@router.post("/modules")
async def modules(req: ModulesRequest):
    try:
        return get_modules(limit=req.limit, query=req.query, min_power_w=req.min_power_w)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/inverters")
async def inverters(req: InvertersRequest):
    try:
        return get_inverters(limit=req.limit, query=req.query, min_pac_w=req.min_pac_w)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/propose")
async def size_system(req: SizingRequest):
    try:
        return propose_system(
            req.area_m2,
            support=req.support,
            module_name=req.module_name,
            inverter_name=req.inverter_name,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
