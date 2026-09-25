"""에이전트 도구 8종. 모두 서비스 함수의 얇은 래퍼이며, 결정론적 계산(순위·차이·배정량)은 코드가 붙입니다. 쓰기 도구는 없습니다."""

from __future__ import annotations

import json
import re
from typing import Any

from app.db import facilities_voucher_col
from app.engine.models import Scenario
from app.services import (
    candidate_service,
    catalog_service,
    gap_service,
    scenario_service,
    supply_service,
)

TOOL_SPECS: list[dict[str, Any]] = [
    {"name": "resolve_place", "description": "지역(시도·시군구)이나 시설 이름 표현을 표준 코드·ID로 확정한다. 지역 질문이면 항상 먼저 호출. 시설은 가맹시설과 비가맹 전체 체육시설 양쪽에서 찾아 affiliated 여부를 함께 돌려준다.",
     "input_schema": {"type": "object", "properties": {"text": {"type": "string", "description": "예: '종로구', '부산 동래', '올림픽기념국민생활관수영장'"}, "kind": {"type": "string", "enum": ["region", "facility", "any"]}}, "required": ["text", "kind"], "additionalProperties": False}, "strict": True},
    {"name": "get_region_diagnosis", "description": "시군구의 공백 진단(대상자·수급률·활동 가맹시설·1,000명당·종목 수·주 종목 비율·저녁 강좌 비율·유치 후보 수·전국 순위)과 해석 문장.",
     "input_schema": {"type": "object", "properties": {"regionCode": {"type": "string", "description": "5자리 시군구 코드"}}, "required": ["regionCode"], "additionalProperties": False}, "strict": True},
    {"name": "compare_regions", "description": "최대 5개 시군구의 축별 수치와 첫째−둘째 차이(코드가 계산).",
     "input_schema": {"type": "object", "properties": {"regionCodes": {"type": "array", "items": {"type": "string"}, "maxItems": 5}}, "required": ["regionCodes"], "additionalProperties": False}, "strict": True},
    {"name": "list_supply_options", "description": "시군구의 최근 12개월 활동 가맹 강좌(시간표·월 수강료·최근 신청·AI 추출 사실과 출처 등급). 종목·시간대로 거를 수 있다.",
     "input_schema": {"type": "object", "properties": {"regionCode": {"type": "string"}, "sport": {"type": ["string", "null"]}, "eveningOnly": {"type": "boolean"}, "limit": {"type": "integer", "minimum": 1, "maximum": 30}}, "required": ["regionCode", "sport", "eveningOnly", "limit"], "additionalProperties": False}, "strict": True},
    {"name": "list_candidates", "description": "시군구의 비가맹 유치 후보(가맹 목록과 대조되지 않은 정상운영 체육시설)를 점수 규칙으로 정렬. 모두 가맹 여부 확인 필요.",
     "input_schema": {"type": "object", "properties": {"regionCode": {"type": "string"}, "sport": {"type": ["string", "null"]}, "limit": {"type": "integer", "minimum": 1, "maximum": 20}}, "required": ["regionCode", "sport", "limit"], "additionalProperties": False}, "strict": True},
    {"name": "build_scenario", "description": "수요 집단·예산으로 시나리오 JSON을 만든다. 공급 옵션은 활동 강좌에서, 조치는 유치 후보 상위에서 자동으로 채운다. 사용자가 말한 값은 반드시 해당 필드에 넣어라: 예산→budgetWon, '가맹 N만원'→affiliationCostWon, '개설 N만원'→openCourseCostWon, '개설 N석/정원 N'→openCourseCapacity, '기존 강좌 추가 정원 N석'→existingCapacity (만원 단위는 원으로 환산: 20만원=200000). 말하지 않은 값만 null. transport는 사용자가 이동 지원이 필요하다고 말한 경우에만 needs_support, 기본은 walk.",
     "input_schema": {"type": "object", "properties": {
         "regionCode": {"type": "string"}, "sport": {"type": "string"},
         "demandGroups": {"type": "array", "items": {"type": "object", "properties": {
             "label": {"type": "string"}, "size": {"type": "integer", "minimum": 1, "maximum": 500},
             "weekdays": {"type": "array", "items": {"type": "integer", "minimum": 0, "maximum": 6}, "description": "월=0 … 일=6"},
             "startMinute": {"type": "integer", "minimum": 0, "maximum": 1440}, "endMinute": {"type": "integer", "minimum": 0, "maximum": 1440},
             "ageMin": {"type": ["integer", "null"]}, "ageMax": {"type": ["integer", "null"]},
             "transport": {"type": "string", "enum": ["walk", "own_vehicle", "needs_support"], "description": "기본 walk. 사용자가 차량·이동 지원을 언급한 경우에만 own_vehicle/needs_support"}}, "required": ["label", "size", "weekdays", "startMinute", "endMinute", "ageMin", "ageMax", "transport"], "additionalProperties": False}, "maxItems": 10},
         "budgetWon": {"type": ["integer", "null"]},
         "affiliationCostWon": {"type": ["integer", "null"], "description": "사용자가 말한 가맹 협의 비용(없으면 null)"},
         "openCourseCostWon": {"type": ["integer", "null"]}, "openCourseCapacity": {"type": ["integer", "null"]},
         "existingCapacity": {"type": ["integer", "null"], "description": "사용자가 말한 기존 강좌 추가 정원(없으면 null)"}},
      "required": ["regionCode", "sport", "demandGroups", "budgetWon", "affiliationCostWon", "openCourseCostWon", "openCourseCapacity", "existingCapacity"], "additionalProperties": False}, "strict": True},
    {"name": "run_simulation", "description": "build_scenario가 만든 시나리오로 조치 조합을 전부 평가한다. 현재 상태·예산 내 최선 조합·탐욕 비교·결합 효과·막힌 제약·미확인 항목을 코드가 계산해 돌려준다.",
     "input_schema": {"type": "object", "properties": {"scenarioJson": {"type": "string"}}, "required": ["scenarioJson"], "additionalProperties": False}, "strict": True},
    {"name": "get_provenance", "description": "데이터 버전·기준일·출처 등급 정의를 돌려준다.",
     "input_schema": {"type": "object", "properties": {}, "required": [], "additionalProperties": False}, "strict": True},
]

