import asyncio
import json
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.agent.answer import answer_question
from app.api.events import broadcaster, registry
from app.core.serialize import jsonable
from app.db import agent_history_col
from app.services import catalog_service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["agent"])

_cache: dict[str, dict] = {}


class AskBody(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    mode: str = Field(default="admin", pattern="^(admin|user)$")


async def _run_and_store(question: str, run: dict | None, mode: str = "admin") -> dict:
    v = await catalog_service.active_version()
    key = f"{v}|{mode}|{question.strip()}"
    if key in _cache:
        res = _cache[key]
        if run:
            registry.emit(run, {"type": "note", "level": "info", "text": "같은 질문의 이전 답변을 재사용"})
            registry.finish(run, res)
        return res
    emit = (lambda e: registry.emit(run, e)) if run else None
    res = await answer_question(question, emit, mode)
    res["dataset_version"] = v
    if res.get("completed") and not res.get("blocked") and not res.get("disabled"):
        _cache[key] = res
    try:
        await agent_history_col.insert_one({**json.loads(json.dumps(jsonable(res), default=str)), "createdAt": datetime.now(UTC)})
    except Exception:
        logger.warning("agent_history 저장 실패", exc_info=True)
    if run:
        registry.finish(run, jsonable(res))
    return res


@router.post("/api/agent/answer")
async def answer(body: AskBody):
    return jsonable(await _run_and_store(body.question, None, body.mode))


@router.post("/runs")
async def start_run(body: AskBody):
    run = registry.create(body.question)
    run["mode"] = body.mode
    asyncio.create_task(_run_and_store(body.question, run, body.mode))
    return {"run_id": run["run_id"], "status": "running"}


@router.get("/runs/{run_id}")
async def get_run(run_id: str):
    run = registry.get(run_id)
    if not run:
        raise HTTPException(404, "실행을 찾을 수 없습니다")
    return jsonable({k: v for k, v in run.items() if k != "started_mono"})


@router.get("/events")
async def events(request: Request):
    q = broadcaster.subscribe()
    if q is None:
        raise HTTPException(503, "구독자 한도 초과")

    async def gen():
        try:
            yield "event: hello\ndata: {}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    ev = await asyncio.wait_for(q.get(), timeout=15)
                    yield f"data: {json.dumps(jsonable(ev), ensure_ascii=False, default=str)}\n\n"
                except TimeoutError:
                    yield ": ping\n\n"
        finally:
            broadcaster.unsubscribe(q)
    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/history")
async def history(limit: int = Query(20, ge=1, le=100), mode: str = Query("admin", max_length=10)):
    out = []
    async for d in agent_history_col.find({"mode": mode} if mode == "user" else {"mode": {"$ne": "user"}}, {"_id": 0, "question": 1, "answer": 1, "created_at": 1, "cost_usd": 1, "completed": 1, "tool_trace": 1, "unresolved": 1, "provenance_summary": 1, "evidence": 1, "think_trace": 1}).sort("createdAt", -1).limit(limit):
        out.append(d)
    return jsonable({"items": out, "running": registry.recent()})
