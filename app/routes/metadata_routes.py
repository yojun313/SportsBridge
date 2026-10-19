from fastapi import APIRouter

from app.core.serialize import jsonable
from app.db.mongo import ping
from app.services import catalog_service

router = APIRouter(tags=["metadata"])


@router.get("/api/metadata")
async def get_metadata():
    return jsonable(await catalog_service.metadata())


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/ready")
async def ready():
    from fastapi.responses import JSONResponse

    try:
        await ping()
    except Exception:  # noqa: BLE001
        return JSONResponse(status_code=503, content={"status": "db_unavailable"})
    v = await catalog_service.active_version()
    if not v:
        return JSONResponse(status_code=503, content={"status": "no_active_dataset"})
    return {"status": "ready", "datasetVersion": v}
