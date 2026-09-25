#!/usr/bin/env python3
"""원본 CSV 10종을 검사해 data/reports/inspect_report.json·md를 만듭니다.

    uv run python scripts/inspect_datasets.py [--raw-dir data/raw] [--report-dir data/reports]

행 수·컬럼·인코딩·결측·주요 분포와 함께, 서비스 성패를 좌우하는 조인 가능성
(가맹시설↔전체시설, 이용현황↔강좌)을 실측합니다. 숫자를 미리 채우지 않습니다.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.dataset_files import FILES, find_file
from app.services.normalization_service import (
    norm_address,
    norm_name,
    norm_tel,
    parse_time_hhmm,
    parse_weekday_bits,
    sigungu5,
)

csv.field_size_limit(10**9)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_rows(path: Path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        cols = [c.strip() for c in reader.fieldnames or []]
        for row in reader:
            yield {k.strip(): (v or "").strip() for k, v in row.items() if k is not None}
    return cols


def columns(path: Path) -> list[str]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return [c.strip() for c in next(csv.reader(f))]


def top(counter: Counter, n=12):
    return [{"value": k, "count": v} for k, v in counter.most_common(n)]


def profile(key: str, path: Path, sample_cols: list[str]) -> dict:
    cols = columns(path)
    n = 0
    empty = Counter()
    dists = {c: Counter() for c in sample_cols if c in cols}
    for row in read_rows(path):
        n += 1
        for c in cols:
            if row.get(c, "") == "":
                empty[c] += 1
        for c, counter in dists.items():
            counter[row.get(c, "")] += 1
    return {
        "file": path.name,
        "sha256": sha256(path),
        "bytes": path.stat().st_size,
        "rows": n,
        "columns": cols,
        "emptyRate": {c: round(empty[c] / n, 4) if n else None for c in cols},
        "distributions": {c: top(d) for c, d in dists.items()},
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-dir", default="data/raw")
    ap.add_argument("--report-dir", default="data/reports")
    args = ap.parse_args()
    raw = Path(args.raw_dir)
    out = Path(args.report_dir)
    out.mkdir(parents=True, exist_ok=True)

    report: dict = {"files": {}, "joins": {}}
    sample_cols = {
        "regional_usage": ["BASE_YEAR", "RECIPT_FLAG_NM"],
        "voucher_facilities": ["ITEM_NM", "FCLTY_COURSE_SDIV_NM", "CTPRVN_NM"],
        "voucher_courses": ["ITEM_NM", "TRGET_YEAR", "SUPLI_SLE_AT", "WKDAY_NM"],
        "voucher_usage": ["ITEM_NM", "COURSE_ESTBL_YEAR", "CTPRVN_NM"],
        "all_facilities": ["FCLTY_STATE_VALUE", "INDUTY_NM", "FCLTY_TY_NM", "NDOR_SDIV_NM", "DEL_AT", "CTPRVN_NM"],
        "public_facilities": ["INDUTY_NM", "FCLTY_STATE_CD", "DEL_AT"],
        "open_schools": ["BASE_YEAR", "SCHUL_TY_NM"],
        "safety": ["SAFECHK_GNRLZ_GRAD_NM", "OPER_STATE_NM", "INDUTY_NM"],
        "transit_voucher": ["PBTRNSP_FCLTY_SDIV_NM", "SVCH_FCLTY_SDIV_NM"],
        "transit_public": ["PBTRNSP_FCLTY_SDIV_NM", "ALSFC_SDIV_NM"],
    }
    for key, name in FILES.items():
        path = find_file(raw, key)
        if path is None:
            report["files"][key] = {"missing": True, "file": name}
            continue
        print(f"[profile] {key} ...", flush=True)
        report["files"][key] = profile(key, path, sample_cols.get(key, []))

    # ---- 조인 검사 1: 가맹시설(80) ↔ 전체시설(64) ----
    print("[join] voucher_facilities vs all_facilities", flush=True)
    vf = list(read_rows(find_file(raw, "voucher_facilities")))
    vf_keys = {}
    vf_tel = defaultdict(set)
    for r in vf:
        k = (sigungu5(r["SIGNGU_CD"]), norm_name(r["FCLTY_NM"]), norm_address(r["FCLTY_ADDR"]))
        vf_keys[k] = r
        t = norm_tel(r["RPRSNTV_TEL_NO"])
        if t:
            vf_tel[(sigungu5(r["SIGNGU_CD"]), t)].add(k)
    vf_unique = len({(sigungu5(r["SIGNGU_CD"]), norm_name(r["FCLTY_NM"]), norm_address(r["FCLTY_ADDR"])) for r in vf})
    vf_name_region = defaultdict(set)
    for k in vf_keys:
        vf_name_region[(k[0], k[1])].add(k)

    total = exact = name_only = tel_only = 0
    state = Counter()
    for r in read_rows(find_file(raw, "all_facilities")):
        total += 1
        sg = sigungu5(r["SIGNGU_CD"])
        k = (sg, norm_name(r["FCLTY_NM"]), norm_address(r["RDNMADR_ONE_NM"] or r["FCLTY_ADDR_ONE_NM"]))
        if k in vf_keys:
            exact += 1
            state[r["FCLTY_STATE_VALUE"]] += 1
        elif (sg, k[1]) in vf_name_region:
            name_only += 1
        elif (sg, norm_tel(r["FCLTY_TEL_NO"])) in vf_tel and norm_tel(r["FCLTY_TEL_NO"]):
            tel_only += 1
    report["joins"]["voucher_vs_all_facilities"] = {
        "voucherRows": len(vf),
        "voucherUniqueFacilities": vf_unique,
        "allRows": total,
        "exactNameAddr": exact,
        "nameOnlySameSigungu": name_only,
        "telOnlySameSigungu": tel_only,
        "exactMatchedStateDist": dict(state),
        "voucherCoverageByExact": round(exact / vf_unique, 4) if vf_unique else None,
    }

    # ---- 조인 검사 2: 이용현황(05) ↔ 강좌(74) ↔ 가맹시설(80) ----
    print("[join] usage vs courses vs facilities", flush=True)
    course_rows = list(read_rows(find_file(raw, "voucher_courses")))
    cs_keys = Counter((r["ITEM_CD"], norm_name(r["COURSE_NM"])) for r in course_rows)
    cs_time_ok = sum(1 for r in course_rows if parse_time_hhmm(r["BEGIN_TIME"]) is not None and parse_time_hhmm(r["END_TIME"]) is not None)
    cs_wk_ok = sum(1 for r in course_rows if parse_weekday_bits(r["WKDAY_NM"]) is not None)
    desc_len = Counter()
    for r in course_rows:
        L = len(r["COURSE_DETAIL_CN"])
        desc_len["0" if L == 0 else "1-19" if L < 20 else "20-99" if L < 100 else "100+"] += 1
    report["files"]["voucher_courses"]["timeParseRate"] = round(cs_time_ok / len(course_rows), 4)
    report["files"]["voucher_courses"]["weekdayParseRate"] = round(cs_wk_ok / len(course_rows), 4)
    report["files"]["voucher_courses"]["descriptionLength"] = dict(desc_len)
    report["files"]["voucher_courses"]["uniqueItemCourseName"] = len(cs_keys)

    usage_fac = {}
    usage_course = {}
    usage_years = Counter()
    matched_course_rows = 0
    usage_fac_in_vf = 0
    n_usage = 0
    for r in read_rows(find_file(raw, "voucher_usage")):
        n_usage += 1
        usage_years[r["COURSE_ESTBL_YEAR"]] += 1
        fk = (sigungu5(r["SIGNGU_CD"]), norm_name(r["FCLTY_NM"]), norm_address(r["FCLTY_ADDR"]))
        if fk not in usage_fac:
            usage_fac[fk] = 1
            if fk in vf_keys:
                usage_fac_in_vf += 1
        ck = (r["ITEM_CD"], norm_name(r["COURSE_NM"]))
        if r["COURSE_NO"] not in usage_course:
            usage_course[r["COURSE_NO"]] = ck
            if ck in cs_keys:
                matched_course_rows += 1
    report["joins"]["usage_vs_courses_vs_facilities"] = {
        "usageRows": n_usage,
        "usageYears": dict(usage_years),
        "usageUniqueFacilities": len(usage_fac),
        "usageFacilitiesFoundInVoucherFacilities": usage_fac_in_vf,
        "usageUniqueCourseNo": len(usage_course),
        "usageCoursesMatchedToCourseTable(item+name)": matched_course_rows,
        "courseTableRows": len(course_rows),
    }

    # ---- 지역 코드 정합 ----
    reg = {sigungu5(r["SIGNGU_CD"]) for r in read_rows(find_file(raw, "regional_usage"))}
    vreg = {sigungu5(r["SIGNGU_CD"]) for r in vf}
    report["joins"]["region_codes"] = {
        "regionalUsageSigungu": len(reg),
        "voucherFacilitySigungu": len(vreg),
        "voucherSigunguNotInRegional": sorted(vreg - reg)[:20],
        "regionalSigunguWithoutVoucherFacility": len(reg - vreg),
    }

    (out / "inspect_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# 원본 데이터 검사 보고서", ""]
    for key, info in report["files"].items():
        if info.get("missing"):
            lines.append(f"- **{key}**: 파일 없음 ({info['file']})")
            continue
        lines.append(f"## {key} — `{info['file']}`")
        lines.append(f"- 행 {info['rows']:,} · 컬럼 {len(info['columns'])} · SHA-256 `{info['sha256'][:16]}…`")
        worst = sorted(info["emptyRate"].items(), key=lambda kv: -(kv[1] or 0))[:8]
        lines.append("- 결측 상위: " + ", ".join(f"{c} {int((v or 0)*100)}%" for c, v in worst))
        for extra in ("timeParseRate", "weekdayParseRate", "descriptionLength", "uniqueItemCourseName"):
            if extra in info:
                lines.append(f"- {extra}: {info[extra]}")
        lines.append("")
    lines.append("## 조인 검사")
    lines.append("```json")
    lines.append(json.dumps(report["joins"], ensure_ascii=False, indent=2))
    lines.append("```")
    (out / "inspect_report.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(report["joins"], ensure_ascii=False, indent=2))
    print(f"written: {out/'inspect_report.json'}, {out/'inspect_report.md'}")


if __name__ == "__main__":
    main()