CORE_TOOLS = {t["name"] for t in TOOL_SPECS}

# OpenAI Responses API 함수 도구 형태 (strict: 모든 속성 required, additionalProperties false)
OPENAI_TOOLS = [{"type": "function", "name": t["name"], "description": t["description"], "parameters": t["input_schema"], "strict": True} for t in TOOL_SPECS]


def _num(v):
    return v


async def resolve_place(text: str, kind: str = "any") -> dict:
    v = await catalog_service.require_version()
    t = re.sub(r"\s+", "", text)
    out: dict = {"input": text, "regions": [], "facilities": []}
    if kind in ("region", "any"):
        rows = await catalog_service.region_options(v)
        exact, partial = [], []
        for r in rows:
            full = (r["sidoName"] + r["sigunguName"]).replace(" ", "")
            if t == r["sigunguName"] or t == full or t == r["sidoName"][:2] + r["sigunguName"]:
                exact.append(r)
            elif t in full or r["sigunguName"] in t or (len(t) >= 2 and t[:2] == r["sidoName"][:2] and r["sigunguName"][:-1] in t):
                partial.append(r)
        hits = exact or partial
        out["regions"] = [{"regionCode": r["regionCode"], "name": f"{r['sidoName']} {r['sigunguName']}"} for r in hits[:8]]
        out["regionResolution"] = "exact" if exact else ("partial" if partial else "none")
    if kind in ("facility", "any") and len(t) >= 2:
        from app.db import facilities_all_col
        rx = {"$regex": re.escape(text.strip()), "$options": "i"}
        async for f in facilities_voucher_col.find({"datasetVersion": v, "name": rx}, {"name": 1, "address": 1, "regionCode": 1, "sports": 1}).limit(5):
            out["facilities"].append({"facilityId": f["_id"], "name": f["name"], "address": f.get("address"), "regionCode": f.get("regionCode"), "sports": f.get("sports"),
                                      "affiliated": True, "note": "이용권 가맹시설 목록에 있음"})
        async for f in facilities_all_col.find({"datasetVersion": v, "name": rx, "voucherMatch": None}, {"name": 1, "address": 1, "regionCode": 1, "category": 1, "status": 1, "childSuitability": 1}).limit(5):
            out["facilities"].append({"facilityId": f["_id"], "name": f["name"], "address": f.get("address"), "regionCode": f.get("regionCode"), "category": f.get("category"),
                                      "status": f.get("status"), "affiliated": None, "note": "전체 체육시설 목록에만 있음 — 가맹 목록과 대조되지 않음(가맹 여부 확인 필요)"})
    if not out["regions"] and not out["facilities"]:
        out["note"] = "일치하는 지역·시설이 없습니다. 데이터에 없는 지역이거나 표기가 다릅니다."
    return out


async def get_region_diagnosis(regionCode: str) -> dict:
    v = await catalog_service.require_version()
    d = await gap_service.region_detail(v, regionCode[:5])
    r = d["region"]
    return {"region": r, "axes": [{k: a[k] for k in ("key", "label", "desc", "value", "rankNational", "regionTotal", "computable")} for a in d["axes"]],
            "sportCounts": d["sportCounts"][:8], "interpretation": d["interpretation"],
            "provenance_summary": {"public": len(d["axes"])}, "unresolved": [n for n in (r.get("notComputable") or [])] + ["유치 후보의 가맹 여부는 확인 필요"],
            "datasetVersion": v, "dataMaxMonth": r.get("dataMaxMonth")}


