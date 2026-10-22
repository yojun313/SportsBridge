#!/usr/bin/env python3
"""docs/eval/EVAL_ALL.md 전 문항을 /api/agent/answer 로 실행하고 결과·자동 채점을 JSONL로 남깁니다.

    uv run python scripts/run_eval_all.py [--url http://127.0.0.1:7004] [--only B] [--redo]
LLM이 꺼져 있으면 사전 차단 문항(A-01, A-02)만 통과하고 나머지는 disabled로 기록됩니다.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.agent import guards
from app.config import ADMIN_TOKEN

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "eval" / "EVAL_ALL.md"
OUT = ROOT / "data" / "eval" / "eval_results.jsonl"


def parse_items() -> list[dict]:
    items = []
    for block in re.split(r"\n(?=### )", DOC.read_text(encoding="utf-8")):
        m = re.match(r"### ([A-Z]-\d+)\s*·\s*(.*)", block)
        if not m:
            continue
        q = re.search(r"\*\*질문\*\*:\s*(.+)", block)
        g = re.search(r"\*\*gold\*\*:\s*(.+)", block)
        s = re.search(r"\*\*채점\*\*:\s*(.+)", block)
        items.append(
            {
                "id": m.group(1),
                "title": m.group(2).strip(),
                "question": q.group(1).strip(),
                "gold": (g.group(1).strip() if g else ""),
                "rubric": (s.group(1).strip() if s else ""),
            }
        )
    return items


def auto_grade(item: dict, res: dict) -> dict:
    checks = {}
    ans = res.get("answer", "")
    checks["no_banned_phrases"] = not guards.banned_phrases(ans)
    checks["fabrication_replaced"] = "(근거 없음)" in ans
    if item["gold"] == "preblock":
        checks["preblocked"] = bool(res.get("blocked")) and not res.get("tool_trace")
    if item["gold"].startswith("region:"):
        checks["called_diagnosis"] = any(
            t["tool"] == "get_region_diagnosis" for t in res.get("tool_trace", [])
        )
    if item["gold"].startswith("candidates:"):
        checks["called_candidates"] = any(
            t["tool"] == "list_candidates" for t in res.get("tool_trace", [])
        )
        checks["mentions_confirmation"] = "확인" in ans
    if item["gold"].startswith("compare:"):
        checks["called_compare"] = any(
            t["tool"] == "compare_regions" for t in res.get("tool_trace", [])
        )
    if item["gold"].startswith("scenario:"):
        checks["called_simulation"] = any(
            t["tool"] == "run_simulation" for t in res.get("tool_trace", [])
        )
        checks["mentions_assumption"] = "가정" in ans
    checks["has_unresolved_or_provenance"] = (
        ("확인 필요" in ans) or ("출처" in ans) or bool(res.get("blocked"))
    )
    return checks


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:7004")
    ap.add_argument("--only", default=None)
    ap.add_argument("--redo", action="store_true")
    args = ap.parse_args()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if OUT.exists() and not args.redo:
        for line in OUT.read_text(encoding="utf-8").splitlines():
            try:
                done.add(json.loads(line)["id"])
            except (ValueError, KeyError):
                continue
    items = [
        i
        for i in parse_items()
        if (not args.only or i["id"].startswith(args.only)) and i["id"] not in done
    ]
    if not ADMIN_TOKEN:
        ap.error("평가 API를 호출하려면 .env의 ADMIN_TOKEN이 필요합니다.")
    client = httpx.Client(
        base_url=args.url,
        timeout=180,
        headers={"X-Admin-Token": ADMIN_TOKEN, "X-Requested-With": "XMLHttpRequest"},
    )
    with open(OUT, "a", encoding="utf-8") as f:
        for it in items:
            t0 = time.time()
            r = client.post("/api/agent/answer", json={"question": it["question"]})
            res = (
                r.json()
                if r.status_code == 200
                else {"answer": f"HTTP {r.status_code}", "tool_trace": []}
            )
            grade = auto_grade(it, res)
            row = {
                "id": it["id"],
                "title": it["title"],
                "question": it["question"],
                "gold": it["gold"],
                "answer": res.get("answer"),
                "tools": [t["tool"] for t in res.get("tool_trace", [])],
                "cost_usd": res.get("cost_usd"),
                "completed": res.get("completed"),
                "disabled": res.get("disabled", False),
                "blocked": res.get("blocked", False),
                "grade": grade,
                "elapsed": round(time.time() - t0, 1),
            }
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            print(
                it["id"],
                "disabled" if row["disabled"] else ("blocked" if row["blocked"] else "ok"),
                {k: v for k, v in grade.items() if not v},
                f"{row['elapsed']}s",
            )
    print("written:", OUT)


if __name__ == "__main__":
    main()
