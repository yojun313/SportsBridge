"""LLM 호출 전후의 코드 가드.

사전 차단: 개인 식별·자격 판정 요구, 빈 질문. 힌트 라우터: 질문 키워드 → 짧은 도구 힌트.
후검증: 답변의 숫자·고유명사가 도구 결과에 있는지, 성과 단정 표현, provenance/unresolved 부록.
"""

from __future__ import annotations

import json
import re
from typing import Any

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
MAX_QUESTION_CHARS = 2000

_PII_RE = re.compile(
    r"(주민등록번호|주민번호|생년월일|집\s*주소|전화번호를?\s*알려|아이\s*이름|아동\s*명단|누가\s*수급|수급자\s*명단|어느\s*가구|특정\s*아동|개인정보)"
)
_ELIG_RE = re.compile(
    r"(자격이?\s*(되|돼|있)|지원\s*대상(자)?\s*(인지|이야|입니까|이니|맞)|수급\s*자격|받을\s*수\s*있(나|어|는지|을까))"
)
_META_RE = re.compile(r"(시스템\s*프롬프트|너의\s*(지침|규칙)|이전\s*지시|규칙\s*무시|무시하고)")

PREBLOCK = {
    "pii": "특정 아동·가구를 식별하거나 개인정보를 다루는 요청에는 응답하지 않습니다. 이 도구는 시군구 단위 통계와 공개 시설 정보만 다룹니다.",
    "eligibility": "개인의 스포츠강좌이용권 지원 자격은 이 도구가 판정하지 않습니다. 공식 사이트(svoucher.kspo.or.kr) 또는 주민센터에서 확인하세요. 지역 단위 공급 공백 질문은 도와드릴 수 있습니다.",
    "meta": "저는 스포츠강좌이용권 공급 공백을 진단하고 후보·조치 조합을 계산하는 담당자용 에이전트입니다. 지역이나 시설, 수요 조건을 말씀해 주세요.",
}

# 성과·확정 단정 표현. 문장 단위로 제거하거나 재작성 요구.
_BANNED = re.compile(
    r"(참여율이?\s*(오를|상승할|높아질)|예산이?\s*절감|가맹(이|될)\s*(확정|것입니다|될\s*것)|가장\s*안전한|확실히\s*(효과|성공)|반드시\s*(늘|증가)|보장)"
)
_ASSERT_WORDS = re.compile(r"(충분합니다|부족합니다)")

HINTS = [
    (re.compile(r"저녁|야간|퇴근|18시|19시|20시"), "eveningOnly=true로 강좌를 보세요."),
    (re.compile(r"주말|토요일|일요일"), "주말 세션(weekday 5,6)만 골라 말하세요."),
    (
        re.compile(r"초등|저학년|고학년|유아|중학"),
        "연령 조건은 AI추출·검토완료 값만 근거로 쓰고, 없으면 확인 필요로 두세요.",
    ),
    (re.compile(r"비교|vs|보다|어디가"), "compare_regions를 쓰세요."),
    (
        re.compile(r"몇\s*명|인원|아이들|수요|예산|만\s*원"),
        "수요·예산이 있으면 build_scenario → run_simulation.",
    ),
    (
        re.compile(r"가맹\s*안|비가맹|후보|유치|어느\s*시설"),
        "list_candidates를 쓰고 '가맹 여부 확인 필요'를 명시하세요.",
    ),
]
SPORT_WORDS = [
    "수영",
    "태권도",
    "헬스",
    "축구",
    "풋살",
    "복싱",
    "필라테스",
    "댄스",
    "발레",
    "무용",
    "줄넘기",
    "농구",
    "야구",
    "검도",
    "유도",
    "합기도",
    "요가",
    "주짓수",
    "배드민턴",
    "탁구",
]


def sanitize(q: str) -> str:
    q = _CONTROL.sub("", q or "").strip()
    return q[:MAX_QUESTION_CHARS]


def preblock(q: str) -> str | None:
    if not q:
        return "질문을 입력해 주세요. 예: '종로구에서 초등학생이 저녁에 갈 수 있는 수영 강좌가 왜 적어?'"
    if _PII_RE.search(q):
        return PREBLOCK["pii"]
    if _ELIG_RE.search(q) and not re.search(r"지역|시군구|구\b|시\b|군\b", q):
        return PREBLOCK["eligibility"]
    # 지침·규칙을 캐묻는 것만 차단합니다. "규칙 무시하고 종로구 진단…"처럼 실제 질문이 섞여 있으면
    # 모델이 도구 결과로 답하게 두고, 주입 지시는 시스템 프롬프트가 데이터로 취급합니다.
    if _META_RE.search(q) and not re.search(
        r"(구|시|군|지역|시군구|시설|강좌|수영|태권도|후보|진단)", q
    ):
        return PREBLOCK["meta"]
    return None


