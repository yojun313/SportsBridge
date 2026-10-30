"""지원금 계산에 적용할 공개 강좌 검색."""

import re

from fastapi import APIRouter, Query

from app.core.serialize import jsonable
from app.db import courses_col
from app.services import catalog_service

router = APIRouter(prefix="/api/user/planner", tags=["user-planner"])


@router.get("/courses")
async def search_courses(
    region: str = Query(..., pattern=r"^\d{5}$"),
    sport: str = Query("", max_length=40),
    q: str = Query("", max_length=60),
    page: int = Query(1, ge=1, le=10000),
):
    version = await catalog_service.require_version()
    meta = await catalog_service.metadata()
    cutoff = meta.get("activeCutoffMonth")
    query = {"datasetVersion": version, "regionCode": region}
    if sport.strip():
        query["sport"] = sport.strip()
    if cutoff:
        query["lastMonth"] = {"$gte": cutoff}
    pipeline = [
        {"$match": query},
        {"$sort": {"lastMonth": -1, "_id": 1}},
        {
            "$lookup": {
                "from": "facilities_voucher",
                "localField": "facilityId",
                "foreignField": "_id",
                "pipeline": [
                    {"$match": {"datasetVersion": version}},
                    {"$project": {"name": 1, "address": 1, "tel": 1}},
                ],
                "as": "facility",
            }
        },
        {"$unwind": {"path": "$facility", "preserveNullAndEmptyArrays": True}},
    ]
    if q.strip():
        pattern = {"$regex": re.escape(q.strip()), "$options": "i"}
        pipeline.append(
            {
                "$match": {
                    "$or": [
                        {"name": pattern},
                        {"facility.name": pattern},
                        {"facilityName": pattern},
                    ]
                }
            }
        )
    pipeline.extend(
        [
            {
                "$project": {
                    "_id": 0,
                    "courseId": "$_id",
                    "name": 1,
                    "facilityId": 1,
                    "facilityName": {"$ifNull": ["$facility.name", "$facilityName"]},
                    "address": "$facility.address",
                    "tel": "$facility.tel",
                    "sport": 1,
                    "sessions": 1,
                    "priceWon": 1,
                    "lastMonth": 1,
                    "scheduleAmbiguous": 1,
                }
            },
            {
                "$facet": {
                    "items": [{"$skip": (page - 1) * 20}, {"$limit": 20}],
                    "count": [{"$count": "total"}],
                }
            },
        ]
    )
    result = (await courses_col.aggregate(pipeline).to_list(length=1))[0]
    return jsonable(
        {
            "items": result["items"],
            "total": result["count"][0]["total"] if result["count"] else 0,
            "page": page,
            "pageSize": 20,
            "cutoff": cutoff,
            "datasetVersion": version,
        }
    )
