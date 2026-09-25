#!/usr/bin/env python3
"""UC2 시설 동일성 판정: 규칙으로 못 가른 블로킹 후보 쌍만 OpenAI 모델에 보내 same/different/unsure를 받고 검토 큐에 넣습니다.

    uv run python scripts/llm_judge_matches.py --region 11110 --limit 50
같은 인자 쌍은 재호출하지 않습니다. 'same'도 자동 확정하지 않고 검토 큐에서 승인해야 반영됩니다.
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.llm import client as llm
from app.llm.extract import judge_match_sync


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", required=True)
    ap.add_argument("--limit", type=int, default=50)
    args = ap.parse_args()
    if not llm.enabled():
        raise SystemExit("LLM 비활성")
    db = llm._sync_db()
    version = db["catalog_state"].find_one({"_id": "catalog"})["activeVersion"]
    n = 0
    for m in db["match_results"].find({"datasetVersion": version, "status": "candidates", "llmJudged": {"$ne": True}}):
        v = db["facilities_voucher"].find_one({"_id": m["voucherFacilityId"]})
        if not v or v.get("regionCode") != args.region:
            continue
        top = (m.get("candidates") or [])[:1]
        if not top:
            continue
        a = db["facilities_all"].find_one({"_id": top[0]["allFacilityId"]})
        if not a:
            continue
        verdict, _usage = judge_match_sync(v, a)
        db["match_results"].update_one({"_id": m["_id"]}, {"$set": {"llmJudged": True, "llmVerdict": verdict.model_dump(), "llmJudgedAt": datetime.now(UTC)}})
        if verdict.verdict in ("same", "unsure"):
            db["review_queue"].update_one({"_id": f"rq:match:{m['voucherFacilityId']}"}, {"$set": {
                "kind": "match", "refId": m["voucherFacilityId"], "datasetVersion": version, "status": "pending", "createdAt": datetime.now(UTC),
                "payload": {"voucherName": v["name"], "voucherAddress": v.get("address"), "candidateName": a["name"], "candidateAddress": a.get("address"),
                            "allFacilityId": a["_id"], "verdict": verdict.verdict, "reason": verdict.reason, "score": top[0].get("score")}}}, upsert=True)
        n += 1
        print(n, v["name"], "↔", a["name"], verdict.verdict, "|", verdict.reason)
        if n >= args.limit:
            break
    print("판정", n, "건")


if __name__ == "__main__":
    main()
