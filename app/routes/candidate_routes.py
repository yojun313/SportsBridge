from fastapi import APIRouter, Query
from fastapi.responses import Response

from app.core.serialize import jsonable
from app.services import candidate_service, catalog_service

router = APIRouter(prefix="/api/gap", tags=["candidates"])


@router.get("/{region_code}/candidates")
async def candidates(region_code: str, sport: str | None = Query(None, max_length=40), category: str | None = Query(None, max_length=60),
                     unknown: bool = True, unlikely: bool = False, safety_ok: bool = False, q: str | None = Query(None, max_length=60),
                     limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0)):
    v = await catalog_service.require_version()
    data = await candidate_service.list_candidates(v, region_code[:5], sport, category, unknown, unlikely, safety_ok, q, limit, offset)
    data["summary"] = await candidate_service.candidate_summary(v, region_code[:5])
    return jsonable({"datasetVersion": v, **data})


@router.get("/{region_code}/candidates.csv")
async def candidates_csv(region_code: str, sport: str | None = Query(None, max_length=40), category: str | None = Query(None, max_length=60),
                         unknown: bool = True, unlikely: bool = False, safety_ok: bool = False):
    v = await catalog_service.require_version()
    data = await candidate_service.list_candidates(v, region_code[:5], sport, category, unknown, unlikely, safety_ok, None, 2000, 0)
    body = candidate_service.to_csv(data["items"])
    return Response(content=body, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="candidates_{region_code[:5]}_{v}.csv"'})
