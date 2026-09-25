"""수요 집단 ↔ 공급 옵션 호환 판정. 각 판정은 (가능 여부, 막힌 제약 목록)을 돌려줍니다."""

from __future__ import annotations

from app.engine.models import DemandGroup, SupplyOption


def time_ok(group: DemandGroup, opt: SupplyOption) -> tuple[bool, str | None]:
    if not opt.sessions:
        return False, "time:unknown_schedule"
    if not group.availability:
        return True, None  # 가용시간 미입력 = 제약 없음으로 보되 화면에서 안내
    buf = group.bufferMinutes
    fits = []
    for s in opt.sessions:
        ok = any(w.weekday == s.weekday and w.startMinute <= s.startMinute - buf and s.endMinute + buf <= w.endMinute
                 for w in group.availability)
        fits.append(ok)
    if opt.attendanceRule == "all_required" or opt.attendanceRule == "unknown":
        # 불명은 보수적으로 전 요일 필수로 판정하되, 사유는 unknown으로 남깁니다.
        if all(fits):
            return True, None
        return False, "time:required_days_conflict" if opt.attendanceRule == "all_required" else "time:attendance_rule_unknown"
    # selectable: 필요한 주당 횟수만큼 맞는 세션이 있으면 OK
    need = group.sessionsPerWeek or 1
    return (sum(fits) >= need), (None if sum(fits) >= need else "time:not_enough_selectable_days")


def age_ok(group: DemandGroup, opt: SupplyOption) -> tuple[bool, str | None]:
    if opt.ageMin is None and opt.ageMax is None:
        return True, None
    if group.ageMin is None and group.ageMax is None:
        return True, None
    gmin, gmax = group.ageMin or 0, group.ageMax or 99
    omin, omax = opt.ageMin or 0, opt.ageMax or 99
    if gmin >= omin and gmax <= omax:
        return True, None
    return False, "age:out_of_range"


def sport_ok(group: DemandGroup, opt: SupplyOption) -> tuple[bool, str | None]:
    return (group.sport == opt.sport), (None if group.sport == opt.sport else "sport:mismatch")


def reach_ok(group: DemandGroup, opt: SupplyOption, transport_actions: set[tuple[str, str]]) -> tuple[bool, str | None]:
    if (group.id, opt.facilityId) in transport_actions:
        return True, None
    r = opt.reachable.get(group.id)
    if r is True:
        return True, None
    if r is False:
        return False, "reach:not_reachable"
    if group.transport == "needs_support":
        return False, "reach:needs_transport_support"
    return True, None  # 미확인 + 자력 이동 가능 집단은 통과(확인 필요로 표시)


def affiliation_ok(opt: SupplyOption, affiliated: set[str]) -> tuple[bool, str | None]:
    if opt.facilityId in affiliated or opt.voucherAffiliated is True:
        return True, None
    if opt.voucherAffiliated is False:
        return False, "affiliation:not_affiliated"
    return False, "affiliation:unknown"


def compatible(group: DemandGroup, opt: SupplyOption, affiliated: set[str], transport_actions: set[tuple[str, str]],
               exists: bool) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if not exists:
        reasons.append("supply:not_opened")
    for fn in (sport_ok, age_ok, time_ok):
        ok, why = fn(group, opt)
        if not ok:
            reasons.append(why)
    ok, why = reach_ok(group, opt, transport_actions)
    if not ok:
        reasons.append(why)
    ok, why = affiliation_ok(opt, affiliated)
    if not ok:
        reasons.append(why)
    return (not reasons), reasons
