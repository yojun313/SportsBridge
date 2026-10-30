"""협의 계획서·가맹 제안서 초안. 결정적 템플릿(LLM 없이)과, LLM 초안 후검증(숫자·고유명사 대조)을 제공합니다."""

from __future__ import annotations

import re
from datetime import UTC, datetime

from app.engine.models import Scenario


def build_facts(
    sc: Scenario,
    selected: list[str],
    evaluation: dict,
    region_name: str,
    dataset_version: str | None,
) -> dict:
    actions = {a.id: a for a in sc.actions}
    options = {o.id: o for o in sc.supplyOptions}
    groups = {g.id: g for g in sc.demandGroups}
    sel = [actions[a] for a in selected if a in actions]
    unresolved = []
    for a in sel:
        if a.costWon is None:
            unresolved.append(f"조치 '{a.label}' 비용 미확인")
        if a.kind == "open_course" and a.capacity is None:
            unresolved.append(f"조치 '{a.label}' 신설 정원 미확인")
    for o in sc.supplyOptions:
        if o.capacity is None and o.exists:
            unresolved.append(f"강좌 '{o.label}' 정원 미확인")
        if o.voucherAffiliated is None:
            unresolved.append(f"강좌 '{o.label}' 가맹 여부 미확인")
        if o.attendanceRule == "unknown" and o.sessions:
            unresolved.append(f"강좌 '{o.label}' 출석 규칙 미확인")
    assumed = [
        f"조치 '{a.label}' 비용({a.costWon:,}원)은 가정값"
        for a in sel
        if a.costWon is not None and a.costProvenance == "assumed"
    ]
    assumed += [
        f"강좌 '{o.label}' 정원({o.capacity}석)은 가정값"
        for o in sc.supplyOptions
        if o.capacity is not None and o.capacityProvenance == "assumed"
    ]
    return {
        "date": datetime.now(UTC).astimezone().date().isoformat(),
        "title": sc.title or f"{region_name} {sc.sport or ''} 공급 개선 협의안".strip(),
        "regionCode": sc.regionCode,
        "regionName": region_name,
        "sport": sc.sport,
        "mode": sc.mode,
        "datasetVersion": dataset_version,
        "budgetWon": sc.budgetWon,
        "totalDemand": evaluation["totalDemand"],
        "assigned": evaluation.get("assigned"),
        "connectedGroups": evaluation.get("connectedGroups"),
        "costWon": evaluation["costWon"],
        "groups": [
            {
                "id": g.id,
                "label": g.label,
                "size": g.size,
                "sport": g.sport,
                "assigned": evaluation["perGroup"][g.id]["assigned"],
                "availability": [
                    f"{'월화수목금토일'[w.weekday]} {w.startMinute // 60:02d}:{w.startMinute % 60:02d}~{w.endMinute // 60:02d}:{w.endMinute % 60:02d}"
                    for w in g.availability
                ],
                "transport": g.transport,
                "provenance": g.provenance,
            }
            for g in sc.demandGroups
        ],
        "actions": [
            {
                "id": a.id,
                "label": a.label,
                "kind": a.kind,
                "costWon": a.costWon,
                "costProvenance": a.costProvenance,
                "facility": (
                    options.get(a.supplyOptionId).facilityName
                    if a.supplyOptionId and options.get(a.supplyOptionId)
                    else next(
                        (o.facilityName for o in sc.supplyOptions if o.facilityId == a.facilityId),
                        a.facilityId,
                    )
                ),
                "capacity": a.capacity,
                "requires": a.requires,
            }
            for a in sel
        ],
        "assignments": [
            {
                "group": groups[x["groupId"]].label,
                "option": options[x["optionId"]].label,
                "count": x["count"],
            }
            for x in evaluation["assignments"]
            if x["groupId"] in groups and x["optionId"] in options
        ],
        "blocked": [
            {
                "group": groups[b["groupId"]].label,
                "option": options[b["optionId"]].label,
                "reasons": b["labels"],
            }
            for b in evaluation["blocked"]
            if b["groupId"] in groups and b["optionId"] in options
        ][:30],
        "unresolved": unresolved,
        "assumed": assumed,
    }


KIND_KO = {
    "affiliate": "가맹 협의",
    "open_course": "강좌 신설",
    "add_capacity": "정원 추가",
    "transport": "이동 지원",
}