async def compare_regions(regionCodes: list[str]) -> dict:
    v = await catalog_service.require_version()
    d = await gap_service.compare_regions(v, [c[:5] for c in regionCodes][:5])
    return {**d, "provenance_summary": {"public": len(d["regions"])}, "unresolved": []}


async def list_supply_options(regionCode: str, sport: str | None, eveningOnly: bool, limit: int) -> dict:
    v = await catalog_service.require_version()
    meta = await catalog_service.metadata()
    courses = await supply_service.list_courses(v, regionCode[:5], sport or None, True, meta.get("activeCutoffMonth"), max(limit, 30), with_facts=True)
    if eveningOnly:
        courses = [c for c in courses if any(s["startMinute"] >= 18 * 60 for s in c.get("sessions", []))]
    items = []
    prov = {"public": 0, "llm_extracted": 0, "llm_reviewed": 0}
    for c in courses[:limit]:
        fx = c.get("facts") or {}
        p = fx.get("provenance")
        if p in prov:
            prov[p] += 1
        prov["public"] += 1
        items.append({"courseId": c["courseId"], "name": c["name"], "facility": c["facilityName"], "sport": c["sport"],
                      "sessions": c.get("sessions", []), "scheduleAmbiguous": c.get("scheduleAmbiguous"), "priceWon": c.get("priceWon"),
                      "lastMonth": c.get("lastMonth"), "lastApplicants": c.get("lastApplicants"),
                      "facts": ({"age_min": fx.get("age_min"), "age_max": fx.get("age_max"), "attendance_rule": fx.get("attendance_rule"), "provenance": p} if fx else None)})
    return {"count": len(courses), "items": items, "cutoff": meta.get("activeCutoffMonth"), "provenance_summary": prov,
            "unresolved": ["정원은 공공데이터에 없음(확인 필요)", "AI추출·미검토 값은 진단에 쓰지 않음"] if items else ["활동 강좌 없음"]}


async def list_candidates(regionCode: str, sport: str | None, limit: int) -> dict:
    v = await catalog_service.require_version()
    d = await candidate_service.list_candidates(v, regionCode[:5], sport or None, None, True, False, False, None, limit, 0)
    items = [{"facilityId": f["facilityId"], "name": f["name"], "address": f.get("address"), "category": f.get("category"), "score": f["score"],
              "reasons": f["scoreReasons"], "safetyGrade": (f.get("safety") or {}).get("grade"), "walkSec": (f.get("transit") or {}).get("minWalkSec"),
              "needsConfirmation": f["needsConfirmation"]} for f in d["items"]]
    return {"total": d["total"], "items": items, "scoreRules": [r["desc"] for r in d["scoreRules"]], "provenance_summary": {"public": len(items), "rule": len(items)},
            "unresolved": ["모든 후보의 가맹 여부·아동 강좌 운영 가능 여부는 확인 필요"]}


