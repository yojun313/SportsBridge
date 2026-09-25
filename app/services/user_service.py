"""이용자용 추천: 조건에 맞는 이용권 강좌·무료 공공 공간을 찾고, 조건 변경 제안과 '수요 신호' 등록을 다룹니다.

담당자용과 같은 엔진 규칙(시간 완전 포함, 여유시간, 출석 규칙, 연령)을 쓰되 개인 조건 하나에 대해 강좌를 하나씩 판정합니다.
개인 조건은 저장하지 않고, 이용자가 명시적으로 '수요 등록'을 눌렀을 때만 익명 집계용 신호(지역·종목·요일·시간대·연령대)를 저장합니다.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from app.db import (
    course_facts_col,
    courses_col,
    demand_signals_col,
    facilities_all_col,
    facilities_voucher_col,
    votes_col,
)
from app.engine.constraints import age_ok, time_ok
from app.engine.models import DemandGroup, Session, SupplyOption, TimeWindow

DOW = "월화수목금토일"
REASON_KO = {
    "sport:mismatch": "종목 불일치", "time:unknown_schedule": "시간표 미확인", "time:required_days_conflict": "필수 출석 요일이 가용시간과 충돌",
    "time:attendance_rule_unknown": "출석 규칙 미확인(전 요일 필수로 가정하면 불일치)", "time:not_enough_selectable_days": "가용 요일이 주당 횟수보다 적음",
    "age:out_of_range": "대상 연령 불일치", "price:over_budget": "월 수강료가 예산 초과", "inactive": "최근 12개월 이용 기록 없음",
}
FLAG_KO = {"attendance_unknown": "출석 규칙 미확인", "age_unknown": "대상 연령 미확인", "price_unknown": "수강료 미확인", "schedule_ambiguous": "시간표 후보가 여럿(모호)", "recent_low": "최근 신청 인원 적음(운영 확인 권장)"}


def _group(profile: dict) -> DemandGroup:
    return DemandGroup(id="me", label="나", sport=profile.get("sports", ["*"])[0] if profile.get("sports") else "*", size=1,
                       availability=[TimeWindow(**w) for w in profile.get("availability", [])],
                       sessionsPerWeek=profile.get("sessionsPerWeek"), ageMin=profile.get("age"), ageMax=profile.get("age"),
                       bufferMinutes=profile.get("bufferMinutes", 0), transport=profile.get("transport", "walk"))


def judge_course(profile: dict, c: dict, facts: dict | None) -> dict:
    """한 강좌 판정 → {status: match|needs_confirmation|mismatch, reasons, flags}."""
    reasons, flags = [], []
    sports = profile.get("sports") or []
    if sports and c["sport"] not in sports:
        reasons.append("sport:mismatch")
    reviewed = bool(facts) and facts.get("provenance") == "llm_reviewed"
    att = facts.get("attendance_rule") if reviewed and facts else "unknown"
    opt = SupplyOption(id=c["courseId"], label=c["name"], facilityId=c["facilityId"], sport=c["sport"],
                       sessions=[Session(**s) for s in c.get("sessions", [])], attendanceRule=att or "unknown",
                       ageMin=facts.get("age_min") if reviewed and facts else None, ageMax=facts.get("age_max") if reviewed and facts else None)
    g = _group(profile)
    ok, why = time_ok(g, opt)
    if not ok:
        if why == "time:attendance_rule_unknown":
            # 미확인 규칙: 일부 요일만 맞으면 '확인 필요'로 두고, 하나도 안 맞으면 불일치
            fits = [any(w.weekday == s.weekday and w.startMinute <= s.startMinute - g.bufferMinutes and s.endMinute + g.bufferMinutes <= w.endMinute for w in g.availability) for s in opt.sessions]
            if any(fits):
                flags.append("attendance_unknown")
            else:
                reasons.append("time:required_days_conflict")
        else:
            reasons.append(why)
    elif att == "unknown" and opt.sessions and g.availability:
        flags.append("attendance_unknown")
    if c.get("scheduleAmbiguous"):
        flags.append("schedule_ambiguous")
    if profile.get("age") is not None:
        if opt.ageMin is None and opt.ageMax is None:
            flags.append("age_unknown")
        else:
            ok, why = age_ok(g, opt)
            if not ok:
                reasons.append(why)
    budget = profile.get("monthlyBudgetWon")
    if budget is not None:
        if c.get("priceWon") is None:
            flags.append("price_unknown")
        elif c["priceWon"] > budget:
            reasons.append("price:over_budget")
    if (c.get("lastApplicants") or 0) == 0:
        flags.append("recent_low")
    status = "mismatch" if reasons else ("needs_confirmation" if flags else "match")
    return {"status": status, "reasons": reasons, "reasonLabels": [REASON_KO.get(r, r) for r in reasons], "flags": flags, "flagLabels": [FLAG_KO.get(f, f) for f in flags]}


async def _load_courses(version: str, region_code: str, cutoff: str | None) -> list[dict]:
    q: dict = {"datasetVersion": version, "regionCode": region_code}
    if cutoff:
        q["lastMonth"] = {"$gte": cutoff}
    docs = []
    async for c in courses_col.find(q, {"datasetVersion": 0, "nameNorm": 0, "description": 0}):
        c["courseId"] = c.pop("_id")
        c["months"] = (c.get("months") or [])[-6:]
        docs.append(c)
    ids = [d["courseId"] for d in docs]
    facts = {}
    async for f in course_facts_col.find({"datasetVersion": version, "courseId": {"$in": ids}}, {"_id": 0}):
        facts[f["courseId"]] = f
    fids = list({d["facilityId"] for d in docs})
    fac = {}
    async for f in facilities_voucher_col.find({"_id": {"$in": fids}}, {"name": 1, "address": 1, "tel": 1, "transit": 1, "location": 1, "allMatch": 1}):
        fac[f["_id"]] = f
    safety = {}
    aids = [f["allMatch"]["allFacilityId"] for f in fac.values() if f.get("allMatch") and f["allMatch"].get("allFacilityId")]
    async for a in facilities_all_col.find({"_id": {"$in": aids}}, {"safety": 1, "indoor": 1}):
        safety[a["_id"]] = a
    for d in docs:
        d["facts"] = facts.get(d["courseId"])
        f = fac.get(d["facilityId"]) or {}
        d["facility"] = {"name": f.get("name", d.get("facilityName")), "address": f.get("address"), "tel": f.get("tel"), "transit": f.get("transit"), "location": f.get("location")}
        am = (f.get("allMatch") or {}).get("allFacilityId")
        d["facility"]["safety"] = (safety.get(am) or {}).get("safety") if am else None
        d["facility"]["indoor"] = (safety.get(am) or {}).get("indoor") if am else None
    return docs


def _rank_key(c: dict, j: dict, profile: dict):
    order = {"match": 0, "needs_confirmation": 1, "mismatch": 2}
    sports = profile.get("sports") or []
    pref = sports.index(c["sport"]) if c["sport"] in sports else 9
    walk = ((c["facility"].get("transit") or {}).get("minWalkSec") or 9999)
    return (order[j["status"]], len(j["flags"]), pref, c.get("priceWon") or 10**9, walk, -(c.get("lastApplicants") or 0), c["courseId"])


async def recommend(version: str, profile: dict, cutoff: str | None, limit: int = 30) -> dict:
    region = profile["regionCode"]
    courses = await _load_courses(version, region, cutoff)
    judged = []
    for c in courses:
        j = judge_course(profile, c, c.get("facts"))
        judged.append((c, j))
    judged.sort(key=lambda cj: _rank_key(cj[0], cj[1], profile))
    matched = [_card(c, j) for c, j in judged if j["status"] == "match"][:limit]
    confirm = [_card(c, j) for c, j in judged if j["status"] == "needs_confirmation"][:limit]
    mismatch = [_card(c, j) for c, j in judged if j["status"] == "mismatch"][:limit]
    counts = {"match": sum(1 for _, j in judged if j["status"] == "match"), "needs_confirmation": sum(1 for _, j in judged if j["status"] == "needs_confirmation"),
              "mismatch": sum(1 for _, j in judged if j["status"] == "mismatch"), "total": len(judged)}
    relax = _relaxations(profile, courses, counts["match"] + counts["needs_confirmation"]) if counts["total"] else []
    signals = await demand_summary(region, profile.get("sports") or [])
    return {"counts": counts, "matched": matched, "needsConfirmation": confirm, "mismatched": mismatch, "relaxations": relax, "demandSignals": signals}


def _card(c: dict, j: dict) -> dict:
    fx = c.get("facts") or {}
    return {"courseId": c["courseId"], "name": c["name"], "sport": c["sport"], "sessions": c.get("sessions", []), "scheduleAmbiguous": c.get("scheduleAmbiguous"),
            "priceWon": c.get("priceWon"), "lastMonth": c.get("lastMonth"), "lastApplicants": c.get("lastApplicants"), "monthCount": c.get("monthCount"),
            "facility": c["facility"], "facilityId": c["facilityId"],
            "facts": ({"age_min": fx.get("age_min"), "age_max": fx.get("age_max"), "attendance_rule": fx.get("attendance_rule"), "provenance": fx.get("provenance")} if fx else None),
            **j}


def _count_ok(profile: dict, courses: list[dict]) -> int:
    return sum(1 for c in courses if judge_course(profile, c, c.get("facts"))["status"] != "mismatch")


def _relaxations(profile: dict, courses: list[dict], base: int) -> list[dict]:
    out = []
    avail = profile.get("availability") or []
    def with_(**kw):
        p = dict(profile); p.update(kw); return p
    cands = []
    for d, label in ((5, "토요일 09~18시 추가"), (6, "일요일 09~18시 추가")):
        if not any(w["weekday"] == d for w in avail):
            cands.append((label, "availability", with_(availability=avail + [{"weekday": d, "startMinute": 540, "endMinute": 1080}])))
    if avail:
        cands.append(("각 가용시간을 앞뒤 1시간씩 확장", "availability", with_(availability=[{**w, "startMinute": max(0, w["startMinute"] - 60), "endMinute": min(1440, w["endMinute"] + 60)} for w in avail])))
        cands.append(("평일 저녁 18~21시 추가", "availability", with_(availability=avail + [{"weekday": d, "startMinute": 1080, "endMinute": 1260} for d in range(5) if not any(w["weekday"] == d and w["endMinute"] >= 1260 for w in avail)])))
    if profile.get("monthlyBudgetWon") is not None:
        for add in (10000, 30000, 50000):
            cands.append((f"월 예산 {add:,}원 상향", "monthlyBudgetWon", with_(monthlyBudgetWon=profile["monthlyBudgetWon"] + add)))
    if profile.get("bufferMinutes", 0) > 0:
        cands.append(("이동·준비 여유 없이 계산", "bufferMinutes", with_(bufferMinutes=0)))
    if profile.get("sports"):
        others = {}
        for c in courses:
            if c["sport"] not in profile["sports"]:
                others[c["sport"]] = others.get(c["sport"], 0) + 1
        for sp, _ in sorted(others.items(), key=lambda kv: -kv[1])[:3]:
            cands.append((f"종목에 '{sp}' 추가", "sports", with_(sports=profile["sports"] + [sp])))
    for label, field, p in cands:
        n = _count_ok(p, courses)
        if n > base:
            out.append({"label": label, "field": field, "before": base, "after": n, "gain": n - base, "profile": p})
    out.sort(key=lambda r: -r["gain"])
    return out[:6]


# ---- 개방학교·공공 공간 (일반 이용자용 무료 공간)
_OPEN_RE = re.compile(r"([월화수목금토일])요일\s*:\s*(\d{1,2}):(\d{2})\s*[~-]\s*(\d{1,2}):(\d{2})")


def parse_open_hours(text: str) -> list[dict]:
    out = []
    for m in _OPEN_RE.finditer(text or ""):
        d = DOW.index(m.group(1))
        s = int(m.group(2)) * 60 + int(m.group(3))
        e = int(m.group(4)) * 60 + int(m.group(5))
        if e > s:
            out.append({"weekday": d, "startMinute": s, "endMinute": e})
    return out


async def open_spaces(version: str, profile: dict, limit: int = 20) -> list[dict]:
    """개방학교 체육시설 중 가용시간과 겹치는 곳. 학교 개방은 이용권과 무관한 무료·저가 공간입니다."""
    avail = [TimeWindow(**w) for w in profile.get("availability", [])]
    out = []
    async for f in facilities_all_col.find({"datasetVersion": version, "regionCode": profile["regionCode"], "sources": "open_schools"}, {"nameNorm": 0, "addressNorm": 0}):
        hours = parse_open_hours(f.get("openHours") or "")
        overlap = []
        for h in hours:
            for w in avail:
                if w.weekday == h["weekday"] and max(w.startMinute, h["startMinute"]) < min(w.endMinute, h["endMinute"]):
                    overlap.append({"weekday": h["weekday"], "startMinute": max(w.startMinute, h["startMinute"]), "endMinute": min(w.endMinute, h["endMinute"])})
        if avail and not overlap:
            continue
        out.append({"facilityId": f["_id"], "name": f["name"], "address": f.get("address"), "items": f.get("openItems"), "hours": hours, "overlap": overlap,
                    "showers": f.get("showers"), "lockers": f.get("lockers"), "baseYear": f.get("sourceAsOf"), "period": f.get("openPeriod")})
        if len(out) >= limit:
            break
    return out


# ---- 수요 신호(익명) · 가맹 요청 투표
def _band(age: int | None) -> str:
    if age is None:
        return "unknown"
    if age <= 12:
        return "child"
    if age <= 18:
        return "teen"
    if age <= 64:
        return "adult"
    return "senior"


async def register_demand(version: str, profile: dict, note: str = "") -> dict:
    doc = {"datasetVersion": version, "regionCode": profile["regionCode"], "sports": profile.get("sports") or [], "sport": (profile.get("sports") or ["기타종목"])[0],
           "availability": profile.get("availability", []), "ageBand": _band(profile.get("age")), "userType": profile.get("userType", "general"),
           "monthlyBudgetWon": profile.get("monthlyBudgetWon"), "transport": profile.get("transport", "walk"), "note": (note or "")[:200],
           "createdAt": datetime.now(UTC)}
    await demand_signals_col.insert_one(doc)
    return {"ok": True, "summary": await demand_summary(profile["regionCode"], doc["sports"])}


async def demand_summary(region_code: str, sports: list[str]) -> dict:
    total = await demand_signals_col.count_documents({"regionCode": region_code})
    same = await demand_signals_col.count_documents({"regionCode": region_code, "sports": {"$in": sports}}) if sports else 0
    by_sport = []
    async for d in demand_signals_col.aggregate([{"$match": {"regionCode": region_code}}, {"$group": {"_id": "$sport", "n": {"$sum": 1}}}, {"$sort": {"n": -1}}, {"$limit": 8}]):
        by_sport.append({"sport": d["_id"], "count": d["n"]})
    return {"total": total, "sameSport": same, "bySport": by_sport}


async def demand_groups_for_scenario(region_code: str, sport: str | None) -> list[dict]:
    """등록된 수요 신호를 (종목·요일집합·시간대)로 묶어 시나리오 수요 집단 초기값으로."""
    q: dict = {"regionCode": region_code}
    if sport:
        q["sports"] = sport
    groups: dict[tuple, dict] = {}
    async for d in demand_signals_col.find(q):
        sp = sport or d["sport"]
        days = tuple(sorted({w["weekday"] for w in d.get("availability", [])}))
        if d.get("availability"):
            start = min(w["startMinute"] for w in d["availability"]); end = max(w["endMinute"] for w in d["availability"])
        else:
            start, end = 0, 1440
        key = (sp, days, start // 60, end // 60)
        g = groups.setdefault(key, {"sport": sp, "days": days, "start": (start // 60) * 60, "end": min(1440, (end // 60) * 60 + (60 if end % 60 else 0)), "size": 0, "ageBands": {}})
        g["size"] += 1
        g["ageBands"][d.get("ageBand", "unknown")] = g["ageBands"].get(d.get("ageBand", "unknown"), 0) + 1
    out = []
    for i, g in enumerate(sorted(groups.values(), key=lambda x: -x["size"]), 1):
        label = f"등록 수요 {i} · {g['sport']} " + ("".join(DOW[d] for d in g["days"]) if g["days"] else "요일무관") + f" {g['start']//60:02d}~{g['end']//60:02d}시"
        out.append({"id": f"sig{i}", "label": label, "sport": g["sport"], "size": g["size"],
                    "availability": [{"weekday": d, "startMinute": g["start"], "endMinute": g["end"]} for d in g["days"]],
                    "sessionsPerWeek": None, "bufferMinutes": 0, "transport": "walk", "provenance": "confirmed", "ageBands": g["ageBands"], "source": "demand_signals"})
    return out[:10]


async def vote_facility(version: str, facility_id: str, region_code: str, sport: str | None) -> dict:
    f = await facilities_all_col.find_one({"_id": facility_id, "datasetVersion": version}, {"regionCode": 1, "name": 1})
    if not f:
        return {"ok": False, "detail": "시설을 찾을 수 없습니다"}
    await votes_col.insert_one({"facilityId": facility_id, "regionCode": f["regionCode"], "sport": sport, "createdAt": datetime.now(UTC)})
    n = await votes_col.count_documents({"facilityId": facility_id})
    return {"ok": True, "facilityId": facility_id, "name": f["name"], "votes": n}


async def votes_by_facility(region_code: str) -> dict[str, int]:
    out = {}
    async for d in votes_col.aggregate([{"$match": {"regionCode": region_code}}, {"$group": {"_id": "$facilityId", "n": {"$sum": 1}}}]):
        out[d["_id"]] = d["n"]
    return out


async def nearby_candidates_for_user(version: str, region_code: str, sports: list[str], limit: int = 8) -> list[dict]:
    """이용자에게 '이 시설이 가맹되면 다니겠다'고 표시할 비가맹 후보(아동 적합·정상운영·안전 양호 우선)."""
    from app.services import candidate_service
    sport = sports[0] if sports else None
    data = await candidate_service.list_candidates(version, region_code, sport, None, False, False, False, None, limit, 0)
    votes = await votes_by_facility(region_code)
    out = []
    for f in data["items"]:
        out.append({"facilityId": f["facilityId"], "name": f["name"], "address": f.get("address"), "category": f.get("category"), "sportGuess": f.get("sportGuess"),
                    "safety": (f.get("safety") or {}).get("grade"), "walkSec": (f.get("transit") or {}).get("minWalkSec"), "votes": votes.get(f["facilityId"], 0)})
    return out


async def region_signal_overview(region_code: str) -> dict:
    """담당자 화면용: 지역의 등록 수요·가맹 요청 투표 요약."""
    sig = await demand_summary(region_code, [])
    votes = await votes_by_facility(region_code)
    top = sorted(votes.items(), key=lambda kv: -kv[1])[:5]
    names = {}
    if top:
        async for f in facilities_all_col.find({"_id": {"$in": [t[0] for t in top]}}, {"name": 1}):
            names[f["_id"]] = f["name"]
    return {"demand": sig, "votes": [{"facilityId": k, "name": names.get(k, k), "votes": v} for k, v in top], "voteTotal": sum(votes.values())}
