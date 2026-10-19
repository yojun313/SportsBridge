from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.serialize import jsonable
from app.engine.models import TimeWindow
from app.services import catalog_service, user_service

router = APIRouter(prefix="/api/user", tags=["user"])


class Profile(BaseModel):
    regionCode: str = Field(min_length=5, max_length=5)
    userType: str = Field(default="general", pattern="^(youth_voucher|disability_voucher|general)$")
    sports: list[str] = Field(default_factory=list, max_length=3)
    age: int | None = Field(default=None, ge=3, le=100)
    availability: list[TimeWindow] = Field(default_factory=list, max_length=56)
    sessionsPerWeek: int | None = Field(default=None, ge=1, le=7)
    bufferMinutes: int = Field(default=0, ge=0, le=120)
    monthlyBudgetWon: int | None = Field(default=None, ge=0, le=5_000_000)
    transport: str = Field(default="walk", pattern="^(walk|own_vehicle|needs_support)$")


@router.post("/recommend")
async def recommend(profile: Profile):
    v = await catalog_service.require_version()
    meta = await catalog_service.metadata()
    p = profile.model_dump()
    res = await user_service.recommend(v, p, meta.get("activeCutoffMonth"))
    res["openSpaces"] = await user_service.open_spaces(v, p)
    res["nearbyCandidates"] = await user_service.nearby_candidates_for_user(
        v, p["regionCode"], p["sports"]
    )
    res["cutoff"] = meta.get("activeCutoffMonth")
    res["datasetVersion"] = v
    return jsonable(res)


class DemandBody(BaseModel):
    profile: Profile
    note: str = Field(default="", max_length=200)


@router.post("/demand")
async def demand(body: DemandBody):
    v = await catalog_service.require_version()
    return jsonable(await user_service.register_demand(v, body.profile.model_dump(), body.note))


class VoteBody(BaseModel):
    facilityId: str = Field(min_length=3, max_length=60)
    regionCode: str = Field(min_length=5, max_length=5)
    sport: str | None = Field(default=None, max_length=40)


@router.post("/vote")
async def vote(body: VoteBody):
    v = await catalog_service.require_version()
    res = await user_service.vote_facility(v, body.facilityId, body.regionCode, body.sport)
    if not res.get("ok"):
        raise HTTPException(404, res.get("detail", "실패"))
    return res


@router.get("/signals/{region_code}")
async def signals(region_code: str):
    return jsonable(await user_service.region_signal_overview(region_code[:5]))


@router.get("/region/{region_code}")
async def region_overview(region_code: str):
    """이용자용 내 동네 요약: 진단 수치를 쉬운 말로 + 시설·강좌·이용자 신호."""
    from app.services import gap_service

    v = await catalog_service.require_version()
    d = await gap_service.region_detail(v, region_code[:5])
    r = d["region"]
    plain = []
    if r.get("activeFacilityCount") is not None:
        plain.append(
            f"최근 1년 안에 이용권 강좌가 열린 시설이 {r['activeFacilityCount']}곳, 강좌는 {r['activeCourseCount']}개입니다."
        )
    if r.get("topSport"):
        plain.append(
            f"가장 많은 종목은 {r['topSport']}({round((r.get('topSportShare') or 0) * 100)}%)이고, 종목은 모두 {r['sportCount']}가지입니다."
        )
    if r.get("eveningShare") is not None:
        plain.append(
            f"18시 이후에 시작하는 강좌는 {round(r['eveningShare'] * 100)}%, 주말에 있는 강좌는 {round((r.get('weekendShare') or 0) * 100)}%입니다."
        )
    if r.get("rankFacilitiesPer1000"):
        plain.append(
            f"이용권 대상자 수에 비해 시설이 적은 순으로 전국 {r['regionTotal']}개 시군구 중 {r['rankFacilitiesPer1000']}번째입니다."
        )
    if r.get("candidateLikelyCount"):
        plain.append(
            f"아직 가맹하지 않은 것으로 보이는 체육시설이 {r['candidateLikelyCount']}곳 있어, 가맹 요청을 남길 수 있습니다."
        )
    return jsonable(
        {
            "datasetVersion": v,
            "region": r,
            "plain": plain,
            "sportCounts": d["sportCounts"],
            "hourBins": d["hourBins"],
            "dowCounts": d["dowCounts"],
            "facilities": d["facilities"][:60],
            "signals": d.get("signals"),
        }
    )


