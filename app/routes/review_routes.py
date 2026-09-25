from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.core.serialize import jsonable
from app.services import catalog_service, review_service

router = APIRouter(prefix="/api/review", tags=["review"])


@router.get("")
async def list_items(status: str = Query("pending", max_length=20), kind: str | None = Query(None, max_length=20), limit: int = Query(50, ge=1, le=200)):
    return jsonable({"items": await review_service.list_items(status, kind, limit), "counts": await review_service.counts()})


class DecideBody(BaseModel):
    decision: str = Field(pattern="^(approve|reject)$")
    reviewer: str = Field(default="담당자", max_length=40)
    edits: dict = Field(default_factory=dict)


@router.post("/{item_id}")
async def decide(item_id: str, body: DecideBody):
    res = await review_service.decide(item_id, body.decision, body.reviewer, body.edits)
    v = await catalog_service.active_version()
    if v:
        await review_service.refresh_child_age_share(v)
    return res
