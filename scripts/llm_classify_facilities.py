#!/usr/bin/env python3
"""UC3 시설 업종·아동 적합성 분류: 규칙이 unknown으로 둔 후보 시설만 OpenAI 모델(gpt-5.6-luna)로 보강합니다.

    uv run python scripts/llm_classify_facilities.py --region 11110 --limit 50
결과는 facility_class(provenance=llm_extracted)에 저장하고, 후보 화면에서는 규칙 판정 옆에 참고로 표시합니다.
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.llm import client as llm
from app.llm.extract import classify_facility_sync


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", required=True)
    ap.add_argument("--limit", type=int, default=50)
    args = ap.parse_args()
    if not llm.enabled():
        raise SystemExit("LLM 비활성")
    db = llm._sync_db()
    version = db["catalog_state"].find_one({"_id": "catalog"})["activeVersion"]
    done = {d["facilityId"] for d in db["facility_class"].find({"datasetVersion": version}, {"facilityId": 1})}
    n = 0
    for f in db["facilities_all"].find({"datasetVersion": version, "regionCode": args.region, "voucherMatch": None, "childSuitability": "unknown", "status": "정상운영"}):
        if f["_id"] in done:
            continue
        cls, _usage = classify_facility_sync(f)
        db["facility_class"].update_one({"datasetVersion": version, "facilityId": f["_id"]}, {"$set": {
            "datasetVersion": version, "facilityId": f["_id"], **cls.model_dump(), "provenance": "llm_extracted", "promptVersion": llm.LLM_PROMPT_VERSION,
            "createdAt": datetime.now(UTC)}}, upsert=True)
        n += 1
        print(n, f["name"], cls.child_suitability, cls.sports, cls.confidence)
        if n >= args.limit:
            break
    print("분류", n, "건")


if __name__ == "__main__":
    main()
