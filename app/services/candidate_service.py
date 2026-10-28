"""비가맹 후보 조회: 전체 체육시설 중 가맹 목록과 대조되지 않은 시설. 점수 규칙은 공개됩니다."""

from __future__ import annotations

import csv
import io
import re

from app.db import facilities_all_col, gap_aggregates_col, match_results_col

SCORE_RULES = [
    {"key": "suitability", "desc": "아동 강좌 적합 업종(likely) +3, unknown +1, unlikely 제외"},
    {"key": "sportMatch", "desc": "요청 종목과 업종 추정 종목 일치 +3"},
    {
        "key": "safety",
        "desc": "안전점검 등급 양호 +2, 점검 기록 있음(등급 없음) +1, 주의·수리필요·사용중지 −3",
    },
    {"key": "transit", "desc": "정류장 도보 5분 이내 +2, 10분 이내 +1 (공공시설만 데이터 있음)"},
    {"key": "indoor", "desc": "실내 +1"},
    {"key": "recent", "desc": "정보 갱신일이 2025년 이후 +1"},
    {"key": "votes", "desc": "시설 이용 희망 등록 1건당 +1 (최대 +3)"},
]

BAD_GRADES = {"주의", "수리필요", "사용중지"}


def score(f: dict, sport: str | None) -> tuple[int, list[str]]:
    s, why = 0, []
    suit = f.get("childSuitability")
    if suit == "likely":
        s += 3
        why.append("아동 강좌 적합 업종")
    elif suit == "unknown":
        s += 1
        why.append("업종 적합성 미확인")
    if sport and f.get("sportGuess") == sport:
        s += 3
        why.append(f"종목 일치({sport})")
    sf = f.get("safety") or {}
    g = sf.get("grade")
    if g == "양호":
        s += 2
        why.append("안전점검 양호")
    elif g in BAD_GRADES:
        s -= 3
        why.append(f"안전점검 {g}")
    elif sf:
        s += 1
        why.append("안전점검 기록 있음")
    t = f.get("transit") or {}
    w = t.get("minWalkSec")
    if w is not None:
        if w <= 300:
            s += 2
            why.append("정류장 도보 5분 이내")
        elif w <= 600:
            s += 1
            why.append("정류장 도보 10분 이내")
    if f.get("indoor") == "실내":
        s += 1
        why.append("실내")
    if (f.get("updatedAt") or "")[:4] >= "2025":
        s += 1
        why.append("2025년 이후 갱신")
    return s, why


async def list_candidates(
    version: str,
    region_code: str,
    sport: str | None = None,
    category: str | None = None,
    include_unknown: bool = True,
    include_unlikely: bool = False,
    safety_ok_only: bool = False,
    q: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> dict:
    query: dict = {
        "datasetVersion": version,
        "regionCode": region_code,
        "voucherMatch": None,
        "deleted": {"$ne": True},
        "status": {"$in": ["정상운영", "개방(연도 확인 필요)"]},
    }
    suit = ["likely"]
    if include_unknown:
        suit.append("unknown")
    if include_unlikely:
        suit.append("unlikely")
    query["childSuitability"] = {"$in": suit}
    if category:
        query["category"] = category
    if q:
        query["name"] = {"$regex": re.escape(q), "$options": "i"}
    if safety_ok_only:
        query["safety.grade"] = "양호"
    from app.services.user_service import votes_by_facility

    votes = await votes_by_facility(region_code)
    docs = []
    total = 0
    async for f in facilities_all_col.find(
        query, {"datasetVersion": 0, "nameNorm": 0, "addressNorm": 0, "telNorm": 0}
    ):
        total += 1
        sc, why = score(f, sport)
        v = votes.get(f["_id"], 0)
        if v:
            sc += min(v, 3)
            why.append(f"시설 이용 희망 등록 {v}건")
        f["votes"] = v
        f["facilityId"] = f.pop("_id")
        f["score"] = sc
        f["scoreReasons"] = why
        f["needsConfirmation"] = _needs_confirmation(f)
        docs.append(f)
    docs.sort(key=lambda d: (-d["score"], d["name"]))
    # 확인 필요 목록: 가맹 목록과 애매하게 겹치는 시설(블로킹 후보에 등장)
    ambiguous_ids = set()
    async for m in match_results_col.find(
        {"datasetVersion": version, "status": "candidates"}, {"candidates.allFacilityId": 1}
    ):
        for c in m.get("candidates", []):
            ambiguous_ids.add(c["allFacilityId"])
    for d in docs:
        if d["facilityId"] in ambiguous_ids:
            d["needsConfirmation"].append("가맹시설과 이름이 유사 — 동일 시설일 수 있음")
    page = docs[offset : offset + limit]
    cats: dict[str, int] = {}
    for d in docs:
        cats[d.get("category") or ""] = cats.get(d.get("category") or "", 0) + 1
    return {
        "total": total,
        "items": page,
        "offset": offset,
        "limit": limit,
        "scoreRules": SCORE_RULES,
        "categories": sorted(cats.items(), key=lambda kv: -kv[1]),
        "ambiguousInList": sum(1 for d in docs if d["facilityId"] in ambiguous_ids),
    }


def _needs_confirmation(f: dict) -> list[str]:
    out = ["가맹 여부(공개 목록 미대조)"]
    if f.get("childSuitability") == "unknown":
        out.append("아동 강좌 운영 가능 여부")
    if not f.get("safety"):
        out.append("안전점검 기록 없음")
    if f.get("status") != "정상운영":
        out.append(f"운영 상태: {f.get('status')}")
    if not f.get("tel"):
        out.append("연락처 없음")
    return out


def to_csv(items: list[dict]) -> str:
    def safe_cell(value):
        if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
            return "'" + value
        return value

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(
        [
            "순위",
            "점수",
            "시설명",
            "업종",
            "유형",
            "추정종목",
            "아동적합성",
            "주소",
            "전화",
            "안전등급",
            "점검일",
            "정류장도보(초)",
            "실내여부",
            "운영상태",
            "점수근거",
            "확인필요",
            "출처",
        ]
    )
    for i, f in enumerate(items, 1):
        sf = f.get("safety") or {}
        t = f.get("transit") or {}
        w.writerow(
            list(
                map(
                    safe_cell,
                    [
                        i,
                        f["score"],
                        f["name"],
                        f.get("category"),
                        f.get("facilityType"),
                        f.get("sportGuess") or "",
                        f.get("childSuitability"),
                        f.get("address"),
                        f.get("tel"),
                        sf.get("grade") or "",
                        sf.get("checkDate") or "",
                        t.get("minWalkSec") or "",
                        f.get("indoor") or "",
                        f.get("status"),
                        "; ".join(f["scoreReasons"]),
                        "; ".join(f["needsConfirmation"]),
                        ", ".join(f.get("sources", [])),
                    ],
                )
            )
        )
    return "﻿" + buf.getvalue()


async def candidate_summary(version: str, region_code: str) -> dict | None:
    g = await gap_aggregates_col.find_one(
        {"datasetVersion": version, "regionCode": region_code},
        {
            "_id": 0,
            "candidateCount": 1,
            "candidateLikelyCount": 1,
            "allFacilityCount": 1,
            "matchedFacilityCount": 1,
        },
    )
    return g
