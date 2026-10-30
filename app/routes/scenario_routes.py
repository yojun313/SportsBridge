from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.serialize import jsonable
from app.engine.models import Scenario
from app.services import catalog_service, scenario_service

router = APIRouter(prefix="/api/scenarios", tags=["scenario"])


@router.get("/presets")
async def presets(
    region: str = Query("11110", min_length=5, max_length=5),
    sport: str = Query("수영", min_length=1, max_length=40),
):
    from app.services.scenario_presets import build_presets

    version = await catalog_service.require_version()
    meta = await catalog_service.metadata()
    return jsonable(
        await build_presets(version, meta.get("activeCutoffMonth") or "", region, sport)
    )


@router.get("/supply")
async def supply(
    region: str = Query(..., min_length=5, max_length=5),
    sport: str = Query(..., min_length=1, max_length=40),
    limit: int = Query(20, ge=1, le=30),
):
    v = await catalog_service.require_version()
    meta = await catalog_service.metadata()
    options = await scenario_service.build_supply_options(
        v, region, sport, meta.get("activeCutoffMonth"), limit
    )
    candidates = await scenario_service.build_candidate_actions(v, region, sport, 5)
    from app.services.user_service import demand_groups_for_scenario

    signals = await demand_groups_for_scenario(region, sport)
    return jsonable(
        {
            "datasetVersion": v,
            "supplyOptions": options,
            "candidateActions": candidates,
            "demandGroups": signals,
            "cutoff": meta.get("activeCutoffMonth"),
        }
    )


@router.post("/validate")
async def validate(sc: Scenario):
    return jsonable(scenario_service.validate(sc))


@router.post("/compare")
async def compare(sc: Scenario):
    v = scenario_service.validate(sc)
    if not v["ok"]:
        raise HTTPException(status_code=422, detail={"problems": v["problems"]})
    return jsonable(scenario_service.run_compare(sc))


class EvalBody(BaseModel):
    scenario: Scenario
    selected: list[str] = Field(default_factory=list, max_length=10)


@router.post("/evaluate")
async def evaluate(body: EvalBody):
    return jsonable(scenario_service.run_evaluate(body.scenario, body.selected))


class PlanBody(BaseModel):
    scenario: Scenario
    selected: list[str] = Field(default_factory=list, max_length=10)


@router.post("/plan-draft")
async def plan_draft(body: PlanBody):
    """LLM 없이 결정적 템플릿으로 만드는 협의 계획서 초안 + 근거 JSON."""
    from app.db import region_stats_col
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
    draft = document_service.template_plan(facts)
    return jsonable(
        {
            "facts": facts,
            "draft": draft,
            "source": "template",
            "guard": document_service.verify_numbers_and_names(draft, facts),
        }
    )
