"""UC1 강좌 설명 구조화 추출 + UC2 매칭 판정 + UC3 시설 분류. 온라인 단건(Responses API parse)과 Batch(JSONL)."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from app.llm import client as llm
from app.llm.schemas import CourseFacts, FacilityClass, MatchVerdict

logger = logging.getLogger(__name__)
MIN_DESC_CHARS = 20


def course_user_message(name: str, description: str) -> str:
    return f"<course>\n강좌명: {name}\n설명: {description}\n</course>"


def evidence_ok(facts: CourseFacts, description: str) -> bool:
    return all(e.strip() and e.strip() in description for e in facts.evidence)


def postprocess_course(facts: CourseFacts, description: str) -> tuple[CourseFacts, list[str]]:
    flags = []
    if not evidence_ok(facts, description):
        flags.append("evidence_not_in_text")
        facts = facts.model_copy(update={"confidence": "low"})
    if facts.age_min is not None and facts.age_max is not None and facts.age_min > facts.age_max:
        flags.append("age_range_inverted")
        facts = facts.model_copy(update={"confidence": "low"})
    return facts, flags


def _parse(model_cls, system: str, user: str, model: str, max_tokens: int):
    c = llm.sync_client()
    resp = c.responses.parse(
        model=model,
        instructions=system,
        input=[{"role": "user", "content": user}],
        text_format=model_cls,
        reasoning=llm.reasoning(),
        max_output_tokens=max_tokens,
        store=False,
    )
    return resp


def extract_course_sync(
    course_id: str, name: str, description: str, model: str | None = None
) -> dict:
    """온라인 단건 추출. 결과 dict는 course_facts 문서 형태."""
    model = model or llm.model_bulk()
    if len(description.strip()) < MIN_DESC_CHARS:
        return _facts_doc(
            course_id, description, CourseFacts(), ["description_too_short"], model, None
        )
    llm.check_budget(0.002)
    resp = _parse(
        CourseFacts,
        llm.prompt("course_extract"),
        course_user_message(name, description),
        model,
        2048,
    )
    if llm.refusal_text(resp) or resp.output_parsed is None:
        return _facts_doc(course_id, description, CourseFacts(), ["refusal"], model, resp.usage)
    facts, flags = postprocess_course(resp.output_parsed, description)
    llm.record_call(
        "course_extract",
        model,
        resp.usage,
        llm.input_hash(course_id, description),
        {"courseId": course_id},
    )
    return _facts_doc(course_id, description, facts, flags, model, resp.usage)


def _facts_doc(
    course_id: str, description: str, facts: CourseFacts, flags: list[str], model: str, usage
) -> dict:
    needs_review = (
        facts.confidence == "low"
        or bool(flags)
        or facts.attendance_rule != "unknown"
        or facts.age_min is not None
    )
    return {
        "courseId": course_id,
        "descriptionHash": llm.input_hash(description),
        "promptVersion": llm.LLM_PROMPT_VERSION,
        "model": model,
        **facts.model_dump(),
        "flags": flags,
        "provenance": "llm_extracted",
        "needsReview": needs_review,
        "extractedAt": datetime.now(UTC),
        "usage": llm.usage_dict(usage) if usage else None,
    }


# ---- Batch (JSONL, /v1/responses)
def build_course_batch_lines(rows: list[dict], model: str | None = None) -> list[str]:
    model = model or llm.model_bulk()
    schema = llm.strict_schema(CourseFacts)
    system = llm.prompt("course_extract")
    lines = []
    for r in rows:
        body = {
            "model": model,
            "instructions": system,
            "input": [
                {"role": "user", "content": course_user_message(r["name"], r["description"])}
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "CourseFacts",
                    "schema": schema,
                    "strict": True,
                }
            },
            "reasoning": llm.reasoning(),
            "max_output_tokens": 2048,
            "store": False,
        }
        lines.append(
            json.dumps(
                {
                    "custom_id": f"course-{r['courseId']}",
                    "method": "POST",
                    "url": "/v1/responses",
                    "body": body,
                },
                ensure_ascii=False,
            )
        )
    return lines


def parse_batch_line(line: str) -> tuple[str, CourseFacts | None, dict | None, str | None]:
    """결과 JSONL 한 줄 → (custom_id, facts|None, usage|None, error|None)."""
    row = json.loads(line)
    cid = row.get("custom_id", "")
    if row.get("error") or not row.get("response") or row["response"].get("status_code") != 200:
        return (
            cid,
            None,
            None,
            json.dumps(row.get("error") or row.get("response"), ensure_ascii=False)[:300],
        )
    body = row["response"]["body"]
    text = None
    for item in body.get("output", []):
        if item.get("type") != "message":
            continue
        for c in item.get("content", []):
            if c.get("type") == "refusal":
                return cid, None, body.get("usage"), "refusal"
            if c.get("type") == "output_text":
                text = c.get("text")
    if not text:
        return cid, None, body.get("usage"), "no_text"
    try:
        return cid, CourseFacts.model_validate_json(text), body.get("usage"), None
    except Exception as e:  # noqa: BLE001
        return cid, None, body.get("usage"), f"parse:{type(e).__name__}"


class _Usage:
    """dict usage → 속성 접근용 어댑터 (record_call/usage_dict 호환)."""

    def __init__(self, d: dict | None):
        d = d or {}
        self.input_tokens = d.get("input_tokens", 0)
        self.output_tokens = d.get("output_tokens", 0)
        itd = d.get("input_tokens_details") or {}
        otd = d.get("output_tokens_details") or {}
        self.input_tokens_details = type("X", (), {"cached_tokens": itd.get("cached_tokens", 0)})()
        self.output_tokens_details = type(
            "Y", (), {"reasoning_tokens": otd.get("reasoning_tokens", 0)}
        )()


def usage_from_dict(d: dict | None):
    return _Usage(d)


# ---- UC2 매칭 판정
def judge_match_sync(
    voucher: dict, candidate: dict, model: str | None = None
) -> tuple[MatchVerdict, dict]:
    model = model or llm.model_bulk()
    llm.check_budget(0.002)
    payload = {
        "A_가맹시설": {
            k: voucher.get(k) for k in ("name", "address", "detailAddress", "tel", "sports")
        },
        "B_전체시설": {
            k: candidate.get(k) for k in ("name", "address", "tel", "category", "facilityType")
        },
    }
    resp = _parse(
        MatchVerdict,
        llm.prompt("match_judge"),
        "<records>\n" + json.dumps(payload, ensure_ascii=False) + "\n</records>",
        model,
        512,
    )
    if llm.refusal_text(resp) or resp.output_parsed is None:
        return MatchVerdict(verdict="unsure", reason="refusal"), llm.usage_dict(resp.usage)
    llm.record_call(
        "match_judge", model, resp.usage, llm.input_hash(json.dumps(payload, ensure_ascii=False))
    )
    return resp.output_parsed, llm.usage_dict(resp.usage)


# ---- UC3 시설 분류
def classify_facility_sync(fac: dict, model: str | None = None) -> tuple[FacilityClass, dict]:
    model = model or llm.model_bulk()
    llm.check_budget(0.001)
    payload = {k: fac.get(k) for k in ("name", "category", "facilityType", "flag")}
    resp = _parse(
        FacilityClass,
        llm.prompt("facility_class"),
        "<facility>\n" + json.dumps(payload, ensure_ascii=False) + "\n</facility>",
        model,
        400,
    )
    if llm.refusal_text(resp) or resp.output_parsed is None:
        return FacilityClass(), llm.usage_dict(resp.usage)
    llm.record_call(
        "facility_class", model, resp.usage, llm.input_hash(json.dumps(payload, ensure_ascii=False))
    )
    return resp.output_parsed, llm.usage_dict(resp.usage)
