"""비가맹 후보 조회: 전체 체육시설 중 가맹 목록과 대조되지 않은 시설. 점수 규칙은 공개됩니다."""

from __future__ import annotations

import csv
import io
import re

from app.db import facilities_all_col, gap_aggregates_col, match_results_col

SCORE_RULES = [
    {
        "key": "suitability",
        "label": "아동 강좌 업종 적합성",
        "desc": "아동 강좌 적합 업종 +3, 적합성 미확인 +1, 가능성 낮은 업종은 기본 제외",
        "help": "공개 체육시설의 업종·시설 유형을 미리 정한 분류표와 비교합니다. 수영장·태권도장처럼 아동 강좌에 적합하다고 분류한 업종과 판단하기 어려운 업종을 구분합니다. 시설이 실제로 아동 강좌를 운영하는지 확인한 결과나 가맹 승인 기준은 아닙니다.",
        "conditions": [
            {
                "label": "적합 업종",
                "points": "+3",
                "help": "시설의 업종·유형이 아동 강좌 적합 업종으로 분류되면 3점을 더합니다. 분류는 공개 자료와 업종 대응 규칙을 기준으로 하며, 실제 아동 대상 강좌·강사·수용 정원을 확인한 결과는 아닙니다. 이 기준에서는 미확인 업종 가점과 중복 가산하지 않습니다.",
            },
            {
                "label": "적합성 미확인",
                "points": "+1",
                "help": "업종 정보만으로 아동 강좌 적합성을 판단하기 어려운 경우 1점을 더합니다. 화면의 ‘적합성 미확인 업종 포함’을 선택한 경우에만 목록에 포함됩니다. 부적합이 확인됐거나 실제 강좌 운영 가능성이 검증됐다는 의미는 아닙니다.",
            },
            {
                "label": "가능성 낮은 업종",
                "points": "0",
                "help": "당구장·골프 등 규칙상 아동 강좌 가능성이 낮은 업종은 기본 목록에서 제외합니다. 해당 업종 포함 옵션을 선택하면 후보로 볼 수 있지만 이 적합성 기준의 가점은 없습니다. 다른 기준의 가점·감점은 적용되며 실제 수업 가능 여부는 시설에 확인해야 합니다.",
            },
        ],
    },
    {
        "key": "sportMatch",
        "label": "검토 종목 일치",
        "desc": "검토 종목과 업종 추정 종목 일치 +3",
        "help": "담당자가 선택한 검토 종목과 시설의 업종·유형으로 추정한 종목을 비교합니다. 이 선택은 종목이 다른 시설을 모두 제외하는 필터가 아니라 일치하는 후보에 가점을 주는 기준입니다. 종목을 선택하지 않으면 이 가점은 적용하지 않습니다.",
        "conditions": [
            {
                "label": "추정 종목과 일치",
                "points": "+3",
                "help": "검토 종목을 선택했고 시설의 업종 기반 추정 종목과 정확히 같으면 3점을 더합니다. 예를 들어 수영을 선택하고 시설의 추정 종목도 수영이면 해당합니다. 실제 수영 강좌나 잔여석이 확인됐다는 뜻은 아니며, 미선택·불일치·추정 종목 미확인은 0점입니다.",
            },
        ],
    },
    {
        "key": "safety",
        "label": "안전점검 기록",
        "desc": "양호 +2, 그 외 점검 기록 +1, 주의·수리필요·사용중지 −3, 기록 미확인 0",
        "help": "시설의 지역·이름·주소를 정리해 안전점검 자료와 연결하고, 연결된 기록 중 가장 최근 점검 결과를 참고합니다. 아래 조건 중 하나만 적용합니다. 과거 공개 점검 기록이며, 현재 안전 상태를 확인하거나 시설 이용의 안전성을 보장하는 점수는 아닙니다.",
        "conditions": [
            {
                "label": "양호",
                "points": "+2",
                "help": "시설에 연결된 안전점검 등급이 ‘양호’이면 2점을 더합니다. 연결된 과거 점검 결과를 반영하는 것으로 현재 시설 상태를 실시간 확인하지 않습니다. ‘그 외 점검 기록’ 1점은 함께 더하지 않으며 실제 점검일과 현재 운영 상태를 확인해야 합니다.",
            },
            {
                "label": "그 외 점검 기록",
                "points": "+1",
                "help": "연결된 안전점검 기록이 있지만 등급이 ‘양호’도 아니고 ‘주의·수리필요·사용중지’에도 해당하지 않으면 1점을 더합니다. 등급이 비어 있는 기록도 이 경우에 포함됩니다. 기록 자체가 없으면 0점이며, 이 1점은 안전 양호를 판정한 결과가 아닙니다.",
            },
            {
                "label": "주의·수리필요·사용중지",
                "points": "−3",
                "help": "연결된 점검 등급이 ‘주의’, ‘수리필요’, ‘사용중지’ 중 하나면 3점을 뺍니다. 점검 기록 존재에 대한 1점은 별도로 더하지 않습니다. 해당 기록 이후 개선됐을 수 있으므로 점검일과 현재 상태를 확인해야 하며, 이 표시만으로 현재 영업 중단을 단정하지 않습니다.",
            },
            {
                "label": "기록 미확인",
                "points": "0",
                "help": "이 시설에 연결된 안전점검 기록이 없으면 안전 항목에 점수를 더하거나 빼지 않습니다. 시설이 위험하거나 점검을 한 번도 받지 않았다는 뜻은 아닙니다. 원본 누락이나 시설 이름·주소 차이로 기록이 연결되지 않았을 수 있습니다.",
            },
        ],
    },
    {
        "key": "transit",
        "label": "정류장 접근성",
        "desc": "도보 5분 이내 +2, 5분 초과~10분 이내 +1, 그 외 0",
        "help": "공개 교통 자료에 연결된 정류장 중 가장 짧은 도보시간을 사용합니다. 점수는 초 단위 원본값으로 계산하고 화면의 분 표시는 반올림합니다. 자료가 연결된 시설에만 적용하며 이용자의 출발지에서 시설까지의 이동 경로나 실제 소요시간을 계산한 값은 아닙니다.",
        "conditions": [
            {
                "label": "도보 5분 이내",
                "points": "+2",
                "help": "연결된 정류장의 최소 도보시간이 300초 이하이면 2점을 더합니다. 300초도 포함하며, 10분 이내 가점 1점은 중복해서 더하지 않습니다. 표시된 분은 반올림값이므로 점수 판단은 원본 초 단위 값과 다르게 보일 수 있습니다.",
            },
            {
                "label": "5분 초과~10분 이내",
                "points": "+1",
                "help": "최소 도보시간이 300초를 초과하고 600초 이하이면 1점을 더합니다. 600초도 포함합니다. 예를 들어 301초는 화면에 5분으로 반올림될 수 있지만 점수는 이 구간의 1점을 적용하며, 10분 초과나 자료 미확인은 0점입니다.",
            },
        ],
    },
    {
        "key": "indoor",
        "label": "실내 여부",
        "desc": "실내 +1",
        "help": "공개 시설 자료의 실내 여부를 참고합니다. 자료가 ‘실내’로 표시된 경우에만 가점을 주며, 시설명만 보고 실내로 추정하지 않습니다. 실외나 미확인에 대한 감점은 없습니다.",
        "conditions": [
            {
                "label": "자료에 실내로 표시",
                "points": "+1",
                "help": "시설의 실내 여부 값이 ‘실내’이면 1점을 더합니다. 실외이거나 해당 정보가 없으면 0점입니다. 건물 내 일부 시설만 실내일 수도 있으므로 실제 강좌 공간과 운영 환경은 시설에 확인해야 합니다.",
            }
        ],
    },
    {
        "key": "recent",
        "label": "정보 갱신 시점",
        "desc": "정보 갱신일이 2025년 이후 +1",
        "help": "시설 자료의 정보 갱신 연도를 기준으로 합니다. 현재 구현에서는 2025년을 고정 기준으로 사용하며 오늘 날짜에서 최근 1년을 계산하는 방식은 아닙니다. 정보 갱신은 실제 시설 개업일·강좌 개설일과 다릅니다.",
        "conditions": [
            {
                "label": "갱신 연도 2025년 이상",
                "points": "+1",
                "help": "시설 정보 갱신일의 연도가 2025년 또는 그 이후이면 1점을 더합니다. 2024년 이전이나 갱신일 미확인은 0점입니다. 이 가점만으로 현재 모집·영업·가맹 상태가 최신이라고 판단하지 말고 원본 기준일과 시설 안내를 확인해야 합니다.",
            }
        ],
    },
    {
        "key": "votes",
        "label": "시설 이용 희망",
        "desc": "시설 이용 희망 등록 1건당 +1, 최대 +3",
        "help": "이 서비스에 등록된 시설 이용 희망 건수를 공개 자료의 기본 점수에 더합니다. 시설별 누적 등록이며 실제 수강 신청·가맹 신청·대기 인원과 다릅니다. 등록 건수가 많더라도 이 항목만으로 우선순위가 과도하게 바뀌지 않도록 가점을 제한합니다.",
        "conditions": [
            {
                "label": "등록 1건당 1점",
                "points": "최대 +3",
                "help": "시설 이용 희망 등록이 1건이면 1점, 2건이면 2점, 3건 이상이면 3점을 더합니다. 10건을 등록해도 이 항목의 가점은 3점입니다. 반복 등록이 포함될 수 있어 고유 이용자 수로 읽으면 안 되며, 희망 종목이나 공개 강좌 집계기간과 무관한 시설별 누적 건수를 사용합니다.",
            }
        ],
    },
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
