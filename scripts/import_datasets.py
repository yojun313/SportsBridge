#!/usr/bin/env python3
"""원본 CSV를 MongoDB에 적재합니다.

    uv run python scripts/import_datasets.py --raw-dir data/raw --dry-run
    uv run python scripts/import_datasets.py --raw-dir data/raw
    uv run python scripts/import_datasets.py --limit 3000   # 빠른 점검용 부분 적재
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.importer import run_import


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-dir", default="data/raw")
    ap.add_argument("--version", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=None, help="파일당 최대 행 (점검용)")
    ap.add_argument("--report-dir", default="data/reports")
    args = ap.parse_args()
    t0 = time.time()
    log = run_import(Path(args.raw_dir), version=args.version, dry_run=args.dry_run, limit=args.limit)
    log["elapsedSec"] = round(time.time() - t0, 1)
    out = Path(args.report_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"import_{log['version']}.json").write_text(json.dumps(log, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps({k: v for k, v in log.items() if k != "unmappedRegions"}, ensure_ascii=False, indent=2, default=str))
    print("unmapped regions (sample):", log.get("unmappedRegions"))


if __name__ == "__main__":
    main()