def template_plan(facts: dict) -> str:
    f = facts
    lines = [
        f"# {f['title']}",
        "",
        f"작성일 {f['date']} · 데이터 버전 {f['datasetVersion'] or '–'} · **자동 생성 초안, 담당자 검토 전**",
        "",
        "## 1. 목적",
        f"{f['regionName']}에서 스포츠 강좌이용권으로 이용할 수 있는 {f['sport'] or ''} 강좌를 늘리기 위해 검토할 지원 방안을 정리합니다.".replace(
            "  ", " "
        ),
        "",
        "## 2. 수요 집단",
    ]
    for g in f["groups"]:
        lines.append(
            f"- {g['label']}: {g['size']}명, 종목 {g['sport']}, 가용시간 {', '.join(g['availability']) or '제약 없음'}, 이동 {g['transport']} (출처: {g['provenance']})"
        )
    lines += ["", "## 3. 선택한 조치 조합"]
    if not f["actions"]:
        lines.append("- 조치 없음(현재 상태)")
    for a in f["actions"]:
        cost = (
            f"{a['costWon']:,}원 ({a['costProvenance']})"
            if a["costWon"] is not None
            else "비용 미확인"
        )
        extra = f", 정원 {a['capacity']}석" if a.get("capacity") is not None else ""
        req = f", 선행: {', '.join(a['requires'])}" if a.get("requires") else ""
        lines.append(
            f"- {a['id']} {a['label']} — {KIND_KO.get(a['kind'], a['kind'])}, 대상 {a['facility']}, {cost}{extra}{req}"
        )
    lines += ["", "## 4. 모델상 결과"]
    if f["mode"] == "capacity":
        lines.append(
            f"- 총 수요 {f['totalDemand']}명 중 **모델상 배정 가능 {f['assigned']}명**, 비용 합계 {f['costWon']:,}원"
            + (f", 예산 {f['budgetWon']:,}원" if f["budgetWon"] is not None else "")
        )
    else:
        lines.append(
            f"- 정원 미적용 비교 모드: 연결 가능한 수요 집단 {f['connectedGroups']}개 (정원을 보지 않았으므로 사람 수로 해석하지 않음)"
        )
    for x in f["assignments"]:
        lines.append(f"- {x['group']} → {x['option']}: {x['count']}명")
    if f["blocked"]:
        lines += ["", "### 막힌 연결"]
        for b in f["blocked"][:10]:
            lines.append(f"- {b['group']} → {b['option']}: {', '.join(b['reasons'])}")
    lines += ["", "## 5. 성립 조건 (확인 필요)"]
    lines += [f"- {u}" for u in f["unresolved"]] or ["- 없음"]
    if f["assumed"]:
        lines += ["", "## 6. 가정에 의존하는 값"] + [f"- {a}" for a in f["assumed"]]
    lines += [
        "",
        "## 7. 다음 행동",
        "- 위 확인 필요 항목을 시설·기관에 확인한 뒤 재계산합니다.",
        "- 가맹 신청은 시설이 공식 사이트(svoucher.kspo.or.kr)에서 직접 진행합니다. 본 문서는 협의 준비용입니다.",
        "",
        "_이 문서의 배정 인원은 입력 조건과 가정하의 모델 값이며 실제 참여·예산 절감·사업 승인을 뜻하지 않습니다._",
    ]
    return "\n".join(lines)


_NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")


def verify_numbers_and_names(draft: str, facts: dict) -> list[str]:
    """초안의 모든 숫자와 시설·집단·조치 이름이 facts에 존재하는지 검사. 문제 목록을 돌려줍니다(비어 있으면 통과)."""
    allowed_nums: set[str] = set()

    def walk(v):
        if isinstance(v, bool):
            return
        if isinstance(v, (int, float)):
            allowed_nums.add(str(int(v)) if float(v).is_integer() else str(v))
            allowed_nums.add(f"{int(v):,}" if float(v).is_integer() else str(v))
        elif isinstance(v, str):
            for m in _NUM_RE.findall(v):
                allowed_nums.add(m)
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)

    walk(facts)
    # 문서 구조 번호(## 1. 등)와 날짜 부분은 허용
    allowed_nums.update(str(i) for i in range(32))
    problems = []
    for m in _NUM_RE.findall(draft):
        if m not in allowed_nums and m.replace(",", "") not in allowed_nums:
            problems.append(f"근거 없는 숫자: {m}")
    names = {a["facility"] for a in facts["actions"] if a.get("facility")} | {
        g["label"] for g in facts["groups"]
    }
    # 이름 검증은 '시설명'처럼 보이는 고유명사가 facts 밖에서 등장하는지 완벽히 판정할 수 없어, 문서에 facts의 시설명이 하나도 없으면 경고
    if facts["actions"] and not any(n in draft for n in names if n):
        problems.append("근거의 시설·집단 이름이 문서에 나타나지 않음")
    return sorted(set(problems))
