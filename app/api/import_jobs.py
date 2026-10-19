"""데이터 재적재 작업 상태. 서버에 하나만 두어 어느 브라우저에서 접속해도 같은 진행률을 봅니다.

적재는 동기 함수(run_import)를 워커 스레드에서 돌리고, 단계마다 progress 콜백으로 상태를 갱신하며
SSE 브로드캐스터에도 이벤트를 보냅니다(스레드에서 이벤트 루프로 안전하게 전달).
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.api.events import broadcaster

logger = logging.getLogger(__name__)

STEPS = [
    ("hash", "원본 파일 확인·해시", 3),
    ("regions", "지역(표준 코드) 적재", 5),
    ("voucher_facilities", "가맹시설 병합", 12),
    ("courses", "강좌·이용현황 결합", 30),
    ("all_facilities", "전체 체육시설·안전점검·대중교통", 60),
    ("voucher_transit", "가맹시설 대중교통", 68),
    ("matching", "가맹↔전체 시설 매칭", 78),
    ("aggregates", "시군구 집계", 84),
    ("write", "MongoDB 기록", 97),
    ("activate", "활성 버전 전환", 100),
]
STEP_PCT = {k: p for k, _, p in STEPS}
STEP_LABEL = {k: l for k, l, _ in STEPS}


class ImportJob:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.state: dict[str, Any] = {
            "status": "idle",
            "percent": 0,
            "step": None,
            "stepLabel": None,
            "message": None,
            "startedAt": None,
            "finishedAt": None,
            "version": None,
            "log": [],
            "error": None,
            "elapsedSec": 0,
        }
        self._loop: asyncio.AbstractEventLoop | None = None
        self._t0 = 0.0

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            s = dict(self.state)
            if s["status"] == "running":
                s["elapsedSec"] = round(time.monotonic() - self._t0, 1)
            s["log"] = list(s["log"])[-40:]
            return s

    def _emit(self, event: dict[str, Any]) -> None:
        if self._loop is None:
            return
        try:
            self._loop.call_soon_threadsafe(
                broadcaster.publish, {"type": "import_progress", **event}
            )
        except RuntimeError:
            pass

    def progress(
        self, step: str, message: str = "", percent: int | None = None, extra: dict | None = None
    ) -> None:
        with self.lock:
            self.state["step"] = step
            self.state["stepLabel"] = STEP_LABEL.get(step, step)
            self.state["percent"] = (
                percent if percent is not None else STEP_PCT.get(step, self.state["percent"])
            )
            self.state["message"] = message
            self.state["log"].append(
                {
                    "t": round(time.monotonic() - self._t0, 1),
                    "step": step,
                    "label": STEP_LABEL.get(step, step),
                    "message": message,
                    **(extra or {}),
                }
            )
            snap = dict(self.state)
        self._emit(
            {
                "status": snap["status"],
                "percent": snap["percent"],
                "step": step,
                "stepLabel": snap["stepLabel"],
                "message": message,
                "elapsedSec": round(time.monotonic() - self._t0, 1),
            }
        )

    def start(self, raw_dir: Path, loop: asyncio.AbstractEventLoop) -> bool:
        with self.lock:
            if self.state["status"] == "running":
                return False
            self.state.update(
                {
                    "status": "running",
                    "percent": 0,
                    "step": None,
                    "stepLabel": None,
                    "message": "시작",
                    "startedAt": datetime.now(UTC).isoformat(),
                    "finishedAt": None,
                    "version": None,
                    "log": [],
                    "error": None,
                }
            )
            self._loop = loop
            self._t0 = time.monotonic()
        self._emit(
            {
                "status": "running",
                "percent": 0,
                "step": None,
                "stepLabel": "시작",
                "message": "적재를 시작합니다",
                "elapsedSec": 0,
            }
        )
        threading.Thread(target=self._run, args=(raw_dir,), daemon=True, name="import-job").start()
        return True

    def _run(self, raw_dir: Path) -> None:
        from app.services.importer import run_import

        try:
            log = run_import(raw_dir, progress=self.progress)
            with self.lock:
                self.state.update(
                    {
                        "status": "done",
                        "percent": 100,
                        "step": "activate",
                        "stepLabel": STEP_LABEL["activate"],
                        "message": f"완료 · 버전 {log['version']}",
                        "finishedAt": datetime.now(UTC).isoformat(),
                        "version": log["version"],
                        "elapsedSec": round(time.monotonic() - self._t0, 1),
                        "summary": log.get("steps"),
                    }
                )
            self._emit(
                {
                    "status": "done",
                    "percent": 100,
                    "step": "activate",
                    "stepLabel": "완료",
                    "message": f"버전 {log['version']} 활성화",
                    "elapsedSec": round(time.monotonic() - self._t0, 1),
                    "version": log["version"],
                }
            )
        except Exception as e:
            logger.exception("import job failed")
            with self.lock:
                self.state.update(
                    {
                        "status": "failed",
                        "message": f"실패: {type(e).__name__}: {str(e)[:300]}",
                        "error": f"{type(e).__name__}: {str(e)[:500]}",
                        "finishedAt": datetime.now(UTC).isoformat(),
                        "elapsedSec": round(time.monotonic() - self._t0, 1),
                    }
                )
            self._emit(
                {
                    "status": "failed",
                    "percent": self.state["percent"],
                    "step": self.state["step"],
                    "stepLabel": "실패",
                    "message": self.state["message"],
                    "elapsedSec": self.state["elapsedSec"],
                }
            )


job = ImportJob()