async def build_scenario(regionCode: str, sport: str, demandGroups: list[dict], budgetWon, affiliationCostWon, openCourseCostWon, openCourseCapacity, existingCapacity) -> dict:
    v = await catalog_service.require_version()
    meta = await catalog_service.metadata()
    opts = await scenario_service.build_supply_options(v, regionCode[:5], sport, meta.get("activeCutoffMonth"), 10)
    cands = await scenario_service.build_candidate_actions(v, regionCode[:5], sport, 3)
    groups = []
    for i, g in enumerate(demandGroups[:10], 1):
        groups.append({"id": f"d{i}", "label": g["label"], "sport": sport, "size": g["size"],
                       "availability": [{"weekday": w, "startMinute": g["startMinute"], "endMinute": g["endMinute"]} for w in g["weekdays"]],
                       "ageMin": g.get("ageMin"), "ageMax": g.get("ageMax"), "bufferMinutes": 0, "transport": g.get("transport", "walk"), "provenance": "confirmed"})
    for o in opts:
        o.pop("meta", None)
        if existingCapacity is not None:
            o["capacity"] = existingCapacity
            o["capacityProvenance"] = "confirmed"
    actions = []
    # 신설 슬롯의 시간표는 아직 없으므로, 첫 수요 집단의 가용시간을 '계획 시간표'(가정)로 넣습니다.
    planned = []
    if groups:
        g0 = groups[0]
        for w in g0["availability"]:
            planned.append({"weekday": w["weekday"], "startMinute": w["startMinute"], "endMinute": min(w["endMinute"], w["startMinute"] + 60)})
    for c in cands:
        so = c["supplyOption"]
        so["sessions"] = planned
        so["attendanceRule"] = "all_required"
        so["provenance"] = "assumed"
        opts.append(so)
        a1, a2 = c["actions"]
        if affiliationCostWon is not None:
            a1["costWon"], a1["costProvenance"] = affiliationCostWon, "assumed"
        if openCourseCostWon is not None:
            a2["costWon"], a2["costProvenance"] = openCourseCostWon, "assumed"
        if openCourseCapacity is not None:
            a2["capacity"] = openCourseCapacity
        actions += [a1, a2]
    sc = {"id": "agent", "title": f"{sport} 수요 {sum(g['size'] for g in groups)}명", "regionCode": regionCode[:5], "sport": sport,
          "demandGroups": groups, "supplyOptions": opts, "actions": actions[:10], "budgetWon": budgetWon,
          "mode": "capacity" if (openCourseCapacity is not None or existingCapacity is not None) else "structure", "datasetVersion": v}
    model = Scenario.model_validate(sc)
    val = scenario_service.validate(model)
    return {"scenarioJson": model.model_dump_json(), "validation": val, "summary": {"groups": len(groups), "supplyOptions": len(opts), "actions": len(actions[:10]), "mode": sc["mode"]},
            "provenance_summary": val["provenanceSummary"], "unresolved": [u["text"] for u in val["unresolved"]],
            "note": "모드가 structure면 정원이 없어 사람 수 배정 대신 연결 가능 집단 수만 계산합니다. 신설 슬롯의 시간표는 첫 수요 집단의 가용시간에 맞춘 계획값(가정)입니다."}


async def run_simulation(scenarioJson: str) -> dict:
    sc = Scenario.model_validate_json(scenarioJson)
    r = scenario_service.run_compare(sc)
    L = r["labels"]
    def brief(b):
        if not b:
            return None
        return {"actions": [f"{a} {L['actions'].get(a, '')}" for a in b["actions"]], "assigned": b.get("assigned"), "connectedGroups": b.get("connectedGroups"),
                "costWon": b["costWon"], "overBudget": b.get("overBudget"), "budgetUndetermined": b.get("budgetUndetermined"), "assumptionDependent": b.get("assumptionDependent")}
    blocked = [{"group": L["groups"].get(x["groupId"]), "option": L["options"].get(x["optionId"]), "reasons": x["labels"]} for x in r["baseline"]["blocked"][:12]]
    return {"mode": r["mode"], "objective": r["objective"], "baseline": brief(r["baseline"]), "best": brief(r["best"]),
            "greedy": {"actions": r["greedy"]["actions"], "objective": r["greedy"]["objective"], "costWon": r["greedy"]["costWon"]},
            "synergy": r["synergy"], "evaluated": r["evaluated"], "topBundles": [brief(b) for b in r["bundles"][:5]], "blockedBaseline": blocked,
            "provenance_summary": r["validation"]["provenanceSummary"], "unresolved": [u["text"] for u in r["validation"]["unresolved"]],
            "note": "assigned는 입력 조건과 가정하의 모델상 배정 가능 인원이며 실제 참여·성과가 아닙니다."}


async def get_provenance() -> dict:
    meta = await catalog_service.metadata()
    return {"datasetVersion": meta["datasetVersion"], "dataMaxMonth": meta["dataMaxMonth"], "activeCutoffMonth": meta["activeCutoffMonth"],
            "grades": {"public": "공공데이터 원본", "rule": "코드 규칙", "llm_extracted": "AI 추출·미검토", "llm_reviewed": "AI 추출·검토완료", "confirmed": "담당자 확인", "assumed": "가정"},
            "files": [f["name"] for f in meta["files"]], "provenance_summary": {"public": 1}, "unresolved": []}


DISPATCH = {"resolve_place": resolve_place, "get_region_diagnosis": get_region_diagnosis, "compare_regions": compare_regions,
            "list_supply_options": list_supply_options, "list_candidates": list_candidates, "build_scenario": build_scenario,
            "run_simulation": run_simulation, "get_provenance": get_provenance}


async def dispatch(name: str, args: dict) -> Any:
    fn = DISPATCH.get(name)
    if fn is None:
        return {"error": f"알 수 없는 도구: {name}"}
    return await fn(**args)


def serialize_result(result: Any, max_chars: int = 12_000) -> str:
    from app.core.serialize import jsonable
    text = json.dumps(jsonable(result), ensure_ascii=False, default=str)
    if len(text) <= max_chars:
        return text
    head = int(max_chars * 0.7)
    return text[:head] + f"\n...({len(text) - max_chars:,}자 생략)...\n" + text[-(max_chars - head):]
