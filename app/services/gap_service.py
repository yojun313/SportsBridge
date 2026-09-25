"""시군구 공백 진단 조회. 집계는 적재 시 만들어진 gap_aggregates를 읽고, 축별 해석 문구를 붙입니다."""

from __future__ import annotations

from fastapi import HTTPException

from app.db import courses_col, facilities_voucher_col, gap_aggregates_col, region_stats_col

AXES = [
    {"key": "quantity", "label": "양", "desc": "이용권 대상자 1,000명당 최근 12개월 활동 가맹시설 수", "field": "facilitiesPer1000Targets", "rank": "rankFacilitiesPer1000", "lowerIsWorse": True},
    {"key": "sport", "label": "종목 선택권", "desc": "최근 12개월 강좌가 있는 종목 수", "field": "sportCount", "rank": "rankSportCount", "lowerIsWorse": True},
    {"key": "time", "label": "시간 선택권", "desc": "평일 18시 이후 시작 강좌 비율", "field": "eveningShare", "rank": "rankEveningShare", "lowerIsWorse": True},
    {"key": "uptake", "label": "수급률", "desc": "대상자 대비 실제 수급 인원 비율", "field": "recipientRate", "rank": "rankRecipientRate", "lowerIsWorse": True},
]

PROJ = {"_id": 0}


async def list_regions(version: str, sido: str | None = None, sort: str = "rankFacilitiesPer1000", limit: int = 300) -> list[dict]:
    q: dict = {"datasetVersion": version}
    if sido:
        q["sidoCode"] = sido
    allowed = {"rankFacilitiesPer1000", "rankSportCount", "rankEveningShare", "rankRecipientRate", "targetsTotal", "candidateLikelyCount", "regionCode", "activeFacilityCount"}
    if sort not in allowed:
        sort = "rankFacilitiesPer1000"
    docs = []
    async for d in gap_aggregates_col.find(q, PROJ):
        docs.append(_slim(d))
    # 계산 불가(None)는 항상 뒤로. 순위 축은 오름차순(1 = 가장 공백 큼), 수량 축은 내림차순.
    desc = sort in ("targetsTotal", "candidateLikelyCount", "activeFacilityCount")
    def key(d):
        v = d.get(sort)
        if v is None:
            return (1, 0, d["regionCode"])
        return (0, -v if desc else v, d["regionCode"])
    docs.sort(key=key)
    return docs[:limit]


def _slim(d: dict) -> dict:
    keys = ["regionCode", "sidoCode", "sidoName", "sigunguName", "population", "targetsTotal", "recipientsTotal", "recipientRate",
            "voucherFacilityCount", "activeFacilityCount", "facilitiesPer1000Targets", "targetsPerActiveFacility",
            "activeCourseCount", "sportCount", "topSport", "topSportShare", "eveningShare", "weekendShare", "scheduleKnownCount",
            "candidateCount", "candidateLikelyCount", "allFacilityCount", "matchedFacilityCount", "last12mApplicants",
            "rankFacilitiesPer1000", "rankSportCount", "rankEveningShare", "rankRecipientRate",
            "rankFacilitiesPer1000InSido", "rankSportCountInSido", "regionTotal", "sidoTotal", "notComputable", "dataMaxMonth", "activeCutoffMonth"]
    return {k: d.get(k) for k in keys}


