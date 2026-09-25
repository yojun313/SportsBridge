"""조치 조합 탐색. 최대 10개 조치의 부분집합(≤1024)을 전부 평가하고, 의존·배타 관계와 예산을 지킵니다.

결과 정렬: 배정량 최대 → 비용 최소 → 조치 수 최소 → 조치 ID 순(안정).
탐욕(단독 효과 순) 선택과 비교해 결합 효과 누락을 보여줍니다.
"""

from __future__ import annotations

from itertools import combinations

from app.engine.assignment import max_flow_assign
from app.engine.constraints import compatible
from app.engine.models import Scenario

TRACE_LABEL = {
    "supply:not_opened": "강좌 미개설(신설 조치 필요)",
    "sport:mismatch": "종목 불일치",
    "age:out_of_range": "대상 연령 불일치",
    "time:unknown_schedule": "시간표 미확인",
    "time:required_days_conflict": "필수 출석 요일이 가용시간과 충돌",
    "time:attendance_rule_unknown": "출석 규칙 미확인(보수적으로 전 요일 필수 적용)",
    "time:not_enough_selectable_days": "가용시간에 맞는 요일이 주당 횟수보다 적음",
    "reach:not_reachable": "이동 불가(확인됨)",
    "reach:needs_transport_support": "이동 지원 필요",
    "affiliation:not_affiliated": "비가맹 시설(가맹 조치 필요)",
    "affiliation:unknown": "가맹 여부 미확인",
    "capacity:unknown": "정원 미확인(확정 배정 제외)",
}


def evaluate(sc: Scenario, selected: set[str]) -> dict:
    """선택한 조치 집합에서의 배정 결과."""
    actions = {a.id: a for a in sc.actions}
    affiliated: set[str] = set()
    transport: set[tuple[str, str]] = set()
    opened: set[str] = set()
    cap_add: dict[str, int] = {}
    cost = 0
    unknown_cost = []
    for aid in selected:
        a = actions[aid]
        if a.costWon is None:
            unknown_cost.append(aid)
        else:
            cost += a.costWon
        if a.kind == "affiliate" and a.facilityId:
            affiliated.add(a.facilityId)
        elif a.kind == "transport" and a.demandGroupId and a.facilityId:
            transport.add((a.demandGroupId, a.facilityId))
        elif a.kind == "open_course" and a.supplyOptionId:
            opened.add(a.supplyOptionId)
            if a.capacity is not None:
                cap_add[a.supplyOptionId] = cap_add.get(a.supplyOptionId, 0) + a.capacity
        elif a.kind == "add_capacity" and a.supplyOptionId and a.capacity is not None:
            cap_add[a.supplyOptionId] = cap_add.get(a.supplyOptionId, 0) + a.capacity

    edges: set[tuple[str, str]] = set()
    blocked: dict[tuple[str, str], list[str]] = {}
    options = []
    unknown_capacity = []
    for opt in sc.supplyOptions:
        exists = opt.exists or opt.id in opened
        base_cap = opt.capacity
        extra = cap_add.get(opt.id, 0)
        if base_cap is None and extra == 0:
            capacity = None
        else:
            capacity = (base_cap or 0) + extra
        if sc.mode == "structure":
            capacity = 10**6 if exists else None  # 구조 탐색: 정원을 보지 않고 연결 가능성만
        options.append((opt.id, capacity))
        if capacity is None and exists:
            unknown_capacity.append(opt.id)
        for g in sc.demandGroups:
            ok, reasons = compatible(g, opt, affiliated, transport, exists)
            if ok and capacity is None:
                ok, reasons = False, ["capacity:unknown"]
            if ok:
                edges.add((g.id, opt.id))
            else:
                blocked[(g.id, opt.id)] = reasons
    groups = [(g.id, g.size) for g in sc.demandGroups]
    flow, assigned = max_flow_assign(groups, options, edges)
    per_group = {}
    for g in sc.demandGroups:
        got = sum(v for (gid, _), v in assigned.items() if gid == g.id)
        per_group[g.id] = {"size": g.size, "assigned": got, "unmet": g.size - got,
                           "connectedOptions": sorted(o for (gid, o) in edges if gid == g.id)}
    connected_types = sum(1 for g in sc.demandGroups if per_group[g.id]["connectedOptions"])
    return {
        "actions": sorted(selected), "assigned": flow if sc.mode == "capacity" else None,
        "connectedGroups": connected_types, "totalDemand": sum(g.size for g in sc.demandGroups),
        "costWon": cost, "unknownCostActions": unknown_cost, "unknownCapacityOptions": unknown_capacity,
        "assignments": [{"groupId": g, "optionId": o, "count": n} for (g, o), n in sorted(assigned.items())],
        "perGroup": per_group,
        "blocked": [{"groupId": g, "optionId": o, "reasons": r, "labels": [TRACE_LABEL.get(x, x) for x in r]} for (g, o), r in sorted(blocked.items())],
    }