def build_hint(q: str) -> str:
    hints = [h for rx, h in HINTS if rx.search(q)]
    sports = [s for s in SPORT_WORDS if s in q]
    if sports:
        hints.append(f"종목 필터: {sports[0]}.")
    text = " ".join(hints)
    return text[:200]


# ---- 후검증
_NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")


def allowed_numbers_from_tools(tool_log: list[dict]) -> set[str]:
    nums: set[str] = set()
    for entry in tool_log:
        text = json.dumps(entry.get("result"), ensure_ascii=False, default=str)
        for m in _NUM_RE.findall(text):
            nums.add(m)
            nums.add(m.replace(",", ""))
            # 정수는 천단위 구분 표기도 허용
            if m.replace(",", "").isdigit():
                nums.add(f"{int(m.replace(',', '')):,}")
        # 백분율 변환: 0.1304 → 13, 13.0
        for m in re.findall(r"0\.\d{2,4}", text):
            pct = float(m) * 100
            nums.add(str(round(pct)))
            nums.add(f"{pct:.1f}".rstrip("0").rstrip("."))
            nums.add(f"{pct:.2f}".rstrip("0").rstrip("."))
    for i in range(32):
        nums.add(str(i))
    return nums


def fabricated_numbers(answer: str, tool_log: list[dict]) -> list[str]:
    allowed = allowed_numbers_from_tools(tool_log)
    bad = []
    # 시각 표기(16:00) 및 연도(2026)는 허용
    scrubbed = re.sub(r"\d{1,2}:\d{2}", "", answer)
    scrubbed = re.sub(r"20\d{2}[-년.]?\s*\d{0,2}", "", scrubbed)
    for m in _NUM_RE.findall(scrubbed):
        if m not in allowed and m.replace(",", "") not in allowed:
            bad.append(m)
    return sorted(set(bad))


def banned_phrases(answer: str) -> list[str]:
    return sorted(
        {m.group(0) for m in _BANNED.finditer(answer)}
        | {m.group(0) for m in _ASSERT_WORDS.finditer(answer)}
    )


def strip_banned_sentences(answer: str) -> str:
    out = []
    for sent in re.split(r"(?<=[.!?。])\s+|\n", answer):
        if _BANNED.search(sent) or _ASSERT_WORDS.search(sent):
            continue
        out.append(sent)
    return "\n".join(s for s in out if s.strip())


def replace_fabricated(answer: str, bad: list[str]) -> str:
    for b in sorted(bad, key=len, reverse=True):
        answer = re.sub(r"(?<![\d,.])" + re.escape(b) + r"(?![\d,.])", "(근거 없음)", answer)
    return answer


def collect_appendix(tool_log: list[dict]) -> tuple[dict, list[str]]:
    prov: dict[str, int] = {}
    unresolved: list[str] = []
    for entry in tool_log:
        r = entry.get("result")
        if isinstance(r, dict):
            for k, v in (r.get("provenance_summary") or {}).items():
                if isinstance(v, int):
                    prov[k] = prov.get(k, 0) + v
            for u in r.get("unresolved") or []:
                if isinstance(u, str) and u not in unresolved:
                    unresolved.append(u)
    return prov, unresolved[:12]


def ensure_appendix(answer: str, prov: dict, unresolved: list[str]) -> str:
    has_unres = any(u[:12] in answer for u in unresolved) or "확인 필요" in answer
    add = []
    if unresolved and not has_unres:
        add.append("확인 필요: " + "; ".join(unresolved))
    if prov and "출처" not in answer:
        add.append("출처 등급: " + ", ".join(f"{k} {v}" for k, v in prov.items()))
    if add:
        answer = answer.rstrip() + "\n\n" + "\n".join(add)
    return answer


def gave_up_with_results(answer: str, tool_log: list[dict]) -> bool:
    has_data = any(
        isinstance(e.get("result"), dict) and not e["result"].get("error") for e in tool_log
    )
    return (
        has_data
        and bool(re.search(r"(확인할 수 없|데이터가 없|알 수 없습니다)", answer))
        and len(answer) < 200
    )


def tool_call_signature(name: str, args: dict[str, Any]) -> str:
    return name + ":" + json.dumps(args, ensure_ascii=False, sort_keys=True)
