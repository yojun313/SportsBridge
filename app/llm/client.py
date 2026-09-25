"""OpenAI 클라이언트 1곳. 모델·비용 한도·호출 기록을 여기서만 관리합니다.

키가 없으면 LLM_ENABLED=false이고, 모든 호출은 LLMDisabled를 던집니다.
Responses API를 씁니다. 프롬프트 캐싱은 자동(1,024토큰 이상 접두)이며 usage.input_tokens_details.cached_tokens로 확인합니다.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime

from app.config import (
    LLM_DAILY_BUDGET_USD,
    LLM_ENABLED,
    LLM_MODEL_BULK,
    LLM_MODEL_MAIN,
    LLM_PROMPT_VERSION,
    LLM_REASONING_EFFORT,
    OPENAI_API_KEY,
)
from app.core.paths import PROMPTS_DIR

logger = logging.getLogger(__name__)

# 2026-09 기준 1M 토큰당 USD (입력, 캐시 읽기, 출력). 모델 추가 시 여기만 고칩니다.
PRICES = {
    "gpt-5.6-luna": (0.20, 0.02, 1.20),
    "gpt-5.6-terra": (2.00, 0.20, 12.00),
    "gpt-5.6-sol": (4.00, 0.40, 20.00),
    "gpt-6-astra": (10.00, 1.00, 50.00),
    "gpt-5.4-nano": (0.20, 0.02, 1.25),
}


class LLMDisabled(RuntimeError):
    pass


class BudgetExceeded(RuntimeError):
    pass


_client = None
_async_client = None


def enabled() -> bool:
    return LLM_ENABLED


def sync_client():
    global _client
    if not LLM_ENABLED:
        raise LLMDisabled("LLM이 비활성 상태입니다 (.env의 OPENAI_API_KEY, LLM_ENABLED 확인)")
    if _client is None:
        from openai import OpenAI
        _client = OpenAI(api_key=OPENAI_API_KEY, max_retries=3)
    return _client


def async_client():
    global _async_client
    if not LLM_ENABLED:
        raise LLMDisabled("LLM이 비활성 상태입니다 (.env의 OPENAI_API_KEY, LLM_ENABLED 확인)")
    if _async_client is None:
        from openai import AsyncOpenAI
        _async_client = AsyncOpenAI(api_key=OPENAI_API_KEY, max_retries=3)
    return _async_client


def prompt(name: str) -> str:
    p = PROMPTS_DIR / f"{name}_{LLM_PROMPT_VERSION}.txt"
    if not p.exists():
        p = max(PROMPTS_DIR.glob(f"{name}_v*.txt"))
    return p.read_text(encoding="utf-8").strip()


def reasoning() -> dict:
    return {"effort": LLM_REASONING_EFFORT}


def input_hash(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:24]


def usage_dict(usage) -> dict:
    if usage is None:
        return {"input_tokens": 0, "output_tokens": 0, "cached_tokens": 0, "reasoning_tokens": 0}
    inp_d = getattr(usage, "input_tokens_details", None)
    out_d = getattr(usage, "output_tokens_details", None)
    return {
        "input_tokens": getattr(usage, "input_tokens", 0) or 0,
        "output_tokens": getattr(usage, "output_tokens", 0) or 0,
        "cached_tokens": (getattr(inp_d, "cached_tokens", 0) or 0) if inp_d else 0,
        "reasoning_tokens": (getattr(out_d, "reasoning_tokens", 0) or 0) if out_d else 0,
    }


def cost_usd(model: str, usage) -> float:
    pin, pcache, pout = PRICES.get(model, (0.20, 0.02, 1.20))
    u = usage_dict(usage)
    uncached = max(0, u["input_tokens"] - u["cached_tokens"])
    return (uncached * pin + u["cached_tokens"] * pcache + u["output_tokens"] * pout) / 1_000_000


# ---- 사용량 기록 (동기 pymongo: 스크립트·요청 어디서든 짧게)
def _sync_db():
    from pymongo import MongoClient

    from app.config import DB_NAME, MONGO_URI
    return MongoClient(MONGO_URI)[DB_NAME]


def record_call(kind: str, model: str, usage, ihash: str, extra: dict | None = None) -> float:
    c = cost_usd(model, usage)
    try:
        _sync_db()["llm_calls"].insert_one({"kind": kind, "model": model, "inputHash": ihash, "promptVersion": LLM_PROMPT_VERSION,
                                            "usage": usage_dict(usage), "costUsd": c, "createdAt": datetime.now(UTC), **(extra or {})})
    except Exception:
        logger.warning("llm_calls 기록 실패", exc_info=True)
    return c


def today_spend_usd() -> float:
    try:
        start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        agg = list(_sync_db()["llm_calls"].aggregate([{"$match": {"createdAt": {"$gte": start}}}, {"$group": {"_id": None, "s": {"$sum": "$costUsd"}}}]))
        return float(agg[0]["s"]) if agg else 0.0
    except Exception:  # noqa: BLE001
        return 0.0


def check_budget(estimated_usd: float = 0.0) -> None:
    spent = today_spend_usd()
    if spent + estimated_usd > LLM_DAILY_BUDGET_USD:
        raise BudgetExceeded(f"오늘 LLM 비용 {spent:.2f} USD가 한도 {LLM_DAILY_BUDGET_USD} USD에 도달했습니다")


def model_main() -> str:
    return LLM_MODEL_MAIN


def model_bulk() -> str:
    return LLM_MODEL_BULK


# ---- Responses API 응답 해석 도우미
def refusal_text(response) -> str | None:
    """구조화 출력이 거부됐으면 거부 문구를, 아니면 None."""
    for item in getattr(response, "output", []) or []:
        if getattr(item, "type", None) != "message":
            continue
        for c in getattr(item, "content", []) or []:
            if getattr(c, "type", None) == "refusal":
                return getattr(c, "refusal", "") or "refusal"
    return None


def strict_schema(model_cls) -> dict:
    """Pydantic 모델을 OpenAI strict JSON 스키마로 (Batch 요청 본문용)."""
    from openai.lib._pydantic import to_strict_json_schema
    return to_strict_json_schema(model_cls)
