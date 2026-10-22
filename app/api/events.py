"""에이전트 실행 상태와 SSE 이벤트. 실행 상태는 서버에 있어 어느 탭에서든 같은 진행을 봅니다."""

from __future__ import annotations

import asyncio
import time
import uuid
from collections import OrderedDict
from datetime import UTC, datetime
from typing import Any

_MAX_SUBSCRIBERS = 64
_MAX_QUEUE = 500
_KEEP_FINISHED = 20


class Broadcaster:
    def __init__(self) -> None:
        self._subs: list[asyncio.Queue] = []

    def subscribe(self) -> asyncio.Queue | None:
        if len(self._subs) >= _MAX_SUBSCRIBERS:
            return None
        q: asyncio.Queue = asyncio.Queue(maxsize=_MAX_QUEUE)
        self._subs.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        if q in self._subs:
            self._subs.remove(q)

    def publish(self, event: dict[str, Any]) -> None:
        for q in list(self._subs):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass


broadcaster = Broadcaster()


class RunRegistry:
    def __init__(self) -> None:
        self._runs: OrderedDict[str, dict[str, Any]] = OrderedDict()

    def create(self, question: str) -> dict[str, Any]:
        run = {
            "run_id": uuid.uuid4().hex,
            "question": question,
            "started_at": datetime.now(UTC).isoformat(),
            "started_mono": time.monotonic(),
            "status": "running",
            "events": [],
            "result": None,
        }
        self._runs[run["run_id"]] = run
        while len(self._runs) > _KEEP_FINISHED + 4:
            self._runs.popitem(last=False)
        return run

    def get(self, run_id: str) -> dict[str, Any] | None:
        return self._runs.get(run_id)

    def emit(self, run: dict[str, Any], event: dict[str, Any]) -> None:
        event = {**event, "t": round(time.monotonic() - run["started_mono"], 2)}
        if len(run["events"]) < 400:
            run["events"].append(event)
        if run.get("mode") == "admin":
            broadcaster.publish({"type": "run_event", "run_id": run["run_id"], "event": event})

    def finish(self, run: dict[str, Any], result: dict[str, Any]) -> None:
        run["status"] = "done"
        run["result"] = result
        if run.get("mode") == "admin":
            broadcaster.publish({"type": "run_done", "run_id": run["run_id"], "result": result})

    def recent(self) -> list[dict[str, Any]]:
        return [
            {
                "run_id": r["run_id"],
                "question": r["question"],
                "status": r["status"],
                "started_at": r["started_at"],
            }
            for r in reversed(self._runs.values())
        ]


registry = RunRegistry()
