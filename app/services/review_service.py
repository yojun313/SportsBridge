"""검토 큐: LLM 추출·매칭 판정을 사람이 승인/반려. 승인하면 provenance가 llm_reviewed로 바뀌고 진단에 반영됩니다."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException

from app.db import (
    course_facts_col,
    courses_col,
    facilities_all_col,
    match_results_col,
    review_queue_col,
)


async def enqueue(kind: str, ref_id: str, payload: dict, version: str) -> str:
    _id = f"rq:{kind}:{ref_id}"
    await review_queue_col.update_one({"_id": _id}, {"$set": {"kind": kind, "refId": ref_id, "payload": payload, "datasetVersion": version,
                                                              "status": "pending", "createdAt": datetime.now(UTC)}}, upsert=True)
    return _id


async def list_items(status: str = "pending", kind: str | None = None, limit: int = 50) -> list[dict]:
    q: dict = {"status": status}
    if kind:
        q["kind"] = kind
    out = []
    async for d in review_queue_col.find(q).sort("createdAt", -1).limit(limit):
        d["id"] = d.pop("_id")
        out.append(d)
    return out


async def counts() -> dict:
    out = {}
    async for d in review_queue_col.aggregate([{"$group": {"_id": {"k": "$kind", "s": "$status"}, "n": {"$sum": 1}}}]):
        out[f"{d['_id']['k']}:{d['_id']['s']}"] = d["n"]
    return out


async def decide(item_id: str, decision: str, reviewer: str = "담당자", edits: dict | None = None) -> dict:
    item = await review_queue_col.find_one({"_id": item_id})
    if not item:
        raise HTTPException(404, "검토 항목이 없습니다")
    if decision not in ("approve", "reject"):
        raise HTTPException(422, "decision은 approve/reject")
    now = datetime.now(UTC)
    await review_queue_col.update_one({"_id": item_id}, {"$set": {"status": "approved" if decision == "approve" else "rejected",
                                                                  "reviewedAt": now, "reviewer": reviewer, "edits": edits or {}}})
    v = item["datasetVersion"]
    if item["kind"] == "extraction":
        if decision == "approve":
            upd = {"provenance": "llm_reviewed", "reviewedAt": now, "reviewer": reviewer, "needsReview": False}
            for k in ("age_min", "age_max", "attendance_rule", "level", "shuttle", "sessions_per_week"):
                if edits and k in edits:
                    upd[k] = edits[k]
            await course_facts_col.update_one({"datasetVersion": v, "courseId": item["refId"]}, {"$set": upd})
        else:
            await course_facts_col.update_one({"datasetVersion": v, "courseId": item["refId"]}, {"$set": {"provenance": "rejected", "needsReview": False, "reviewedAt": now}})
    elif item["kind"] == "match":
        vid = item["refId"]
        aid = (edits or {}).get("allFacilityId") or item["payload"].get("allFacilityId")
        if decision == "approve" and aid:
            await match_results_col.update_one({"datasetVersion": v, "voucherFacilityId": vid},
                                               {"$set": {"allFacilityId": aid, "matchType": "llm_reviewed", "provenance": "llm_reviewed", "status": "matched", "reviewedAt": now}})
            await facilities_all_col.update_one({"datasetVersion": v, "_id": aid}, {"$set": {"voucherMatch": {"voucherFacilityId": vid, "matchType": "llm_reviewed"}}})
        else:
            await match_results_col.update_one({"datasetVersion": v, "voucherFacilityId": vid}, {"$set": {"llmVerdictRejected": True}})
    return {"ok": True, "id": item_id, "status": "approved" if decision == "approve" else "rejected"}


async def refresh_child_age_share(version: str) -> int:
    """검토 완료된 연령 정보를 시군구 집계(childAgeShare)에 반영."""
    from app.db import gap_aggregates_col
    per: dict[str, list[int]] = {}
    async for f in course_facts_col.find({"datasetVersion": version, "provenance": "llm_reviewed"}, {"courseId": 1, "age_min": 1, "age_max": 1}):
        c = await courses_col.find_one({"_id": f["courseId"]}, {"regionCode": 1})
        if not c:
            continue
        child = 1 if (f.get("age_max") is not None and f["age_max"] <= 12) or (f.get("age_min") is not None and f["age_min"] <= 12 and (f.get("age_max") or 99) <= 18) else 0
        per.setdefault(c["regionCode"], []).append(child)
    n = 0
    for code, vals in per.items():
        await gap_aggregates_col.update_one({"datasetVersion": version, "regionCode": code}, {"$set": {"childAgeShare": round(sum(vals) / len(vals), 4), "childAgeReviewed": len(vals)}})
        n += 1
    return n
