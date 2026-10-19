"""원본 CSV 10종 → MongoDB 적재 파이프라인 (동기, 스크립트용).

단계: 지역(26) → 가맹시설(80∪05) → 강좌(05+74) → 전체시설(64+73+19, 안전34·교통08) →
가맹시설 교통(06) → 규칙 매칭 → 시군구 집계. 모든 문서에 datasetVersion을 붙이고,
성공했을 때만 catalog_state의 활성 버전을 바꿉니다.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

from app.core.paths import DATA_DIR
from app.services.dataset_files import FILES, find_file
from app.services.normalization_service import (
    norm_address,
    norm_name,
    norm_tel,
    parse_coord,
    parse_float,
    parse_int,
    parse_time_hhmm,
    parse_weekday_bits,
)
from app.services.regions import RegionResolver

csv.field_size_limit(10**9)

EVENING_MINUTE = 18 * 60
CHUNK = 4000


def _hid(prefix: str, *parts: str) -> str:
    return prefix + hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:14]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_csv(raw_dir: Path, key: str, limit: int | None = None):
    path = find_file(raw_dir, key)
    if path is None:
        return
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8-sig", newline="") as f:
        for i, row in enumerate(csv.DictReader(f)):
            if limit and i >= limit:
                break
            yield {k.strip(): (v or "").strip() for k, v in row.items() if k}


def load_category_rules() -> dict:
    p = DATA_DIR / "mappings" / "category_rules.json"
    return json.loads(p.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- 지역(26)
def build_regions(raw_dir: Path, version: str) -> tuple[list[dict], RegionResolver]:
    regions: dict[str, dict] = {}
    for r in read_csv(raw_dir, "regional_usage"):
        code = r["SIGNGU_CD"][:5]
        doc = regions.setdefault(
            code,
            {
                "_id": f"r:{code}",
                "datasetVersion": version,
                "regionCode": code,
                "sidoCode": code[:2],
                "sidoName": r["CTPRVN_NM"],
                "sigunguName": r["SIGNGU_NM"],
                "baseYear": r["BASE_YEAR"],
                "population": parse_int(r["SIGNGU_ACCTO_POPLTN_CO"]),
                "facilityCountReported": parse_int(r["SIGNGU_ACCTO_FCLTY_CO"]),
                "targets": {},
                "recipients": {},
                "targetsTotal": 0,
                "recipientsTotal": 0,
                "provenance": "public",
                "sourceKey": "regional_usage",
            },
        )
        flag = r["RECIPT_FLAG_CD"] or r["RECIPT_FLAG_NM"]
        t = parse_int(r["CRRSPND_FLAG_TRGET_NMPR_CO"]) or 0
        rc = parse_int(r["CRRSPND_FLAG_RECIPT_NMPR_CO"]) or 0
        doc["targets"][flag] = t
        doc["recipients"][flag] = rc
        doc["targetsTotal"] += t
        doc["recipientsTotal"] += rc
        doc["flagNames"] = {**doc.get("flagNames", {}), flag: r["RECIPT_FLAG_NM"]}
    resolver = RegionResolver(list(regions.values()))
    return list(regions.values()), resolver


# ---------------------------------------------------------------- 가맹시설(80 ∪ 05)
def build_voucher_facilities(
    raw_dir: Path, version: str, resolver: RegionResolver, limit=None
) -> dict[str, dict]:
    facilities: dict[str, dict] = {}

    def key_of(code, name, addr, sgnm):
        region, ok = resolver.resolve(code, sgnm)
        return (region, norm_name(name), norm_address(addr)), region, ok

    for r in read_csv(raw_dir, "voucher_facilities", limit):
        k, region, ok = key_of(r["SIGNGU_CD"], r["FCLTY_NM"], r["FCLTY_ADDR"], r["SIGNGU_NM"])
        fid = _hid("vf:", *k)
        doc = facilities.get(fid)
        if doc is None:
            doc = facilities[fid] = {
                "_id": fid,
                "datasetVersion": version,
                "name": r["FCLTY_NM"].replace("\xa0", " ").strip(),
                "nameNorm": k[1],
                "address": r["FCLTY_ADDR"],
                "addressNorm": k[2],
                "detailAddress": r["DETAIL_ADDR"],
                "zip": r["ZIP_NO"],
                "tel": r["RPRSNTV_TEL_NO"],
                "telNorm": norm_tel(r["RPRSNTV_TEL_NO"]),
                "regionCode": region,
                "regionMapped": ok,
                "sidoCode": region[:2],
                "regionNameRaw": f"{r['CTPRVN_NM']} {r['SIGNGU_NM']}",
                "sports": [],
                "sportCodes": [],
                "location": parse_coord(r["FCLTY_X_CRDNT_VALUE"], r["FCLTY_Y_CRDNT_VALUE"]),
                "decisionDate": r["FCLTY_DECSN_DE"],
                "sources": ["voucher_facilities"],
                "hasCourseFlag": r["FCLTY_COURSE_SDIV_NM"] == "강좌",
                "provenance": "public",
            }
        if r["ITEM_NM"] and r["ITEM_NM"] not in doc["sports"]:
            doc["sports"].append(r["ITEM_NM"])
            doc["sportCodes"].append(r["ITEM_CD"])
        if r["FCLTY_DECSN_DE"] > (doc.get("decisionDate") or ""):
            doc["decisionDate"] = r["FCLTY_DECSN_DE"]
        if not doc["telNorm"] and r["RPRSNTV_TEL_NO"]:
            doc["tel"], doc["telNorm"] = r["RPRSNTV_TEL_NO"], norm_tel(r["RPRSNTV_TEL_NO"])
        if doc["location"] is None:
            doc["location"] = parse_coord(r["FCLTY_X_CRDNT_VALUE"], r["FCLTY_Y_CRDNT_VALUE"])
        if r["FCLTY_COURSE_SDIV_NM"] == "강좌":
            doc["hasCourseFlag"] = True

    # 05 이용현황의 시설도 가맹시설 집합에 합칩니다(과거 가맹 포함).
    for r in read_csv(raw_dir, "voucher_usage", limit):
        k, region, ok = key_of(r["SIGNGU_CD"], r["FCLTY_NM"], r["FCLTY_ADDR"], r["SIGNGU_NM"])
        fid = _hid("vf:", *k)
        doc = facilities.get(fid)
        if doc is None:
            doc = facilities[fid] = {
                "_id": fid,
                "datasetVersion": version,
                "name": r["FCLTY_NM"].strip(),
                "nameNorm": k[1],
                "address": r["FCLTY_ADDR"],
                "addressNorm": k[2],
                "detailAddress": r["FCLTY_DETAIL_ADDR"],
                "zip": r["ZIP_NO"],
                "tel": r["TEL_NO"],
                "telNorm": norm_tel(r["TEL_NO"]),
                "regionCode": region,
                "regionMapped": ok,
                "sidoCode": region[:2],
                "regionNameRaw": f"{r['CTPRVN_NM']} {r['SIGNGU_NM']}",
                "sports": [],
                "sportCodes": [],
                "location": None,
                "decisionDate": "",
                "sources": ["voucher_usage"],
                "hasCourseFlag": True,
                "provenance": "public",
            }
        elif "voucher_usage" not in doc["sources"]:
            doc["sources"].append("voucher_usage")
        if r["ITEM_NM"] and r["ITEM_NM"] not in doc["sports"]:
            doc["sports"].append(r["ITEM_NM"])
            doc["sportCodes"].append(r["ITEM_CD"])
        if not doc["telNorm"] and r["TEL_NO"]:
            doc["tel"], doc["telNorm"] = r["TEL_NO"], norm_tel(r["TEL_NO"])
        if r["BSNS_NO"]:
            doc.setdefault("businessNos", [])
            if r["BSNS_NO"] not in doc["businessNos"] and len(doc["businessNos"]) < 5:
                doc["businessNos"].append(r["BSNS_NO"])
    return facilities


# ---------------------------------------------------------------- 강좌(05 + 74)
def build_courses(
    raw_dir: Path, version: str, resolver: RegionResolver, facilities: dict[str, dict], limit=None
):
    # 74 강좌표를 (종목코드, 강좌명 정규화)로 색인
    sched_index: dict[tuple[str, str], list[dict]] = defaultdict(list)
    n74 = 0
    for r in read_csv(raw_dir, "voucher_courses", limit):
        n74 += 1
        start, end = parse_time_hhmm(r["BEGIN_TIME"]), parse_time_hhmm(r["END_TIME"])
        days = parse_weekday_bits(r["WKDAY_NM"])
        sched_index[(r["ITEM_CD"], norm_name(r["COURSE_NM"]))].append(
            {
                "start": start,
                "end": end,
                "days": days,
                "bits": r["WKDAY_NM"],
                "price": parse_int(r["ATNLC_PRC"]),
                "year": r["TRGET_YEAR"],
                "desc": r["COURSE_DETAIL_CN"],
                "instructor": r["LCTRR_NM"],
            }
        )

    courses: dict[str, dict] = {}
    fac_usage: dict[str, dict] = defaultdict(lambda: {"months": {}, "total": 0})
    for r in read_csv(raw_dir, "voucher_usage", limit):
        region, _ok = resolver.resolve(r["SIGNGU_CD"], r["SIGNGU_NM"])
        fid = _hid("vf:", region, norm_name(r["FCLTY_NM"]), norm_address(r["FCLTY_ADDR"]))
        cno = r["COURSE_NO"]
        cid = f"c:{cno}"
        ym = f"{r['COURSE_ESTBL_YEAR']}-{r['COURSE_ESTBL_MT'].zfill(2)}"
        applicants = parse_int(r["COURSE_REQST_NMPR_CO"]) or 0
        price = parse_int(r["COURSE_PRC"])
        doc = courses.get(cid)
        if doc is None:
            doc = courses[cid] = {
                "_id": cid,
                "datasetVersion": version,
                "sourceCourseId": cno,
                "facilityId": fid,
                "facilityName": r["FCLTY_NM"].strip(),
                "regionCode": region,
                "sidoCode": region[:2],
                "sport": r["ITEM_NM"],
                "sportCode": r["ITEM_CD"],
                "name": r["COURSE_NM"].strip(),
                "nameNorm": norm_name(r["COURSE_NM"]),
                "months": {},
                "provenance": "public",
            }
        doc["months"][ym] = {
            "applicants": applicants,
            "price": price,
            "begin": r["COURSE_BEGIN_DE"],
            "end": r["COURSE_END_DE"],
        }
        fu = fac_usage[fid]
        m = fu["months"].setdefault(ym, {"applicants": 0, "courses": set()})
        m["applicants"] += applicants
        m["courses"].add(cno)
        fu["total"] += applicants

    # 월 배열 정리 + 74 시간표 결합
    stats = Counter()
    for doc in courses.values():
        months = sorted(doc["months"].items())
        doc["months"] = [{"ym": ym, **v} for ym, v in months]
        doc["firstMonth"], doc["lastMonth"] = months[0][0], months[-1][0]
        doc["monthCount"] = len(months)
        doc["totalApplicants"] = sum(v["applicants"] for _, v in months)
        doc["lastApplicants"] = months[-1][1]["applicants"]
        last_price = next((v["price"] for _, v in reversed(months) if v["price"] is not None), None)
        doc["priceWon"] = last_price
        doc["pricePeriod"] = "month" if last_price is not None else "unknown"
        doc["priceNote"] = "이용현황의 강좌연월별 금액을 월 수강료로 해석 (원본 단위 표기 없음)"
        cands = sched_index.get((doc["sportCode"], doc["nameNorm"]), [])
        chosen, ambiguous, ncand = _pick_schedule(cands, last_price, doc["lastMonth"][:4])
        doc["scheduleCandidates"] = ncand
        if chosen is None:
            doc["sessions"] = []
            doc["scheduleSource"] = "none"
            doc["scheduleAmbiguous"] = False
            doc["description"] = ""
            stats["no_schedule"] += 1
        else:
            doc["sessions"] = _sessions(chosen)
            doc["scheduleSource"] = "course_table"
            doc["scheduleAmbiguous"] = ambiguous
            doc["weekdayBits"] = chosen["bits"]
            doc["description"] = chosen["desc"]
            doc["descriptionHash"] = (
                hashlib.sha1(chosen["desc"].encode("utf-8")).hexdigest()[:16]
                if chosen["desc"]
                else ""
            )
            doc["targetYear"] = chosen["year"]
            stats["ambiguous" if ambiguous else "unique"] += 1
        doc["parseFlags"] = []
        if chosen and (chosen["start"] is None or chosen["end"] is None):
            doc["parseFlags"].append("time_unparsed")
        if chosen and not chosen["days"]:
            doc["parseFlags"].append("weekday_unparsed")
        if (
            chosen
            and chosen["start"] is not None
            and chosen["end"] is not None
            and chosen["end"] <= chosen["start"]
        ):
            doc["parseFlags"].append("end_before_start")

    # 시설 이용 요약
    for fid, fu in fac_usage.items():
        f = facilities.get(fid)
        if not f:
            continue
        ms = sorted(fu["months"].items())
        f["usage"] = {
            "firstMonth": ms[0][0],
            "lastMonth": ms[-1][0],
            "monthCount": len(ms),
            "totalApplicants": fu["total"],
            "last12mApplicants": None,  # 집계 단계에서 데이터 최신월 기준으로 채움
            "maxCoursesInMonth": max(len(v["courses"]) for _, v in ms),
        }
    monthly_docs = []
    for fid, fu in fac_usage.items():
        for ym, v in fu["months"].items():
            monthly_docs.append(
                {
                    "datasetVersion": version,
                    "facilityId": fid,
                    "yearMonth": ym,
                    "applicants": v["applicants"],
                    "courseCount": len(v["courses"]),
                }
            )
    stats["course_table_rows"] = n74
    return courses, monthly_docs, dict(stats)


def _pick_schedule(cands: list[dict], price: int | None, year: str):
    if not cands:
        return None, False, 0
    pool = cands
    if price is not None:
        pp = [c for c in pool if c["price"] == price]
        if pp:
            pool = pp
    yy = [c for c in pool if c["year"] == year]
    if yy:
        pool = yy
    distinct = {}
    for c in pool:
        distinct.setdefault((c["start"], c["end"], c["bits"]), c)
    # 최신 연도, 설명이 긴 후보를 우선
    chosen = max(distinct.values(), key=lambda c: (c["year"], len(c["desc"])))
    return chosen, len(distinct) > 1, len(distinct)


def _sessions(c: dict) -> list[dict]:
    if c["start"] is None or c["end"] is None or not c["days"]:
        return []
    return [{"weekday": d, "startMinute": c["start"], "endMinute": c["end"]} for d in c["days"]]


# ---------------------------------------------------------------- 전체시설(64 + 73 + 19) + 안전(34) + 교통(08)
def build_all_facilities(
    raw_dir: Path, version: str, resolver: RegionResolver, rules: dict, limit=None
):
    suit = rules["child_suitability"]
    type_sport = rules["type_to_sport"]
    induty_sport = rules["induty_to_sport"]
    out: dict[str, dict] = {}

    def add(source, name, addr, region, ok, region_raw, **extra):
        k = (region, norm_name(name), norm_address(addr))
        fid = _hid("af:", *k)
        if fid in out:
            d = out[fid]
            if source not in d["sources"]:
                d["sources"].append(source)
            for kk, vv in extra.items():
                if d.get(kk) in (None, "", []) and vv not in (None, ""):
                    d[kk] = vv
            return d
        d = out[fid] = {
            "_id": fid,
            "datasetVersion": version,
            "sources": [source],
            "name": name.replace("\xa0", " ").replace("\n", " ").strip(),
            "nameNorm": k[1],
            "address": addr,
            "addressNorm": k[2],
            "regionCode": region,
            "regionMapped": ok,
            "sidoCode": region[:2],
            "regionNameRaw": region_raw,
            "provenance": "public",
            **extra,
        }
        return d

    for r in read_csv(raw_dir, "all_facilities", limit):
        if not r["SIGNGU_CD"] and not r["SIGNGU_NM"]:
            continue
        region, ok = resolver.resolve(r["SIGNGU_CD"], r["SIGNGU_NM"])
        addr = r["RDNMADR_ONE_NM"] or r["FCLTY_ADDR_ONE_NM"]
        induty, ftype = r["INDUTY_NM"], r["FCLTY_TY_NM"]
        sport = type_sport.get(ftype)
        if sport is None:
            sport = induty_sport.get(induty)
        add(
            "all_facilities",
            r["FCLTY_NM"],
            addr,
            region,
            ok,
            f"{r['CTPRVN_NM']} {r['SIGNGU_NM']}",
            category=induty,
            facilityType=ftype,
            flag=r["FCLTY_FLAG_NM"],
            status=r["FCLTY_STATE_VALUE"] or "미확인",
            deleted=r["DEL_AT"] == "Y",
            indoor=r["NDOR_SDIV_NM"]
            if r["NDOR_SDIV_NM"] in ("실내", "실외", "실내외", "없음")
            else "",
            area=parse_float(r["FCLTY_AR_CO"]),
            tel=r["FCLTY_TEL_NO"],
            telNorm=norm_tel(r["FCLTY_TEL_NO"]),
            location=parse_coord(r["FCLTY_LO"], r["FCLTY_LA"]),
            closedDate=r["OPER_CLSBIZ_DE"],
            childSuitability=suit.get(induty, "unknown"),
            suitabilitySource="rule",
            sportGuess=sport,
            updatedAt=r["UPDT_DT"],
            sourceAsOf=r["FCLTY_CRTN_STDR_DE"] or r["UPDT_DT"],
        )

    for r in read_csv(raw_dir, "public_facilities", limit):
        region, ok = resolver.resolve(
            r["ROAD_NM_SIGNGU_CD"] or r["POSESN_MBY_SIGNGU_CD"],
            r["ROAD_NM_SIGNGU_NM"] or r["POSESN_MBY_SIGNGU_NM"],
        )
        induty, ftype = r["INDUTY_NM"], r["FCLTY_TY_NM"]
        add(
            "public_facilities",
            r["FCLTY_NM"],
            r["RDNMADR_NM"],
            region,
            ok,
            f"{r['ROAD_NM_CTPRVN_NM']} {r['ROAD_NM_SIGNGU_NM']}",
            category=induty,
            facilityType=ftype,
            flag=r["FCLTY_FLAG_NM"] or "공공",
            status="정상운영" if r["FCLTY_STATE_CD"] == "00" else "미확인",
            deleted=r["DEL_AT"] == "Y",
            indoor="",
            area=parse_float(r["FCLTY_AR_CO"]),
            tel=r["RSPNSBLTY_TEL_NO"],
            telNorm=norm_tel(r["RSPNSBLTY_TEL_NO"]),
            location=parse_coord(r["FCLTY_LO"], r["FCLTY_LA"]),
            closedDate="",
            childSuitability=suit.get(induty, "unknown"),
            suitabilitySource="rule",
            sportGuess=type_sport.get(ftype) or induty_sport.get(induty),
            owner=r["POSESN_MBY_NM"],
            department=r["RSPNSBLTY_DEPT_NM"],
            sourceAsOf="",
        )

    for r in read_csv(raw_dir, "open_schools", limit):
        region, ok = resolver.resolve("", r["ALSFC_SIGNGU_NM"])
        # 개방학교는 코드가 없어 시도명+시군구명으로만 붙입니다.
        sido = _sido_code_by_name(resolver, r["ALSFC_CTPRVN_NM"])
        if sido:
            region, ok = resolver.resolve(sido + "000", r["ALSFC_SIGNGU_NM"])
        add(
            "open_schools",
            r["SCHUL_NM"],
            r["ALSFC_ADDR"],
            region,
            ok,
            f"{r['ALSFC_CTPRVN_NM']} {r['ALSFC_SIGNGU_NM']}",
            category="개방학교 체육시설",
            facilityType=r["SCHUL_TY_NM"],
            flag="학교",
            status="개방(연도 확인 필요)",
            deleted=False,
            indoor="",
            area=None,
            tel="",
            telNorm="",
            location=None,
            closedDate="",
            childSuitability="likely",
            suitabilitySource="rule",
            sportGuess=None,
            openItems=r["OPER_ITEM_CN"],
            openHours=r["OPER_TIME_CN"],
            openPeriod=r["OPN_PD"],
            showers=parse_int(r["SHWERRM_CO"]),
            lockers=parse_int(r["LOCKERRM_CO"]),
            sourceAsOf=r["BASE_YEAR"],
        )

    # 안전점검(34): 같은 이름+도로명주소의 최신 점검
    safety: dict[tuple, dict] = {}
    for r in read_csv(raw_dir, "safety", limit):
        region, _ = resolver.resolve(r["CMPTNC_SIGNGU_CD"], r["CMPTNC_SIGNGU_NM"])
        k = (
            region,
            norm_name(r["FCLTY_NM"]),
            norm_address(r["FCLTY_ROAD_NM_ADDR"] or r["FCLTY_ADDR"]),
        )
        cur = safety.get(k)
        stamp = r["SAFECHK_DE"] or r["FCLTY_INFO_UPDT_DE"]
        if cur is None or stamp > cur["stamp"]:
            safety[k] = {
                "stamp": stamp,
                "grade": r["SAFECHK_GNRLZ_GRAD_NM"] or "없음",
                "checkDate": r["SAFECHK_DE"],
                "operState": r["OPER_STATE_NM"],
                "closedDate": r["OPER_CLSBIZ_DE"],
                "publicDate": r["SAFECHK_OTHBC_DE"],
            }
    hit = 0
    for d in out.values():
        s = safety.get((d["regionCode"], d["nameNorm"], d["addressNorm"]))
        if s:
            hit += 1
            d["safety"] = {
                "grade": s["grade"],
                "checkDate": s["checkDate"],
                "operState": s["operState"],
                "provenance": "public",
            }
            if d.get("status") in ("", "미확인") and s["operState"]:
                d["status"] = s["operState"]
        else:
            d["safety"] = None

    # 공공체육시설 인접 대중교통(08): 시설별 최단 도보시간
    transit: dict[tuple, dict] = {}
    for r in read_csv(raw_dir, "transit_public", limit):
        sec = parse_int(r["WLKG_MVMN_TIME"])
        if sec is None:
            continue
        region, _ = resolver.resolve(r["ALSFC_SIGNGU_CD"], r["ALSFC_SIGNGU_NM"])
        k = (region, norm_name(r["ALSFC_NM"]), norm_address(r["ALSFC_ADDR"]))
        cur = transit.get(k)
        if cur is None or sec < cur["minWalkSec"]:
            transit[k] = {
                "minWalkSec": sec,
                "stopName": r["BSTP_SUBWAYST_NM"],
                "stopType": r["PBTRNSP_FCLTY_SDIV_NM"],
                "walkMeters": parse_int(r["WLKG_DSTNC_VALUE"]),
                "provenance": "public",
            }
    thit = 0
    for d in out.values():
        t = transit.get((d["regionCode"], d["nameNorm"], d["addressNorm"]))
        d["transit"] = t
        if t:
            thit += 1
    return out, {
        "allFacilities": len(out),
        "safetyJoined": hit,
        "safetyRows": len(safety),
        "transitJoined": thit,
    }


def _sido_code_by_name(resolver: RegionResolver, name: str) -> str:
    name = (name or "")[:2]
    for r in resolver.by_code.values():
        if r["sidoName"][:2] == name:
            return r["sidoCode"]
    return ""


def attach_voucher_transit(
    raw_dir: Path, resolver: RegionResolver, facilities: dict[str, dict], limit=None
) -> int:
    best: dict[str, dict] = {}
    for r in read_csv(raw_dir, "transit_voucher", limit):
        sec = parse_int(r["WLKG_MVMN_TIME"])
        if sec is None:
            continue
        region, _ = resolver.resolve(r["SVCH_FCLTY_SIGNGU_CD"], r["SVCH_FCLTY_SIGNGU_NM"])
        fid = _hid("vf:", region, norm_name(r["SVCH_FCLTY_NM"]), norm_address(r["SVCH_FCLTY_ADDR"]))
        cur = best.get(fid)
        if cur is None or sec < cur["minWalkSec"]:
            best[fid] = {
                "minWalkSec": sec,
                "stopName": r["BSTP_SUBWAYST_NM"],
                "stopType": r["PBTRNSP_FCLTY_SDIV_NM"],
                "walkMeters": parse_int(r["WLKG_DSTNC_VALUE"]),
                "provenance": "public",
            }
    hit = 0
    for fid, f in facilities.items():
        t = best.get(fid)
        f["transit"] = t
        if t:
            hit += 1
    return hit


# ---------------------------------------------------------------- 규칙 매칭 (가맹 ↔ 전체)
def _bigrams(s: str) -> set[str]:
    return {s[i : i + 2] for i in range(len(s) - 1)} if len(s) > 1 else {s}


def match_facilities(
    version: str, vfac: dict[str, dict], afac: dict[str, dict]
) -> tuple[list[dict], Counter]:
    """단계: exact_id 없음 → exact_name_addr → exact_name_region(양쪽 유일) → exact_tel_region → 블로킹 후보(LLM/검토용)."""
    by_key = {(d["regionCode"], d["nameNorm"], d["addressNorm"]): fid for fid, d in afac.items()}
    by_name_region: dict[tuple, list[str]] = defaultdict(list)
    by_tel_region: dict[tuple, list[str]] = defaultdict(list)
    grams: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for fid, d in afac.items():
        by_name_region[(d["regionCode"], d["nameNorm"])].append(fid)
        if d.get("telNorm"):
            by_tel_region[(d["regionCode"], d["telNorm"])].append(fid)
        for g in _bigrams(d["nameNorm"]):
            grams[d["regionCode"]][g].add(fid)
    v_name_count = Counter((d["regionCode"], d["nameNorm"]) for d in vfac.values())

    results: list[dict] = []
    stats = Counter()
    matched_af: set[str] = set()
    for vid, v in vfac.items():
        k = (v["regionCode"], v["nameNorm"], v["addressNorm"])
        af = by_key.get(k)
        mtype = None
        if af:
            mtype = "exact_name_addr"
        else:
            same = by_name_region.get((v["regionCode"], v["nameNorm"]), [])
            if (
                len(same) == 1
                and v_name_count[(v["regionCode"], v["nameNorm"])] == 1
                and len(v["nameNorm"]) >= 3
            ):
                af, mtype = same[0], "exact_name_region"
            elif v.get("telNorm"):
                tel = by_tel_region.get((v["regionCode"], v["telNorm"]), [])
                if len(tel) == 1:
                    af, mtype = tel[0], "exact_tel_region"
        if af:
            results.append(
                {
                    "_id": f"m:{vid}",
                    "datasetVersion": version,
                    "voucherFacilityId": vid,
                    "allFacilityId": af,
                    "matchType": mtype,
                    "provenance": "public",
                    "status": "matched",
                }
            )
            matched_af.add(af)
            stats[mtype] += 1
            continue
        # 블로킹: 같은 시군구에서 이름 bigram Jaccard 상위 3 (≥0.45) 또는 좌표 300m 이내
        cand_scores: dict[str, float] = {}
        vg = _bigrams(v["nameNorm"])
        counter: Counter = Counter()
        for g in vg:
            for fid in grams[v["regionCode"]].get(g, ()):
                counter[fid] += 1
        for fid, shared in counter.most_common(40):
            ag = _bigrams(afac[fid]["nameNorm"])
            j = shared / max(1, len(vg | ag))
            if j >= 0.45:
                cand_scores[fid] = j
        if v.get("location"):
            vx, vy = v["location"]["coordinates"]
            for fid in counter:  # 이름이 조금이라도 겹치는 것 중 300m 이내
                loc = afac[fid].get("location")
                if loc and _dist_m(vx, vy, *loc["coordinates"]) <= 300:
                    cand_scores[fid] = max(cand_scores.get(fid, 0), 0.5)
        top = sorted(cand_scores.items(), key=lambda kv: -kv[1])[:3]
        results.append(
            {
                "_id": f"m:{vid}",
                "datasetVersion": version,
                "voucherFacilityId": vid,
                "allFacilityId": None,
                "matchType": "unmatched",
                "provenance": "public",
                "status": "candidates" if top else "none",
                "candidates": [
                    {
                        "allFacilityId": fid,
                        "score": round(s, 3),
                        "name": afac[fid]["name"],
                        "address": afac[fid]["address"],
                    }
                    for fid, s in top
                ],
            }
        )
        stats["candidates" if top else "none"] += 1
    return results, stats


def _dist_m(x1, y1, x2, y2) -> float:
    import math

    dx = (x2 - x1) * 88_000 * math.cos(math.radians((y1 + y2) / 2))
    dy = (y2 - y1) * 111_000
    return math.hypot(dx, dy)


# ---------------------------------------------------------------- 시군구 집계
def build_aggregates(
    version: str, regions: list[dict], vfac: dict, courses: dict, afac: dict, matches: list[dict]
) -> list[dict]:
    max_ym = max((c["lastMonth"] for c in courses.values()), default="")
    cutoff = _shift_ym(max_ym, -12) if max_ym else ""
    matched_af = {m["allFacilityId"] for m in matches if m.get("allFacilityId")}
    per: dict[str, dict] = {}
    for r in regions:
        per[r["regionCode"]] = {
            "_id": f"g:{r['regionCode']}",
            "datasetVersion": version,
            "regionCode": r["regionCode"],
            "sidoCode": r["sidoCode"],
            "sidoName": r["sidoName"],
            "sigunguName": r["sigunguName"],
            "population": r["population"],
            "targetsTotal": r["targetsTotal"],
            "recipientsTotal": r["recipientsTotal"],
            "facilityCountReported": r["facilityCountReported"],
            "dataMaxMonth": max_ym,
            "activeCutoffMonth": cutoff,
            "voucherFacilityCount": 0,
            "activeFacilityCount": 0,
            "courseCount": 0,
            "activeCourseCount": 0,
            "scheduleKnownCount": 0,
            "eveningCount": 0,
            "weekendCount": 0,
            "sportCounts": {},
            "candidateCount": 0,
            "candidateLikelyCount": 0,
            "allFacilityCount": 0,
            "matchedFacilityCount": 0,
            "last12mApplicants": 0,
            "notComputable": [],
        }
    for f in vfac.values():
        g = per.get(f["regionCode"])
        if not g:
            continue
        g["voucherFacilityCount"] += 1
        u = f.get("usage")
        if u and u["lastMonth"] >= cutoff:
            g["activeFacilityCount"] += 1
    for c in courses.values():
        g = per.get(c["regionCode"])
        if not g:
            continue
        g["courseCount"] += 1
        active = c["lastMonth"] >= cutoff
        if active:
            g["activeCourseCount"] += 1
            g["sportCounts"][c["sport"]] = g["sportCounts"].get(c["sport"], 0) + 1
            g["last12mApplicants"] += sum(m["applicants"] for m in c["months"] if m["ym"] >= cutoff)
            if c["sessions"]:
                g["scheduleKnownCount"] += 1
                if any(s["startMinute"] >= EVENING_MINUTE for s in c["sessions"]):
                    g["eveningCount"] += 1
                if any(s["weekday"] >= 5 for s in c["sessions"]):
                    g["weekendCount"] += 1
    for fid, a in afac.items():
        g = per.get(a["regionCode"])
        if not g:
            continue
        g["allFacilityCount"] += 1
        if fid in matched_af:
            g["matchedFacilityCount"] += 1
            continue
        if a.get("deleted") or a.get("status") not in ("정상운영", "개방(연도 확인 필요)"):
            continue
        if a.get("childSuitability") == "unlikely":
            continue
        g["candidateCount"] += 1
        if a.get("childSuitability") == "likely":
            g["candidateLikelyCount"] += 1

    docs = list(per.values())
    for g in docs:
        t = g["targetsTotal"] or 0
        g["facilitiesPer1000Targets"] = round(g["activeFacilityCount"] / t * 1000, 2) if t else None
        g["targetsPerActiveFacility"] = (
            round(t / g["activeFacilityCount"], 1) if g["activeFacilityCount"] else None
        )
        g["recipientRate"] = round(g["recipientsTotal"] / t, 4) if t else None
        g["sportCount"] = len(g["sportCounts"])
        if g["activeCourseCount"]:
            top_sport, top_n = max(g["sportCounts"].items(), key=lambda kv: kv[1])
            g["topSport"], g["topSportShare"] = top_sport, round(top_n / g["activeCourseCount"], 4)
        else:
            g["topSport"], g["topSportShare"] = None, None
        if g["scheduleKnownCount"]:
            g["eveningShare"] = round(g["eveningCount"] / g["scheduleKnownCount"], 4)
            g["weekendShare"] = round(g["weekendCount"] / g["scheduleKnownCount"], 4)
        else:
            g["eveningShare"] = g["weekendShare"] = None
            g["notComputable"].append("time_axis:no_schedule")
        if not t:
            g["notComputable"].append("quantity_axis:no_targets")
        g["childAgeShare"] = None  # LLM 추출·검토 후 별도 갱신
    # 순위: 값이 작을수록 공백이 큰 축은 오름차순 순위(1 = 가장 부족)
    _rank(docs, "facilitiesPer1000Targets", ascending=True, key="rankFacilitiesPer1000")
    _rank(docs, "sportCount", ascending=True, key="rankSportCount")
    _rank(docs, "eveningShare", ascending=True, key="rankEveningShare")
    _rank(docs, "recipientRate", ascending=True, key="rankRecipientRate")
    for sido in {g["sidoCode"] for g in docs}:
        sub = [g for g in docs if g["sidoCode"] == sido]
        _rank(sub, "facilitiesPer1000Targets", ascending=True, key="rankFacilitiesPer1000InSido")
        _rank(sub, "sportCount", ascending=True, key="rankSportCountInSido")
    n = len(docs)
    for g in docs:
        g["regionTotal"] = n
        g["sidoTotal"] = sum(1 for x in docs if x["sidoCode"] == g["sidoCode"])
    return docs


def _rank(docs: list[dict], field: str, ascending: bool, key: str) -> None:
    valid = [d for d in docs if d.get(field) is not None]
    valid.sort(key=lambda d: d[field], reverse=not ascending)
    for i, d in enumerate(valid, 1):
        d[key] = i
    for d in docs:
        d.setdefault(key, None)


def _shift_ym(ym: str, months: int) -> str:
    y, m = int(ym[:4]), int(ym[5:7])
    idx = y * 12 + (m - 1) + months
    return f"{idx // 12}-{idx % 12 + 1:02d}"


# ---------------------------------------------------------------- 실행
def run_import(
    raw_dir: Path,
    version: str | None = None,
    dry_run: bool = False,
    limit: int | None = None,
    mongo_uri: str | None = None,
    db_name: str | None = None,
    progress=None,
) -> dict:
    from pymongo import MongoClient

    from app.config import DB_NAME, MONGO_URI

    def report(step: str, message: str = "", **extra):
        if progress:
            progress(step, message, None, extra or None)

    version = version or datetime.now(UTC).strftime("v%Y%m%d-%H%M%S")
    rules = load_category_rules()
    log: dict = {"version": version, "steps": {}}

    missing = [k for k in FILES if find_file(raw_dir, k) is None]
    required_missing = [
        k
        for k in missing
        if k
        in (
            "regional_usage",
            "voucher_facilities",
            "voucher_courses",
            "voucher_usage",
            "all_facilities",
        )
    ]
    if required_missing:
        raise FileNotFoundError("필수 원본이 없습니다: " + ", ".join(required_missing))
    report(
        "hash",
        f"원본 {len(FILES) - len(missing)}종 확인"
        + (f" (없음: {', '.join(missing)})" if missing else ""),
    )
    report("regions", "지역 표준 코드 적재")
    regions, resolver = build_regions(raw_dir, version)
    log["steps"]["regions"] = {"count": len(regions)}
    report("voucher_facilities", "가맹시설 병합 중")
    vfac = build_voucher_facilities(raw_dir, version, resolver, limit)
    log["steps"]["voucher_facilities"] = {
        "count": len(vfac),
        "unmappedRegions": len(resolver.unmapped),
    }
    report("courses", f"가맹시설 {len(vfac):,}곳 · 강좌·이용현황 결합 중")
    courses, monthly, cstats = build_courses(raw_dir, version, resolver, vfac, limit)
    log["steps"]["courses"] = {"count": len(courses), **cstats, "monthlyDocs": len(monthly)}
    report(
        "all_facilities",
        f"강좌 {len(courses):,}개 · 전체 체육시설·안전점검·대중교통 결합 중(가장 오래 걸립니다)",
    )
    afac, astats = build_all_facilities(raw_dir, version, resolver, rules, limit)
    log["steps"]["all_facilities"] = astats
    report("voucher_transit", f"전체시설 {len(afac):,}곳 · 가맹시설 대중교통 결합 중")
    log["steps"]["voucher_transit"] = {
        "joined": attach_voucher_transit(raw_dir, resolver, vfac, limit)
    }
    report("matching", "가맹시설 ↔ 전체시설 매칭 중")
    matches, mstats = match_facilities(version, vfac, afac)
    log["steps"]["matching"] = dict(mstats)
    report(
        "aggregates",
        f"매칭 {sum(v for k, v in mstats.items() if k.startswith('exact')):,}건 · 시군구 집계 중",
    )
    # 시설 활동성(최근 12개월) 채우기
    max_ym = max((c["lastMonth"] for c in courses.values()), default="")
    cutoff = _shift_ym(max_ym, -12) if max_ym else ""
    for f in vfac.values():
        u = f.get("usage")
        if u:
            u["active"] = u["lastMonth"] >= cutoff
    fac_last12 = defaultdict(int)
    for m in monthly:
        if m["yearMonth"] >= cutoff:
            fac_last12[m["facilityId"]] += m["applicants"]
    for fid, f in vfac.items():
        if f.get("usage"):
            f["usage"]["last12mApplicants"] = fac_last12.get(fid, 0)
    aggs = build_aggregates(version, regions, vfac, courses, afac, matches)
    log["steps"]["aggregates"] = {"count": len(aggs), "dataMaxMonth": max_ym}
    log["unmappedRegions"] = dict(list(resolver.unmapped.items())[:50])
    # 매칭 결과를 전체시설 문서에 역참조
    vm = {m["allFacilityId"]: m for m in matches if m.get("allFacilityId")}
    for fid, a in afac.items():
        m = vm.get(fid)
        a["voucherMatch"] = (
            {"voucherFacilityId": m["voucherFacilityId"], "matchType": m["matchType"]}
            if m
            else None
        )
    for m in matches:
        v = vfac.get(m["voucherFacilityId"])
        if v is not None:
            v["allMatch"] = {
                "allFacilityId": m["allFacilityId"],
                "matchType": m["matchType"],
                "status": m["status"],
            }

    files = []
    for key in FILES:
        p = find_file(raw_dir, key)
        if p:
            files.append(
                {"key": key, "name": p.name, "sha256": _sha256(p), "bytes": p.stat().st_size}
            )
    if dry_run:
        log["dryRun"] = True
        return log

    report("write", "MongoDB에 기록 중")
    from app.db import VERSIONED_COLLECTIONS, create_indexes_sync

    client = MongoClient(mongo_uri or MONGO_URI)
    db = client[db_name or DB_NAME]
    db["datasets"].insert_one(
        {
            "datasetVersion": version,
            "status": "staging",
            "files": files,
            "importedAt": datetime.now(UTC),
            "log": log,
            "mappingVersion": "category_rules.json",
            "isSynthetic": False,
        }
    )
    # 안정 ID(c:강좌번호, vf:/af: 해시)는 버전이 바뀌어도 같으므로, 기존 컬렉션에 덧쓰지 않고
    # staging 컬렉션에 쓴 뒤 이름을 바꿔 통째로 교체합니다(컬렉션 단위 원자적).
    try:

        def bulk(col, docs):
            stg = db[col + "_staging"]
            stg.drop()
            docs = list(docs)
            for i in range(0, len(docs), CHUNK):
                stg.insert_many(docs[i : i + CHUNK], ordered=False)
            return len(docs)

        log["written"] = {
            "region_stats": bulk("region_stats", regions),
            "facilities_voucher": bulk("facilities_voucher", vfac.values()),
            "courses": bulk("courses", courses.values()),
            "usage_monthly": bulk("usage_monthly", monthly),
            "facilities_all": bulk("facilities_all", afac.values()),
            "match_results": bulk("match_results", matches),
            "gap_aggregates": bulk("gap_aggregates", aggs),
        }
        report("activate", "활성 버전 전환(컬렉션 교체·인덱스)")
        for col in VERSIONED_COLLECTIONS:
            db[col + "_staging"].rename(col, dropTarget=True)
        create_indexes_sync(db, VERSIONED_COLLECTIONS)
    except Exception as e:
        db["datasets"].update_one(
            {"datasetVersion": version},
            {"$set": {"status": "failed", "error": f"{type(e).__name__}: {str(e)[:500]}"}},
        )
        for col in VERSIONED_COLLECTIONS:
            db[col + "_staging"].drop()
        raise
    db["datasets"].update_one(
        {"datasetVersion": version}, {"$set": {"status": "active", "log": log}}
    )
    prev = db["catalog_state"].find_one({"_id": "catalog"})
    db["catalog_state"].update_one(
        {"_id": "catalog"},
        {"$set": {"activeVersion": version, "updatedAt": datetime.now(UTC)}},
        upsert=True,
    )
    if prev and prev.get("activeVersion") and prev["activeVersion"] != version:
        db["datasets"].update_one(
            {"datasetVersion": prev["activeVersion"]}, {"$set": {"status": "archived"}}
        )
    log["previousVersion"] = prev.get("activeVersion") if prev else None
    return log