async def region_detail(version: str, region_code: str) -> dict:
    g = await gap_aggregates_col.find_one({"datasetVersion": version, "regionCode": region_code}, PROJ)
    if not g:
        raise HTTPException(status_code=404, detail="지역을 찾을 수 없습니다.")
    stats = await region_stats_col.find_one({"datasetVersion": version, "regionCode": region_code}, PROJ)
    cutoff = g.get("activeCutoffMonth") or ""
    # 시간대 분포(시작 시각 2시간 단위)·요일 분포·연령(LLM 검토 완료분)
    hour_bins = {f"{h:02d}": 0 for h in range(6, 24, 2)}
    dow = [0] * 7
    sports: dict[str, int] = {}
    facilities_active = []
    async for c in courses_col.find({"datasetVersion": version, "regionCode": region_code, "lastMonth": {"$gte": cutoff}},
                                    {"_id": 0, "sessions": 1, "sport": 1, "facilityId": 1, "name": 1, "priceWon": 1, "lastApplicants": 1}):
        sports[c["sport"]] = sports.get(c["sport"], 0) + 1
        seen_bins = set()
        for s in c.get("sessions", []):
            dow[s["weekday"]] += 1
            h = min(22, max(6, (s["startMinute"] // 120) * 2))
            seen_bins.add(f"{h:02d}")
        for b in seen_bins:
            hour_bins[b] += 1
    async for f in facilities_voucher_col.find({"datasetVersion": version, "regionCode": region_code},
                                               {"_id": 1, "name": 1, "sports": 1, "usage": 1, "transit": 1, "allMatch": 1, "address": 1}).sort("usage.last12mApplicants", -1).limit(400):
        f["facilityId"] = f.pop("_id")
        facilities_active.append(f)
    axes = []
    for a in AXES:
        val = g.get(a["field"])
        axes.append({**a, "value": val, "rankNational": g.get(a["rank"]), "regionTotal": g.get("regionTotal"),
                     "computable": val is not None})
    from app.services.user_service import region_signal_overview
    signals = await region_signal_overview(region_code)
    return {
        "region": _slim(g), "stats": stats, "axes": axes, "signals": signals,
        "sportCounts": sorted(sports.items(), key=lambda kv: -kv[1]),
        "hourBins": hour_bins, "dowCounts": dow,
        "facilities": facilities_active,
        "interpretation": interpret(g),
    }


def interpret(g: dict) -> list[str]:
    """판정 단어 없이 상대 순위와 원 수치를 문장으로. '부족·충분' 같은 절대 판정은 쓰지 않습니다."""
    out = []
    n = g.get("regionTotal") or 0
    if g.get("rankFacilitiesPer1000"):
        out.append(f"대상자 1,000명당 활동 가맹시설 수는 전국 {n}개 시군구 중 {g['rankFacilitiesPer1000']}번째로 낮습니다 (값 {g['facilitiesPer1000Targets']}).")
    if g.get("topSport") and g.get("topSportShare") is not None:
        out.append(f"최근 12개월 강좌 {g['activeCourseCount']}개 중 '{g['topSport']}'이(가) {round(g['topSportShare']*100)}%를 차지합니다. 종목 수 {g['sportCount']}개.")
    if g.get("eveningShare") is not None:
        out.append(f"시간이 확인된 강좌 {g['scheduleKnownCount']}개 중 18시 이후 시작은 {round(g['eveningShare']*100)}%, 주말 포함은 {round((g.get('weekendShare') or 0)*100)}%입니다.")
    else:
        out.append("강좌 시간 정보가 결합되지 않아 시간 선택권 축은 계산하지 않았습니다.")
    if g.get("candidateLikelyCount") is not None:
        out.append(f"가맹 목록과 대조되지 않은 정상운영 체육시설 중 아동 강좌 가능성이 높은 업종은 {g['candidateLikelyCount']}곳입니다 (가맹 여부 확인 필요).")
    return out


async def compare_regions(version: str, codes: list[str]) -> dict:
    docs = []
    async for d in gap_aggregates_col.find({"datasetVersion": version, "regionCode": {"$in": codes}}, PROJ):
        docs.append(_slim(d))
    order = {c: i for i, c in enumerate(codes)}
    docs.sort(key=lambda d: order.get(d["regionCode"], 99))
    fields = ["targetsTotal", "recipientsTotal", "recipientRate", "activeFacilityCount", "facilitiesPer1000Targets", "sportCount", "topSportShare", "eveningShare", "candidateLikelyCount"]
    diffs = {}
    if len(docs) >= 2:
        a, b = docs[0], docs[1]
        for f in fields:
            if a.get(f) is not None and b.get(f) is not None:
                diffs[f] = round(a[f] - b[f], 4)
    return {"regions": docs, "diffFirstMinusSecond": diffs, "fields": fields}