def feasible(sc: Scenario, selected: set[str]) -> tuple[bool, str | None]:
    actions = {a.id: a for a in sc.actions}
    for aid in selected:
        a = actions[aid]
        for r in a.requires:
            if r not in selected:
                return False, f"{aid} requires {r}"
        for c in a.conflicts:
            if c in selected:
                return False, f"{aid} conflicts {c}"
    return True, None


def compare_bundles(sc: Scenario, max_results: int = 12) -> dict:
    ids = [a.id for a in sc.actions]
    baseline = evaluate(sc, set())
    results = []
    infeasible = 0
    over_budget = 0
    for k in range(len(ids) + 1):
        for combo in combinations(ids, k):
            sel = set(combo)
            ok, _why = feasible(sc, sel)
            if not ok:
                infeasible += 1
                continue
            r = evaluate(sc, sel)
            has_unknown_cost = bool(r["unknownCostActions"])
            if sc.budgetWon is not None and (r["costWon"] > sc.budgetWon):
                over_budget += 1
                r["overBudget"] = True
            else:
                r["overBudget"] = False
            r["budgetUndetermined"] = has_unknown_cost
            r["assumptionDependent"] = _assumption_dependent(sc, sel)
            results.append(r)
    objective = (lambda r: r["assigned"] or 0) if sc.mode == "capacity" else (lambda r: r["connectedGroups"])
    within = [r for r in results if not r["overBudget"] and not r["budgetUndetermined"]]
    within.sort(key=lambda r: (-objective(r), r["costWon"], len(r["actions"]), r["actions"]))
    best = within[0] if within else None
    # 탐욕 비교: 단독 효과 큰 순으로 예산 내 추가
    greedy = _greedy(sc, ids, objective, baseline)
    # 각 조치 단독 효과
    singles = {}
    for aid in ids:
        feasible_single, _ = feasible(sc, {aid})
        singles[aid] = evaluate(sc, {aid}) if feasible_single else None
    all_sorted = sorted(results, key=lambda r: (-objective(r), r["costWon"], len(r["actions"]), r["actions"]))
    return {
        "mode": sc.mode, "objective": "assigned" if sc.mode == "capacity" else "connectedGroups",
        "baseline": baseline, "best": best, "greedy": greedy, "singles": singles,
        "bundles": all_sorted[:max_results], "evaluated": len(results), "infeasible": infeasible, "overBudget": over_budget,
        "synergy": _synergy_note(sc, singles, best, objective, baseline),
        "traceLabels": TRACE_LABEL,
    }


def _greedy(sc, ids, objective, baseline):
    chosen: set[str] = set()
    cur = baseline
    cost = 0
    steps = []
    remaining = set(ids)
    while remaining:
        best_gain, best_id, best_r = 0, None, None
        for aid in sorted(remaining):
            sel = chosen | {aid}
            ok, _ = feasible(sc, sel)
            if not ok:
                continue
            r = evaluate(sc, sel)
            if r["unknownCostActions"] or (sc.budgetWon is not None and r["costWon"] > sc.budgetWon):
                continue
            gain = objective(r) - objective(cur)
            if gain > best_gain:
                best_gain, best_id, best_r = gain, aid, r
        if best_id is None:
            break
        chosen.add(best_id)
        cur = best_r
        cost = cur["costWon"]
        steps.append({"added": best_id, "objective": objective(cur), "costWon": cost})
        remaining.discard(best_id)
    return {"actions": sorted(chosen), "objective": objective(cur), "costWon": cost, "steps": steps}


def _synergy_note(sc, singles, best, objective, baseline):
    if not best or len(best["actions"]) < 2:
        return None
    base = objective(baseline)
    single_gain = sum(max(0, objective(singles[a]) - base) for a in best["actions"] if singles.get(a))
    combo_gain = objective(best) - base
    return {"comboGain": combo_gain, "sumOfSingleGains": single_gain, "hasSynergy": combo_gain > single_gain}


def _assumption_dependent(sc: Scenario, selected: set[str]) -> list[str]:
    deps = []
    for a in sc.actions:
        if a.id in selected and (a.costProvenance == "assumed" or a.provenance == "assumed"):
            deps.append(f"action:{a.id}")
    for o in sc.supplyOptions:
        if o.capacity is not None and o.capacityProvenance == "assumed":
            deps.append(f"capacity:{o.id}")
    return deps
