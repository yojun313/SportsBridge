"""시나리오 보조: 지역 공급 옵션을 실제 데이터에서 만들어 초기값으로 제공하고, 엔진을 실행합니다.
시나리오 자체는 서버에 저장하지 않습니다(브라우저 로컬 저장)."""

from __future__ import annotations

from app.engine.bundles import compare_bundles, evaluate
from app.engine.models import Action, Scenario, Session, SupplyOption
from app.services import supply_service


async def build_supply_options(version: str, region_code: str, sport: str, cutoff: str | None, limit: int = 20) -> list[dict]:
    """활동 가맹 강좌를 공급 옵션으로. 정원은 공공 데이터에 없으므로 None(확인 필요)."""
    courses = await supply_service.list_courses(version, region_code, sport, True, cutoff, limit, with_facts=True)
    out = []
    for c in courses:
        fx = c.get("facts") or {}
        reviewed = fx.get("provenance") == "llm_reviewed"
        opt = SupplyOption(
            id=c["courseId"], label=f"{c['facilityName']} · {c['name']}", facilityId=c["facilityId"], facilityName=c["facilityName"],
            sport=c["sport"], sessions=[Session(**s) for s in c.get("sessions", [])],
            attendanceRule=(fx.get("attendance_rule") if reviewed and fx.get("attendance_rule") else "unknown"),
            ageMin=fx.get("age_min") if reviewed else None, ageMax=fx.get("age_max") if reviewed else None,
            capacity=None, capacityProvenance="assumed", voucherAffiliated=True, affiliationProvenance="public",
            priceWon=c.get("priceWon"), exists=True, provenance="public",
        )
        d = opt.model_dump()
        d["meta"] = {"lastMonth": c.get("lastMonth"), "lastApplicants": c.get("lastApplicants"), "scheduleAmbiguous": c.get("scheduleAmbiguous"),
                     "scheduleSource": c.get("scheduleSource"), "factsProvenance": fx.get("provenance")}
        out.append(d)
    return out


async def build_candidate_actions(version: str, region_code: str, sport: str, limit: int = 5) -> list[dict]:
    """후보 발굴 결과 상위 시설을 '가맹 협의 + 강좌 신설' 조치 쌍의 초기값으로."""
    from app.services import candidate_service
    data = await candidate_service.list_candidates(version, region_code, sport, None, True, False, False, None, limit, 0)
    out = []
    for i, f in enumerate(data["items"], 1):
        fid = f["facilityId"]
        opt = SupplyOption(id=f"new:{fid}", label=f"{f['name']} · 신설 {sport} 강좌", facilityId=fid, facilityName=f["name"], sport=sport,
                           sessions=[], attendanceRule="unknown", capacity=None, capacityProvenance="assumed",
                           voucherAffiliated=False, affiliationProvenance="public", exists=False, provenance="assumed")
        a1 = Action(id=f"aff{i}", label=f"{f['name']} 가맹 협의", kind="affiliate", facilityId=fid, costWon=None, costProvenance="assumed", provenance="assumed")
        a2 = Action(id=f"open{i}", label=f"{f['name']} {sport} 강좌 신설", kind="open_course", supplyOptionId=opt.id, capacity=None,
                    costWon=None, costProvenance="assumed", requires=[a1.id], provenance="assumed")
        out.append({"facility": {"facilityId": fid, "name": f["name"], "address": f.get("address"), "category": f.get("category"),
                                 "score": f["score"], "scoreReasons": f["scoreReasons"], "needsConfirmation": f["needsConfirmation"]},
                    "supplyOption": opt.model_dump(), "actions": [a1.model_dump(), a2.model_dump()]})
    return out


def validate(sc: Scenario) -> dict:
    """스키마 외 의미 검증: 참조 무결성, 출처 등급 요약, 미확인 항목."""
    problems = []
    opt_ids = {o.id for o in sc.supplyOptions}
    grp_ids = {g.id for g in sc.demandGroups}
    act_ids = {a.id for a in sc.actions}
    for a in sc.actions:
        if a.kind in ("open_course", "add_capacity") and a.supplyOptionId not in opt_ids:
            problems.append(f"조치 {a.id}: supplyOptionId '{a.supplyOptionId}'가 공급 옵션에 없습니다")
        if a.kind == "transport" and a.demandGroupId not in grp_ids:
            problems.append(f"조치 {a.id}: demandGroupId '{a.demandGroupId}'가 수요 집단에 없습니다")
        for r in a.requires + a.conflicts:
            if r not in act_ids:
                problems.append(f"조치 {a.id}: 참조 조치 '{r}'가 없습니다")
        if a.kind == "open_course" and a.capacity is None and sc.mode == "capacity":
            problems.append(f"조치 {a.id}: 신설 정원이 없어 확정 배정에서 제외됩니다(구조 탐색 모드에서는 연결 여부만 봅니다)")
    unresolved = []
    for o in sc.supplyOptions:
        if o.capacity is None and (o.exists or any(a.supplyOptionId == o.id for a in sc.actions)):
            unresolved.append({"kind": "capacity", "id": o.id, "text": f"'{o.label}' 정원 미확인"})
        if o.voucherAffiliated is None:
            unresolved.append({"kind": "affiliation", "id": o.id, "text": f"'{o.label}' 가맹 여부 미확인"})
        if not o.sessions and o.exists:
            unresolved.append({"kind": "schedule", "id": o.id, "text": f"'{o.label}' 시간표 미확인"})
        if o.attendanceRule == "unknown" and o.sessions:
            unresolved.append({"kind": "attendance", "id": o.id, "text": f"'{o.label}' 출석 규칙 미확인(전 요일 필수로 가정)"})
    for a in sc.actions:
        if a.costWon is None:
            unresolved.append({"kind": "cost", "id": a.id, "text": f"'{a.label}' 비용 미확인"})
    prov = {}
    for o in sc.supplyOptions:
        prov[o.capacityProvenance] = prov.get(o.capacityProvenance, 0) + (1 if o.capacity is not None else 0)
        prov[o.affiliationProvenance] = prov.get(o.affiliationProvenance, 0) + 1
    for a in sc.actions:
        prov[a.costProvenance] = prov.get(a.costProvenance, 0) + (1 if a.costWon is not None else 0)
    for g in sc.demandGroups:
        prov[g.provenance] = prov.get(g.provenance, 0) + 1
    return {"ok": not problems, "problems": problems, "unresolved": unresolved, "provenanceSummary": prov}


def run_compare(sc: Scenario) -> dict:
    v = validate(sc)
    result = compare_bundles(sc)
    labels = {a.id: a.label for a in sc.actions}
    olabels = {o.id: o.label for o in sc.supplyOptions}
    glabels = {g.id: g.label for g in sc.demandGroups}
    result["labels"] = {"actions": labels, "options": olabels, "groups": glabels}
    result["validation"] = v
    return result


def run_evaluate(sc: Scenario, selected: list[str]) -> dict:
    ids = {a.id for a in sc.actions}
    sel = {s for s in selected if s in ids}
    return evaluate(sc, sel)
