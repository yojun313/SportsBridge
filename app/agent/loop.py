"""복구 에이전트 수동 루프 (OpenAI Responses API, 함수 호출).

매 턴: 이력 압축 → 호출 → 함수 실행(반복 차단, 병렬은 같은 입력 목록에 output으로) → 이벤트.
텍스트 응답이 오면 가드 a~d를 적용하고, 한도에 닿으면 강제 마무리합니다.
store=False로 서버에 대화를 남기지 않으므로 응답 output(추론 항목 포함)을 입력 목록에 그대로 되돌립니다.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Callable
from typing import Any

from app.agent import guards
from app.agent.system_prompt import PROMPT_VERSION, SYSTEM_PROMPT, USER_SYSTEM_PROMPT
from app.agent.tools import OPENAI_TOOLS, dispatch, serialize_result
from app.config import AGENT_MAX_TURNS, AGENT_TIME_BUDGET_SECONDS
from app.llm import client as llm

logger = logging.getLogger(__name__)

_FRESH_TURNS = 2
_STALE_CHARS = 800
_FORCED = (
    "도구 호출 한도(또는 시간 한도)에 도달했습니다. 추가 도구 호출 없이 지금까지 수집된 도구 결과만으로 최종 답변을 작성하세요. "
    "확인되지 않은 것은 '확인되지 않음'이라고 적고, 확인 필요 항목과 출처 등급을 마지막에 나열하세요."
)
_STATIC_FALLBACK = "시간·도구 호출 한도 안에 답변을 완성하지 못했습니다. 질문을 더 구체적으로 나누어 다시 시도해 주세요."


def _compact(items: list[dict]) -> list[dict]:
    """오래된 function_call_output은 앞부분만 남깁니다(최근 2턴 결과는 원문 유지)."""
    idx = [i for i, m in enumerate(items) if m.get("type") == "function_call_output"]
    cutoff = idx[-_FRESH_TURNS * 3] if len(idx) > _FRESH_TURNS * 3 else -1
    out = []
    for i, m in enumerate(items):
        if (
            i < cutoff
            and m.get("type") == "function_call_output"
            and isinstance(m.get("output"), str)
            and len(m["output"]) > _STALE_CHARS
        ):
            out.append({**m, "output": m["output"][:_STALE_CHARS] + " ...(이전 턴 결과, 압축됨)"})
        else:
            out.append(m)
    return out


def _to_input_item(item) -> dict:
    """응답 output 항목(pydantic)을 다음 요청 input 항목(dict)으로."""
    if hasattr(item, "model_dump"):
        d = item.model_dump(exclude_none=True)
    else:
        d = dict(item)
    d.pop("status", None)
    return d


def _text_of(resp) -> str:
    t = getattr(resp, "output_text", None)
    if t:
        return t
    parts = []
    for item in getattr(resp, "output", []) or []:
        if getattr(item, "type", None) == "message":
            for c in getattr(item, "content", []) or []:
                if getattr(c, "type", None) == "output_text":
                    parts.append(getattr(c, "text", ""))
    return "".join(parts)


USER_TOOL_NAMES = {
    "resolve_place",
    "get_region_diagnosis",
    "compare_regions",
    "list_supply_options",
    "list_candidates",
    "get_provenance",
}


async def run_agent(
    question: str,
    hint: str,
    emit: Callable[[dict], None],
    deadline: float | None = None,
    mode: str = "admin",
) -> dict:
    client = llm.async_client()
    system_prompt = USER_SYSTEM_PROMPT if mode == "user" else SYSTEM_PROMPT
    tools = (
        [t for t in OPENAI_TOOLS if t["name"] in USER_TOOL_NAMES]
        if mode == "user"
        else OPENAI_TOOLS
    )
    model = llm.model_main()
    deadline = deadline or (time.monotonic() + AGENT_TIME_BUDGET_SECONDS)
    user_text = question + (f"\n\n[도구 힌트] {hint}" if hint else "")
    inputs: list[dict] = [{"role": "user", "content": user_text}]
    tool_log: list[dict] = []
    trace: list[str] = []
    seen_calls: dict[str, Any] = {}
    usage_total = {"input_tokens": 0, "output_tokens": 0, "cached_tokens": 0, "reasoning_tokens": 0}
    cost = 0.0
    nudges = {"fabricated": 0, "banned": 0, "giveup": 0}
    repeat_turns = 0
    completed = True
    answer = ""

    async def call_model(force_text: bool = False):
        nonlocal cost
        kwargs = {
            "model": model,
            "instructions": system_prompt,
            "input": _compact(inputs),
            "reasoning": llm.reasoning(),
            "max_output_tokens": 6000,
            "store": False,
            "tools": tools,
        }
        if force_text:
            kwargs["tool_choice"] = "none"
        resp = await client.responses.create(**kwargs)
        u = llm.usage_dict(resp.usage)
        for k in usage_total:
            usage_total[k] += u.get(k, 0)
        cost += llm.record_call(
            "agent",
            model,
            resp.usage,
            llm.input_hash(question),
            {"promptVersion": PROMPT_VERSION, "mode": mode},
        )
        emit({"type": "usage", "usage": dict(usage_total), "costUsd": round(cost, 5)})
        return resp

    for turn in range(1, AGENT_MAX_TURNS + 1):
        emit({"type": "turn", "turn": turn, "max_turns": AGENT_MAX_TURNS})
        if time.monotonic() > deadline:
            trace.append(f"[턴 {turn}] 시간 한도 → 강제 마무리")
            completed = False
            break
        llm.check_budget(0.01)
        try:
            resp = await call_model()
        except Exception as e:
            logger.exception("model call failed")
            emit({"type": "note", "level": "error", "text": f"모델 호출 실패: {type(e).__name__}"})
            return _result(_STATIC_FALLBACK, tool_log, trace, usage_total, cost, False)
        if llm.refusal_text(resp):
            emit({"type": "note", "level": "warn", "text": "모델이 응답을 거부했습니다"})
            return _result(
                "이 요청에는 응답하지 않습니다. 지역 단위 공급 공백에 관한 질문으로 다시 시도해 주세요.",
                tool_log,
                trace,
                usage_total,
                cost,
                True,
            )
        output = list(getattr(resp, "output", []) or [])
        calls = [it for it in output if getattr(it, "type", None) == "function_call"]
        inputs += [_to_input_item(it) for it in output]
        if not calls:
            candidate = _text_of(resp).strip()
            if getattr(resp, "status", None) == "incomplete":
                trace.append(f"[턴 {turn}] 출력 한도 도달")
            verdict = _guard(candidate, tool_log, nudges)
            if verdict:
                trace.append(f"[턴 {turn}] {verdict['trace']} — 재작성 요구")
                emit({"type": "guard", "text": verdict["trace"]})
                inputs.append({"role": "user", "content": verdict["nudge"]})
                continue
            answer = candidate
            emit({"type": "answer", "text": answer, "turn": turn})
            break
        emit({"type": "tool_batch", "turn": turn, "count": len(calls)})
        all_repeat = True
        for fc in calls:
            try:
                args = (
                    json.loads(fc.arguments)
                    if isinstance(fc.arguments, str)
                    else (fc.arguments or {})
                )
                if not isinstance(args, dict):
                    args = {}
            except json.JSONDecodeError:
                args = {}
            sig = guards.tool_call_signature(fc.name, args)
            emit(
                {
                    "type": "tool_call",
                    "turn": turn,
                    "tool": fc.name,
                    "input": args,
                    "id": fc.call_id,
                }
            )
            if sig in seen_calls:
                result = {
                    "repeat_warning": True,
                    "note": "같은 인자로 이미 호출했습니다. 결과는 바뀌지 않으니 조건을 바꾸거나 답변을 작성하세요.",
                }
                trace.append(f"[턴 {turn}] {fc.name} 반복 호출 차단")
            else:
                all_repeat = False
                t0 = time.monotonic()
                try:
                    result = await asyncio.wait_for(dispatch(fc.name, args), timeout=40)
                except Exception as e:
                    logger.exception("tool %s failed", fc.name)
                    result = {"error": f"{type(e).__name__}: {str(e)[:200]}"}
                seen_calls[sig] = True
                tool_log.append(
                    {
                        "turn": turn,
                        "tool": fc.name,
                        "input": args,
                        "result": result,
                        "elapsedMs": int((time.monotonic() - t0) * 1000),
                    }
                )
                trace.append(f"[턴 {turn}] {fc.name}({_short(args)}) → {_summary(result)}")
            emit(
                {
                    "type": "tool_result",
                    "id": fc.call_id,
                    "tool": fc.name,
                    "ok": not (isinstance(result, dict) and result.get("error")),
                    "summary": _summary(result),
                }
            )
            inputs.append(
                {
                    "type": "function_call_output",
                    "call_id": fc.call_id,
                    "output": serialize_result(result),
                }
            )
        repeat_turns = repeat_turns + 1 if all_repeat else 0
        if repeat_turns >= 2:
            trace.append(f"[턴 {turn}] 연속 반복 호출 → 강제 마무리")
            completed = False
            break
    else:
        completed = False
        trace.append("턴 한도 도달 → 강제 마무리")

    if not answer:
        inputs.append({"role": "user", "content": _FORCED})
        try:
            resp = await call_model(force_text=True)
            answer = _text_of(resp).strip() or _STATIC_FALLBACK
            bad = guards.fabricated_numbers(answer, tool_log)
            if bad:
                answer = guards.replace_fabricated(answer, bad)
            answer = guards.strip_banned_sentences(answer)
            emit({"type": "answer", "text": answer, "forced": True})
        except Exception:
            logger.exception("forced finish failed")
            answer = _STATIC_FALLBACK
    prov, unresolved = guards.collect_appendix(tool_log)
    answer = guards.ensure_appendix(answer, prov, unresolved)
    return _result(answer, tool_log, trace, usage_total, cost, completed, prov, unresolved)


def _guard(candidate: str, tool_log: list[dict], nudges: dict) -> dict | None:
    bad = guards.fabricated_numbers(candidate, tool_log)
    if bad and nudges["fabricated"] < 1:
        nudges["fabricated"] += 1
        return {
            "trace": f"근거 없는 숫자 감지({', '.join(bad[:6])})",
            "nudge": "답변에 도구 결과에 없는 숫자가 있습니다: "
            + ", ".join(bad[:10])
            + ". 도구 결과에 있는 값만 쓰고, 없으면 '확인되지 않음'으로 바꿔 다시 작성하세요.",
        }
    banned = guards.banned_phrases(candidate)
    if banned and nudges["banned"] < 1:
        nudges["banned"] += 1
        return {
            "trace": f"성과·확정 단정 표현 감지({', '.join(banned)})",
            "nudge": "다음 표현은 성과·확정 단정이라 쓸 수 없습니다: "
            + ", ".join(banned)
            + ". 모델상 결과와 확인 필요 조건으로 바꿔 다시 작성하세요.",
        }
    if guards.gave_up_with_results(candidate, tool_log) and nudges["giveup"] < 1:
        nudges["giveup"] += 1
        return {
            "trace": "도구 결과가 있는데 확인 불가로 마무리",
            "nudge": "이미 받은 도구 결과에 답할 수 있는 정보가 있습니다. 그 결과를 근거로 다시 작성하세요.",
        }
    return None


def _result(answer, tool_log, trace, usage, cost, completed, prov=None, unresolved=None) -> dict:
    bad = guards.fabricated_numbers(answer, tool_log)
    if bad:
        answer = guards.replace_fabricated(answer, bad)
        trace.append("최종 방어선: 근거 없는 숫자 치환 " + ", ".join(bad[:6]))
    answer = guards.strip_banned_sentences(answer) or answer
    return {
        "answer": answer,
        "tool_trace": [
            {k: v for k, v in e.items() if k != "result"} | {"summary": _summary(e["result"])}
            for e in tool_log
        ],
        "evidence": _evidence(tool_log),
        "think_trace": trace,
        "usage": usage,
        "cost_usd": round(cost, 5),
        "completed": completed,
        "provenance_summary": prov or {},
        "unresolved": unresolved or [],
    }


def _evidence(tool_log: list[dict]) -> dict:
    ev: dict = {"regions": [], "courses": [], "candidates": [], "simulation": None, "compare": None}
    for e in tool_log:
        r = e.get("result")
        if not isinstance(r, dict) or r.get("error"):
            continue
        if e["tool"] == "get_region_diagnosis":
            ev["regions"].append(
                {
                    "region": r.get("region"),
                    "axes": r.get("axes"),
                    "interpretation": r.get("interpretation"),
                }
            )
        elif e["tool"] == "list_supply_options":
            ev["courses"] = r.get("items", [])[:10]
        elif e["tool"] == "list_candidates":
            ev["candidates"] = r.get("items", [])[:10]
        elif e["tool"] == "run_simulation":
            ev["simulation"] = r
        elif e["tool"] == "compare_regions":
            ev["compare"] = r
    return ev


def _short(args: dict) -> str:
    s = json.dumps(args, ensure_ascii=False)
    return s if len(s) <= 120 else s[:117] + "..."


def _summary(result: Any) -> str:
    if isinstance(result, dict):
        if result.get("error"):
            return "오류: " + str(result["error"])[:120]
        if result.get("repeat_warning"):
            return "반복 호출 차단"
        if "regions" in result and isinstance(result["regions"], list) and "facilities" in result:
            return f"지역 후보 {len(result['regions'])}, 시설 후보 {len(result['facilities'])}"
        if "region" in result and isinstance(result["region"], dict):
            r = result["region"]
            return f"{r.get('sidoName')} {r.get('sigunguName')} 진단 (활동시설 {r.get('activeFacilityCount')}, 종목 {r.get('sportCount')})"
        if "items" in result:
            return f"{result.get('count', result.get('total', len(result['items'])))}건 중 {len(result['items'])}건"
        if "best" in result:
            b = result.get("best") or {}
            return f"조합 {result.get('evaluated')}개 평가, 최선 {b.get('actions')} → {b.get('assigned') if b.get('assigned') is not None else b.get('connectedGroups')}"
        if "scenarioJson" in result:
            return f"시나리오 생성 ({result.get('summary')})"
        if "grades" in result:
            return "출처 정의"
        if "diffFirstMinusSecond" in result:
            return f"{len(result.get('regions', []))}개 지역 비교"
    return str(result)[:120]
