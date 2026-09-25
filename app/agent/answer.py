"""질문 → 답변 파이프라인. 어떤 실패도 예외로 새지 않고 유효한 결과를 돌려줍니다."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime

from app.agent import guards
from app.agent.loop import run_agent
from app.config import LLM_ENABLED
from app.llm import client as llm

logger = logging.getLogger(__name__)


async def answer_question(question: str, emit: Callable[[dict], None] | None = None, mode: str = "admin") -> dict:
    emit = emit or (lambda e: None)
    q = guards.sanitize(question)
    base = {"question": q, "mode": mode, "created_at": datetime.now(UTC).isoformat()}
    blocked = guards.preblock(q)
    if blocked:
        emit({"type": "note", "level": "info", "text": "사전 차단 (도구·모델 호출 없음)"})
        return {**base, "answer": blocked, "tool_trace": [], "evidence": {}, "think_trace": ["사전 차단"], "usage": {}, "cost_usd": 0.0,
                "completed": True, "provenance_summary": {}, "unresolved": [], "blocked": True}
    if not LLM_ENABLED:
        return {**base, "answer": "질문 기능은 OpenAI API 키가 설정되어야 동작합니다(.env의 OPENAI_API_KEY, LLM_ENABLED=true). 다른 화면은 키 없이도 쓸 수 있습니다.",
                "tool_trace": [], "evidence": {}, "think_trace": ["LLM 비활성"], "usage": {}, "cost_usd": 0.0, "completed": False, "provenance_summary": {}, "unresolved": [], "disabled": True}
    hint = guards.build_hint(q)
    if hint:
        emit({"type": "note", "level": "info", "text": "힌트: " + hint})
    try:
        res = await run_agent(q, hint, emit, mode=mode)
    except llm.BudgetExceeded as e:
        return {**base, "answer": str(e), "tool_trace": [], "evidence": {}, "think_trace": ["예산 한도"], "usage": {}, "cost_usd": 0.0, "completed": False, "provenance_summary": {}, "unresolved": []}
    except Exception as e:
        logger.exception("agent failed")
        return {**base, "answer": "답변 생성 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.", "tool_trace": [], "evidence": {}, "think_trace": [f"오류 {type(e).__name__}"], "usage": {}, "cost_usd": 0.0, "completed": False, "provenance_summary": {}, "unresolved": []}
    return {**base, **res}
