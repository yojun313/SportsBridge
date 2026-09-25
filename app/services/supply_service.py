"""공급 옵션 조회: 가맹 강좌(시간표·가격·활동성·AI 추출 사실)와 가맹시설."""

from __future__ import annotations

from app.db import course_facts_col, courses_col, facilities_voucher_col


async def list_courses(version: str, region_code: str, sport: str | None = None, active_only: bool = True,
                       cutoff: str | None = None, limit: int = 300, with_facts: bool = True) -> list[dict]:
    q: dict = {"datasetVersion": version, "regionCode": region_code}
    if sport:
        q["sport"] = sport
    if active_only and cutoff:
        q["lastMonth"] = {"$gte": cutoff}
    docs = []
    async for c in courses_col.find(q, {"datasetVersion": 0, "nameNorm": 0}).sort([("lastMonth", -1), ("lastApplicants", -1)]).limit(limit):
        c["courseId"] = c.pop("_id")
        c["months"] = c.get("months", [])[-12:]
        docs.append(c)
    if with_facts and docs:
        ids = [d["courseId"] for d in docs]
        facts = {}
        async for f in course_facts_col.find({"datasetVersion": version, "courseId": {"$in": ids}}, {"_id": 0}):
            facts[f["courseId"]] = f
        for d in docs:
            d["facts"] = facts.get(d["courseId"])
    return docs


async def get_course(version: str, course_id: str) -> dict | None:
    c = await courses_col.find_one({"datasetVersion": version, "_id": course_id}, {"datasetVersion": 0})
    if not c:
        return None
    c["courseId"] = c.pop("_id")
    c["facts"] = await course_facts_col.find_one({"datasetVersion": version, "courseId": course_id}, {"_id": 0})
    f = await facilities_voucher_col.find_one({"_id": c["facilityId"]}, {"datasetVersion": 0, "nameNorm": 0, "addressNorm": 0})
    if f:
        f["facilityId"] = f.pop("_id")
    c["facility"] = f
    return c


async def get_facility(version: str, facility_id: str) -> dict | None:
    f = await facilities_voucher_col.find_one({"datasetVersion": version, "_id": facility_id}, {"nameNorm": 0, "addressNorm": 0})
    if not f:
        return None
    f["facilityId"] = f.pop("_id")
    f["courses"] = []
    async for c in courses_col.find({"datasetVersion": version, "facilityId": facility_id}, {"_id": 1, "name": 1, "sport": 1, "sessions": 1, "priceWon": 1, "lastMonth": 1, "lastApplicants": 1}).sort("lastMonth", -1).limit(50):
        c["courseId"] = c.pop("_id")
        f["courses"].append(c)
    return f


async def sports_in_region(version: str, region_code: str, cutoff: str | None) -> list[dict]:
    pipeline = [{"$match": {"datasetVersion": version, "regionCode": region_code, **({"lastMonth": {"$gte": cutoff}} if cutoff else {})}},
                {"$group": {"_id": "$sport", "n": {"$sum": 1}}}, {"$sort": {"n": -1}}]
    return [{"sport": d["_id"], "count": d["n"]} async for d in courses_col.aggregate(pipeline)]
