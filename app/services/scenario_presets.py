"""Complete examples grounded in courses from the active public dataset."""

import math

from fastapi import HTTPException

from app.db import course_facts_col, courses_col, region_stats_col
from app.engine.models import Scenario
from app.services import scenario_service


async def build_presets(version: str, cutoff: str, region: str, sport: str) -> dict:
    query = {
        "datasetVersion": version,
        "sport": sport,
        "lastMonth": {"$gte": cutoff},
        "sessions.0": {"$exists": True},
        "scheduleAmbiguous": {"$ne": True},
        "priceWon": {"$gte": 0},
    }

    async def find_pair(region_code):
        q = {**query, **({"regionCode": region_code} if region_code else {})}
        rows = (
            await courses_col.find(
                q,
                {
                    "_id": 1,
                    "name": 1,
                    "facilityId": 1,
                    "facilityName": 1,
                    "regionCode": 1,
                    "sport": 1,
                    "sessions": 1,
                    "priceWon": 1,
                    "lastMonth": 1,
                    "scheduleSource": 1,
                },
            )
            .sort([("lastMonth", -1), ("lastApplicants", -1), ("_id", 1)])
            .limit(200)
            .to_list(200)
        )
        by_region = {}
        for c in rows:
            # Leave room for the assumed 15-minute buffer and valid HTML time inputs.
            if not all(
                15 <= s["startMinute"] < s["endMinute"] <= 1410
                and s["startMinute"] % 5 == 0
                and s["endMinute"] % 5 == 0
                for s in c["sessions"]
            ):
                continue
            if len(c["sessions"]) > 14:
                continue
            bucket = by_region.setdefault(c["regionCode"], [])
            bucket.append(c)
            if len(bucket) == 2:
                return bucket
        return []

    courses = []
    for code in dict.fromkeys([region, "11110", None]):
        courses = await find_pair(code)
        if courses:
            break
    if not courses:
        raise HTTPException(
            404,
            "시간표와 수강료가 확인되는 실제 강좌 두 개를 찾지 못했습니다. 다른 종목을 선택해 주세요.",
        )
    actual_region = courses[0]["regionCode"]
    region_doc = await region_stats_col.find_one(
        {"datasetVersion": version, "regionCode": actual_region}, {"sidoName": 1, "sigunguName": 1}
    )
    region_name = (
        f"{region_doc['sidoName']} {region_doc['sigunguName']}" if region_doc else actual_region
    )
    facts = {
        f["courseId"]: f
        async for f in course_facts_col.find(
            {"datasetVersion": version, "courseId": {"$in": [c["_id"] for c in courses]}}
        )
    }

    def option(c, capacity, groups):
        fx = facts.get(c["_id"], {})
        reviewed = fx.get("provenance") == "llm_reviewed"
        minimum = fx.get("age_min") if reviewed else None
        maximum = fx.get("age_max") if reviewed else None
        assumed = ["capacity", "reachable"]
        if minimum is None:
            minimum = 3 if maximum is not None and maximum < 5 else 5
            assumed.append("ageMin")
        if maximum is None:
            maximum = max(18, minimum + 5)
            assumed.append("ageMax")
        rule = fx.get("attendance_rule") if reviewed else None
        if rule not in ("all_required", "selectable"):
            rule = "all_required"
            assumed.append("attendanceRule")
        return {
            "id": c["_id"],
            "label": f"{c['facilityName']} · {c['name']}",
            "facilityId": c["facilityId"],
            "facilityName": c["facilityName"],
            "sport": c["sport"],
            "sessions": c["sessions"],
            "attendanceRule": rule,
            "ageMin": minimum,
            "ageMax": maximum,
            "capacity": capacity,
            "capacityProvenance": "assumed",
            "voucherAffiliated": True,
            "affiliationProvenance": "public",
            "priceWon": c["priceWon"],
            "exists": True,
            "reachable": {g: True for g in groups},
            "provenance": "public",
            "meta": {
                "lastMonth": c["lastMonth"],
                "scheduleSource": c.get("scheduleSource"),
                "sourceCourseId": c["_id"],
                "sourceCourseName": c["name"],
                "datasetVersion": version,
                "assumedFields": assumed,
            },
        }

    def group(gid, size, opt):
        # Ages are an example group compatible with the source's reviewed range.
        low = max(3, opt["ageMin"])
        high = min(100, opt["ageMax"], low + 4)
        return {
            "id": gid,
            "label": f"희망 집단 {gid} · {size}명(가정)",
            "sport": opt["sport"],
            "size": size,
            "availability": [
                {
                    "weekday": s["weekday"],
                    "startMinute": math.floor((s["startMinute"] - 15) / 15) * 15,
                    "endMinute": math.ceil((s["endMinute"] + 15) / 15) * 15,
                }
                for s in opt["sessions"]
            ],
            "sessionsPerWeek": min(7, len(opt["sessions"])),
            "ageMin": low,
            "ageMax": high,
            "bufferMinutes": 15,
            "transport": "walk",
            "provenance": "assumed",
        }

    def action(aid, label, kind, cost, **extra):
        return {
            "id": aid,
            "label": label,
            "kind": kind,
            "costWon": cost,
            "costProvenance": "assumed",
            "requires": [],
            "conflicts": [],
            "provenance": "assumed",
            **extra,
        }

    items = []
    explanations = {
        "capacity": {
            "purpose": "강좌는 이용할 수 있지만 자리가 부족할 때, 정원을 늘리는 지원으로 몇 명을 더 배정할 수 있는지 비교합니다.",
            "before": "희망 인원은 12명이고 기존 강좌가 추가로 받을 수 있는 자리는 4개라고 가정합니다. 시간·연령·이동 조건은 맞지만 자리가 부족해 현재는 4명만 배정됩니다.",
            "support": "30만 원으로 이 강좌의 추가 수용 정원을 8자리 늘립니다. 기존 4자리와 합쳐 총 12자리가 됩니다. 예산은 40만 원으로 설정합니다.",
            "interpretation": "계산 결과는 4명 → 12명, 즉 8명 추가 배정입니다. 실제 잔여석이나 시설이 정원 확대에 동의했다는 뜻이 아니라, 입력한 자리를 확보할 수 있다는 가정 아래의 결과입니다.",
        },
        "transport": {
            "purpose": "강좌에 자리가 있어도 이동이 어려워 이용하지 못하는 집단에게 이동 지원을 제공했을 때의 차이를 비교합니다.",
            "before": "희망 인원은 6명이고 강좌의 추가 자리는 10개라고 가정합니다. 수업 조건은 맞지만 이 집단은 시설까지 이동할 수 없다고 입력해 현재 배정은 0명입니다.",
            "support": "15만 원의 이동 지원을 이 집단과 해당 시설에 연결합니다. 강좌 자리는 늘리지 않고 이동 제약만 해소합니다. 예산은 20만 원으로 설정합니다.",
            "interpretation": "계산 결과는 0명 → 6명입니다. 실제 셔틀 운영 여부나 이동 경로를 확인한 결과가 아니라, 이 비용으로 이동 지원을 확보한다고 가정한 비교입니다.",
        },
        "combined": {
            "purpose": "자리 부족과 이동 문제가 동시에 있는 경우, 두 지원을 함께 시행해야 효과가 생기는 상황을 비교합니다.",
            "before": "희망 인원은 8명이고 강좌의 추가 자리는 0개이며, 해당 집단의 이동도 불가능하다고 가정합니다. 현재 배정은 0명입니다.",
            "support": "정원 8자리 추가에 30만 원, 이동 지원에 15만 원을 입력합니다. 예산 50만 원 안에서 두 조치를 함께 선택할 수 있게 구성합니다.",
            "interpretation": "정원만 늘리면 이동이 막히고, 이동만 지원하면 자리가 없어 각각의 단독 배정은 0명입니다. 두 조치를 함께 선택하면 총 45만 원으로 8명을 배정합니다. 이처럼 결합해야 생기는 효과를 확인하는 입력값입니다.",
        },
        "groups": {
            "purpose": "두 실제 강좌에 각각 연결한 희망 집단을 함께 검토하면서, 어느 강좌에 자리를 얼마나 늘릴지 비교합니다.",
            "before": "첫 집단은 8명, 둘째 집단은 6명으로 가정하고 각 강좌의 추가 자리를 4개씩 입력합니다. 집단은 각자 지정한 강좌를 이용하는 조건이므로 현재는 총 8명을 배정합니다.",
            "support": "첫 강좌에는 20만 원으로 4자리, 둘째 강좌에는 10만 원으로 2자리를 추가합니다. 각 집단의 이용 가능 시간은 연결된 실제 시간표에 맞추며, 전체 예산은 35만 원입니다.",
            "interpretation": "총 30만 원으로 첫 집단 8명과 둘째 집단 6명, 합계 14명을 배정합니다. 서로 다른 강좌의 자리와 집단 조건을 함께 비교하는 방식이며 실제 희망 등록 인원을 조회한 값은 아닙니다.",
        },
    }
    definitions = [
        ("capacity", "기존 강좌 정원 추가", 400000, 4, 12, 300000),
        ("transport", "기존 강좌 이동 지원", 200000, 0, 6, 150000),
        ("combined", "정원 추가와 이동 지원", 500000, 0, 8, 450000),
        ("groups", "두 강좌의 집단별 정원 추가", 350000, 8, 14, 300000),
    ]
    for pid, label, budget, baseline, assigned, cost in definitions:
        opt = option(
            courses[0],
            4 if pid in ("capacity", "groups") else 10 if pid == "transport" else 0,
            ["d1"],
        )
        groups = [group("d1", 12 if pid == "capacity" else 6 if pid == "transport" else 8, opt)]
        options, actions = [opt], []
        if pid in ("capacity", "combined", "groups"):
            actions.append(
                action(
                    "a1",
                    "추가 수용 정원 확보(가정)",
                    "add_capacity",
                    200000 if pid == "groups" else 300000,
                    supplyOptionId=opt["id"],
                    capacity=4 if pid == "groups" else 8,
                )
            )
        if pid in ("transport", "combined"):
            groups[0]["transport"] = "needs_support"
            opt["reachable"]["d1"] = False
            actions.append(
                action(
                    "a2",
                    "강좌 이용을 위한 이동 지원(가정)",
                    "transport",
                    150000,
                    facilityId=opt["facilityId"],
                    demandGroupId="d1",
                )
            )
        if pid == "groups":
            second = option(courses[1], 4, ["d1", "d2"])
            second["reachable"]["d1"] = False
            opt["reachable"]["d2"] = False
            groups.append(group("d2", 6, second))
            options.append(second)
            actions.append(
                action(
                    "a2",
                    "두 번째 강좌 정원 2자리 추가(가정)",
                    "add_capacity",
                    100000,
                    supplyOptionId=second["id"],
                    capacity=2,
                )
            )
        scenario = {
            "id": f"preset-real-{pid}",
            "title": f"예시 입력값 · {region_name} {label}",
            "regionCode": actual_region,
            "sport": sport,
            "mode": "capacity",
            "budgetWon": budget,
            "datasetVersion": version,
            "demandGroups": groups,
            "supplyOptions": options,
            "actions": actions,
            "notes": "시설·강좌명·시간표·수강료·기록월은 공개 자료입니다. 희망 집단·추가 정원·비용·예산·이동 조건과 미확인 연령·출석 규칙은 계산 연습용 가정입니다. 현재 모집·잔여석은 확인하지 않습니다.",
        }
        model = Scenario.model_validate(scenario)
        validation = scenario_service.validate(model)
        result = scenario_service.run_compare(model)
        if (
            not validation["ok"]
            or validation["unresolved"]
            or not result["best"]
            or (
                result["baseline"]["assigned"],
                result["best"]["assigned"],
                result["best"]["costWon"],
            )
            != (baseline, assigned, cost)
        ):
            raise HTTPException(
                422,
                "현재 강좌 자료로 예시 입력값을 검증하지 못했습니다. 다른 종목을 선택해 주세요.",
            )
        items.append(
            {
                "id": pid,
                "label": f"{label} · {courses[0]['facilityName']}",
                "description": f"{region_name} · {courses[0]['name']} · {baseline}명 → {assigned}명 · 조치 비용 {cost:,}원(가정)",
                "explanation": explanations[pid],
                "scenario": scenario,
                "expected": {"baseline": baseline, "assigned": assigned, "cost": cost},
            }
        )
    return {
        "items": items,
        "datasetVersion": version,
        "regionCode": actual_region,
        "regionName": region_name,
        "requestedRegion": region,
        "fallbackRegion": actual_region != region,
        "courses": [
            {
                "id": c["_id"],
                "name": c["name"],
                "facilityName": c["facilityName"],
                "sessions": c["sessions"],
                "priceWon": c["priceWon"],
                "lastMonth": c["lastMonth"],
            }
            for c in courses
        ],
    }
