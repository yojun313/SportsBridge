from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config import LLM_ENABLED
from app.core.serialize import jsonable
from app.engine.models import Scenario
from app.services import catalog_service, scenario_service

router = APIRouter(prefix="/api/llm", tags=["llm"])


def _require_llm():
    if not LLM_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="LLM 기능이 비활성입니다. .env에 OPENAI_API_KEY와 LLM_ENABLED=true를 설정하세요.",
        )


class PlanBody(BaseModel):
    scenario: Scenario
    selected: list[str] = Field(default_factory=list, max_length=10)


@router.post("/plan-doc")
async def plan_doc(body: PlanBody):
    _require_llm()
    from app.db import region_stats_col
    from app.llm import client as llm
    from app.llm.documents import draft_plan_document
    from app.services import document_service

    v = await catalog_service.active_version()
    ev = scenario_service.run_evaluate(body.scenario, body.selected)
    r = (
        await region_stats_col.find_one(
            {"datasetVersion": v, "regionCode": body.scenario.regionCode},
            {"_id": 0, "sidoName": 1, "sigunguName": 1},
        )
        if v
        else None
    )
    region_name = f"{r['sidoName']} {r['sigunguName']}" if r else body.scenario.regionCode
    facts = document_service.build_facts(body.scenario, body.selected, ev, region_name, v)
    try:
        res = await draft_plan_document(facts)
    except llm.BudgetExceeded as e:
        raise HTTPException(429, str(e))
    if not res["ok"]:
        raise HTTPException(422, "초안 생성 실패: " + "; ".join(res["problems"]))
    return jsonable(
        {
            "facts": facts,
            "draft": res["draft"],
            "source": "llm",
            "guard": [],
            "costUsd": res["costUsd"],
        }
    )


class ExtractBody(BaseModel):
    courseId: str = Field(min_length=1, max_length=60)


@router.post("/extract-course")
async def extract_course(body: ExtractBody):
    """단건 온라인 추출(시연·검토용). 대량은 scripts/llm_extract_courses.py."""
    _require_llm()
    import asyncio

    from app.db import course_facts_col, courses_col
    from app.llm import client as llm
    from app.llm.extract import extract_course_sync
    from app.services import review_service

    v = await catalog_service.require_version()
    c = await courses_col.find_one(
        {"datasetVersion": v, "_id": body.courseId}, {"name": 1, "description": 1}
    )
    if not c:
        raise HTTPException(404, "강좌를 찾을 수 없습니다")
    try:
        doc = await asyncio.to_thread(
            extract_course_sync, body.courseId, c["name"], c.get("description") or ""
        )
    except llm.BudgetExceeded as e:
        raise HTTPException(429, str(e))
    doc["datasetVersion"] = v
    await course_facts_col.update_one(
        {"datasetVersion": v, "courseId": body.courseId}, {"$set": doc}, upsert=True
    )
    if doc["needsReview"]:
        await review_service.enqueue(
            "extraction",
            body.courseId,
            {
                "courseName": c["name"],
                "description": c.get("description") or "",
                "facts": {
                    k: doc[k]
                    for k in (
                        "age_min",
                        "age_max",
                        "grade_hint",
                        "level",
                        "attendance_rule",
                        "sessions_per_week",
                        "shuttle",
                        "voucher_note",
                        "evidence",
                        "confidence",
                        "flags",
                    )
                },
            },
            v,
        )
    return jsonable(doc)


@router.get("/usage")
async def usage():
    from app.llm import client as llm

    return {
        "enabled": LLM_ENABLED,
        "todaySpendUsd": round(llm.today_spend_usd(), 4),
        "dailyBudgetUsd": llm.LLM_DAILY_BUDGET_USD,
        "modelMain": llm.model_main(),
        "modelBulk": llm.model_bulk(),
    }
