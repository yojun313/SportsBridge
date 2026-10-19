from fastapi import APIRouter, Query

from app.core.serialize import jsonable
from app.services import catalog_service, gap_service, supply_service

router = APIRouter(prefix="/api/gap", tags=["gap"])


@router.get("")
async def list_gap(
    sido: str | None = Query(None, max_length=2),
    sort: str = Query("rankFacilitiesPer1000", max_length=40),
    limit: int = Query(300, ge=1, le=300),
):
    v = await catalog_service.require_version()
    return jsonable(
        {"datasetVersion": v, "regions": await gap_service.list_regions(v, sido, sort, limit)}
    )


@router.get("/compare")
async def compare(codes: str = Query(..., max_length=60)):
    v = await catalog_service.require_version()
    ids = [c.strip() for c in codes.split(",") if c.strip()][:5]
    return jsonable({"datasetVersion": v, **await gap_service.compare_regions(v, ids)})


@router.get("/{region_code}")
async def region_detail(region_code: str):
    v = await catalog_service.require_version()
    return jsonable({"datasetVersion": v, **await gap_service.region_detail(v, region_code[:5])})


@router.get("/{region_code}/courses")
async def region_courses(
    region_code: str,
    sport: str | None = Query(None, max_length=40),
    active: bool = True,
    limit: int = Query(200, ge=1, le=500),
):
    v = await catalog_service.require_version()
    meta = await catalog_service.metadata()
    courses = await supply_service.list_courses(
        v, region_code[:5], sport, active, meta.get("activeCutoffMonth"), limit
    )
    sports = await supply_service.sports_in_region(
        v, region_code[:5], meta.get("activeCutoffMonth") if active else None
    )
    return jsonable(
        {
            "datasetVersion": v,
            "courses": courses,
            "sports": sports,
            "cutoff": meta.get("activeCutoffMonth"),
        }
    )


@router.get("/{region_code}/facility/{facility_id}")
async def facility(region_code: str, facility_id: str):
    from fastapi import HTTPException

    v = await catalog_service.require_version()
    f = await supply_service.get_facility(v, facility_id)
    if not f:
        raise HTTPException(404, "시설을 찾을 수 없습니다.")
    return jsonable(f)
