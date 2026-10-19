"""UC5 문서 초안: facts JSON만 근거로 모델이 작성 → 숫자·이름 가드 → 실패 시 1회 재생성 → 반려."""

from __future__ import annotations

import json

from app.llm import client as llm
from app.services.document_service import verify_numbers_and_names


async def draft_plan_document(facts: dict, kind: str = "plan") -> dict:
    llm.check_budget(0.05)
    c = llm.async_client()
    model = llm.model_main()
    system = llm.prompt("plan_doc")
    user = f"<facts>\n{json.dumps(facts, ensure_ascii=False, indent=1)}\n</facts>\n위 facts만 근거로 협의 계획서 초안을 마크다운으로 작성하세요."
    problems: list[str] = []
    draft = ""
    total_cost = 0.0
    for attempt in range(2):
        inputs = [{"role": "user", "content": user}]
        if attempt == 1:
            inputs += [
                {"role": "assistant", "content": draft},
                {
                    "role": "user",
                    "content": "다음 값들은 facts에 없습니다: "
                    + ", ".join(problems)
                    + ". 해당 값을 제거하거나 '미확인'으로 바꿔 전체를 다시 작성하세요.",
                },
            ]
        resp = await c.responses.create(
            model=model,
            instructions=system,
            input=inputs,
            reasoning=llm.reasoning(),
            max_output_tokens=6000,
            store=False,
        )
        total_cost += llm.record_call(
            "plan_doc", model, resp.usage, llm.input_hash(user), {"attempt": attempt}
        )
        if llm.refusal_text(resp):
            return {
                "ok": False,
                "draft": None,
                "problems": ["모델이 응답을 거부했습니다"],
                "costUsd": total_cost,
            }
        draft = (resp.output_text or "").strip()
        problems = verify_numbers_and_names(draft, facts)
        if not problems:
            break
    if problems:
        return {"ok": False, "draft": None, "problems": problems, "costUsd": total_cost}
    draft = (
        f"> **자동 생성 초안({model}), 담당자 검토 전** · 데이터 버전 "
        + str(facts.get("datasetVersion"))
        + "\n\n"
        + draft
    )
    return {"ok": True, "draft": draft, "problems": [], "costUsd": total_cost}