@router.get("/facilities")
async def facilities(
    region: str = Query(..., min_length=5, max_length=5),
    sport: str | None = Query(None, max_length=40),
    q: str | None = Query(None, max_length=60),
    active_only: bool = True,
    evening: bool = False,
    limit: int = Query(60, ge=1, le=200),
):
    from app.db import courses_col, facilities_voucher_col

    v = await catalog_service.require_version()
    meta = await catalog_service.metadata()
    cutoff = meta.get("activeCutoffMonth") or ""
    query: dict = {"datasetVersion": v, "regionCode": region}
    if sport:
        query["sports"] = sport
    if q:
        query["name"] = {"$regex": q, "$options": "i"}
    if active_only:
        query["usage.lastMonth"] = {"$gte": cutoff}
    items = []
    async for f in (
        facilities_voucher_col.find(
            query, {"nameNorm": 0, "addressNorm": 0, "telNorm": 0, "datasetVersion": 0}
        )
        .sort("usage.last12mApplicants", -1)
        .limit(limit * 2)
    ):
        f["facilityId"] = f.pop("_id")
        items.append(f)
    ids = [f["facilityId"] for f in items]
    counts: dict[str, dict] = {}
    async for c in courses_col.find(
        {"datasetVersion": v, "facilityId": {"$in": ids}, "lastMonth": {"$gte": cutoff}},
        {"facilityId": 1, "sessions": 1, "sport": 1, "priceWon": 1},
    ):
        d = counts.setdefault(
            c["facilityId"],
            {"courses": 0, "evening": 0, "weekend": 0, "minPrice": None, "sports": set()},
        )
        d["courses"] += 1
        d["sports"].add(c["sport"])
        if any(s["startMinute"] >= 1080 for s in c.get("sessions", [])):
            d["evening"] += 1
        if any(s["weekday"] >= 5 for s in c.get("sessions", [])):
            d["weekend"] += 1
        if c.get("priceWon") is not None:
            d["minPrice"] = (
                c["priceWon"] if d["minPrice"] is None else min(d["minPrice"], c["priceWon"])
            )
    out = []
    for f in items:
        cs = counts.get(
            f["facilityId"],
            {"courses": 0, "evening": 0, "weekend": 0, "minPrice": None, "sports": set()},
        )
        if evening and not cs["evening"]:
            continue
        f["activeCourses"] = cs["courses"]
        f["eveningCourses"] = cs["evening"]
        f["weekendCourses"] = cs["weekend"]
        f["minPrice"] = cs["minPrice"]
        f["activeSports"] = sorted(cs["sports"])
        out.append(f)
        if len(out) >= limit:
            break
    return jsonable({"datasetVersion": v, "items": out, "cutoff": cutoff})


@router.get("/spaces")
async def spaces(
    region: str = Query(..., min_length=5, max_length=5),
    weekday: int | None = Query(None, ge=0, le=6),
    start: int | None = Query(None, ge=0, le=1440),
    end: int | None = Query(None, ge=0, le=1440),
    limit: int = Query(60, ge=1, le=200),
):
    """무료·공공 공간: 개방학교(운영시간 있음) + 공공체육시설(운영시간 없음, 위치·유형만)."""
    from app.db import facilities_all_col

    v = await catalog_service.require_version()
    prof = {
        "regionCode": region,
        "availability": (
            [{"weekday": weekday, "startMinute": start, "endMinute": end}]
            if weekday is not None and start is not None and end is not None and end > start
            else []
        ),
    }
    schools = await user_service.open_spaces(v, prof, limit)
    public = []
    async for f in facilities_all_col.find(
        {
            "datasetVersion": v,
            "regionCode": region,
            "flag": "공공",
            "status": "정상운영",
            "deleted": {"$ne": True},
        },
        {
            "name": 1,
            "address": 1,
            "category": 1,
            "facilityType": 1,
            "transit": 1,
            "safety": 1,
            "area": 1,
            "owner": 1,
            "department": 1,
            "tel": 1,
            "voucherMatch": 1,
        },
    ).limit(limit):
        f["facilityId"] = f.pop("_id")
        public.append(f)
    return jsonable({"datasetVersion": v, "schools": schools, "public": public})


@router.get("/voice/{region_code}")
async def voice(region_code: str):
    from app.db import demand_signals_col

    overview = await user_service.region_signal_overview(region_code[:5])
    by_slot: dict[str, int] = {}
    async for d in demand_signals_col.find(
        {"regionCode": region_code[:5]}, {"availability": 1, "sport": 1}
    ):
        for w in d.get("availability", []):
            key = f"{w['weekday']}:{(w['startMinute'] // 60)}"
            by_slot[key] = by_slot.get(key, 0) + 1
    cands = await user_service.nearby_candidates_for_user(
        await catalog_service.require_version(), region_code[:5], [], 12
    )
    return jsonable({**overview, "bySlot": by_slot, "candidates": cands})
