#!/usr/bin/env python3
"""UC1 강좌 설명 구조화 추출을 Batch API로 제출·수집합니다.

    uv run python scripts/llm_extract_courses.py --submit --region 11110 [--limit 200]
    uv run python scripts/llm_extract_courses.py --submit --sido 11
    uv run python scripts/llm_extract_courses.py --collect <batch_id>
    uv run python scripts/llm_extract_courses.py --online --region 11110 --limit 20   # 단건 호출(시연용)

설명이 20자 미만이면 호출하지 않고 unknown으로 둡니다. 같은 (강좌, 설명 해시, 프롬프트 버전)은 재호출하지 않습니다.
결과는 course_facts(provenance=llm_extracted)에 저장되고, 검토가 필요한 항목은 review_queue에 들어갑니다.
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.llm import client as llm
from app.llm.extract import (
    MIN_DESC_CHARS,
    _facts_doc,
    build_course_batch_lines,
    extract_course_sync,
    parse_batch_line,
    postprocess_course,
    usage_from_dict,
)
from app.llm.schemas import CourseFacts


def _db():
    return llm._sync_db()


def _active_version(db) -> str:
    st = db["catalog_state"].find_one({"_id": "catalog"})
    if not st:
        raise SystemExit("활성 데이터셋이 없습니다")
    return st["activeVersion"]


def _targets(db, version, region, sido, limit):
    q = {"datasetVersion": version, "description": {"$exists": True, "$ne": ""}}
    if region:
        q["regionCode"] = region
    elif sido:
        q["sidoCode"] = sido
    done = {f["courseId"]: f.get("descriptionHash") for f in db["course_facts"].find({"datasetVersion": version, "promptVersion": llm.LLM_PROMPT_VERSION}, {"courseId": 1, "descriptionHash": 1})}
    rows = []
    for c in db["courses"].find(q, {"name": 1, "description": 1}).sort("lastMonth", -1):
        desc = c.get("description") or ""
        if len(desc.strip()) < MIN_DESC_CHARS:
            continue
        if done.get(c["_id"]) == llm.input_hash(desc):
            continue
        rows.append({"courseId": c["_id"], "name": c["name"], "description": desc})
        if limit and len(rows) >= limit:
            break
    return rows


def _store(db, version, doc, name, desc):
    doc["datasetVersion"] = version
    db["course_facts"].update_one({"datasetVersion": version, "courseId": doc["courseId"]}, {"$set": doc}, upsert=True)
    if doc.get("needsReview"):
        db["review_queue"].update_one({"_id": f"rq:extraction:{doc['courseId']}"}, {"$set": {
            "kind": "extraction", "refId": doc["courseId"], "datasetVersion": version, "status": "pending", "createdAt": datetime.now(UTC),
            "payload": {"courseName": name, "description": desc, "facts": {k: doc.get(k) for k in ("age_min", "age_max", "grade_hint", "level", "attendance_rule", "sessions_per_week", "shuttle", "voucher_note", "evidence", "confidence", "flags")}}}}, upsert=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--submit", action="store_true")
    ap.add_argument("--collect", metavar="BATCH_ID")
    ap.add_argument("--online", action="store_true")
    ap.add_argument("--region")
    ap.add_argument("--sido")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    if not llm.enabled():
        raise SystemExit("LLM 비활성: .env의 OPENAI_API_KEY, LLM_ENABLED 확인")
    db = _db()
    version = _active_version(db)
    if args.submit:
        rows = _targets(db, version, args.region, args.sido, args.limit)
        if not rows:
            print("제출할 강좌가 없습니다(모두 추출됨 또는 설명 없음)")
            return
        est = len(rows) * 0.0005
        llm.check_budget(est)
        client = llm.sync_client()
        jsonl_path = Path("data/reports") / f"batch_courses_{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}.jsonl"
        jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        jsonl_path.write_text("\n".join(build_course_batch_lines(rows)) + "\n", encoding="utf-8")
        with open(jsonl_path, "rb") as fh:
            up = client.files.create(file=fh, purpose="batch")
        batch = client.batches.create(input_file_id=up.id, endpoint="/v1/responses", completion_window="24h",
                                      metadata={"description": f"course_extract {version}"})
        db["llm_batches"].insert_one({"batchId": batch.id, "kind": "course_extract", "datasetVersion": version, "count": len(rows),
                                      "inputFileId": up.id, "jsonl": str(jsonl_path), "createdAt": datetime.now(UTC), "status": batch.status})
        print(f"batch {batch.id} 제출: {len(rows)}건 (예상 비용 ≤ {est:.2f} USD, Batch 50% 할인 전). --collect {batch.id} 로 수집하세요.")
    elif args.collect:
        client = llm.sync_client()
        b = client.batches.retrieve(args.collect)
        print("status:", b.status, "counts:", b.request_counts)
        if b.status != "completed" or not b.output_file_id:
            return
        content = client.files.content(b.output_file_id).text
        ok = err = 0
        for line in content.splitlines():
            if not line.strip():
                continue
            custom_id, facts, usage, error = parse_batch_line(line)
            cid = custom_id.removeprefix("course-")
            course = db["courses"].find_one({"_id": cid}, {"name": 1, "description": 1})
            desc = (course or {}).get("description") or ""
            if facts is None:
                err += 1
                if error == "refusal":
                    _store(db, version, _facts_doc(cid, desc, CourseFacts(), ["refusal"], llm.model_bulk(), usage_from_dict(usage)), (course or {}).get("name", ""), desc)
                continue
            facts, flags = postprocess_course(facts, desc)
            u = usage_from_dict(usage)
            doc = _facts_doc(cid, desc, facts, flags, llm.model_bulk(), u)
            llm.record_call("course_extract_batch", llm.model_bulk(), u, llm.input_hash(cid, desc), {"courseId": cid, "batchId": args.collect})
            _store(db, version, doc, (course or {}).get("name", ""), desc)
            ok += 1
        db["llm_batches"].update_one({"batchId": args.collect}, {"$set": {"status": "collected", "ok": ok, "err": err}})
        print(f"수집 완료: 성공 {ok}, 실패 {err}")
    elif args.online:
        rows = _targets(db, version, args.region, args.sido, args.limit or 20)
        for r in rows:
            doc = extract_course_sync(r["courseId"], r["name"], r["description"])
            _store(db, version, doc, r["name"], r["description"])
            print(r["courseId"], doc["confidence"], doc["attendance_rule"], doc["age_min"], doc["age_max"], doc["flags"])
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
