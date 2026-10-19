"""LLM 구조화 출력 스키마 (Pydantic). 원문에 없는 값은 null/unknown."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class CourseFacts(BaseModel):
    age_min: int | None = Field(None, description="설명에 명시된 최소 연령(만). 없으면 null")
    age_max: int | None = Field(None, description="설명에 명시된 최대 연령(만). 없으면 null")
    grade_hint: str | None = Field(
        None, description="초등 저학년/고학년/중학생/성인 등 원문 표현 그대로"
    )
    level: Literal["beginner", "intermediate", "advanced", "mixed", "unknown"] = "unknown"
    attendance_rule: Literal["all_required", "selectable", "unknown"] = Field(
        "unknown", description="표기 요일 전부 출석 필수인지, 그중 선택인지"
    )
    sessions_per_week: int | None = Field(None, description="주당 수업 횟수가 명시되면")
    shuttle: Literal["yes", "no", "unknown"] = "unknown"
    voucher_note: str | None = Field(
        None, description="이용권 사용 조건·본인부담 언급이 있으면 원문 요약"
    )
    evidence: list[str] = Field(
        default_factory=list, description="각 판단의 근거가 된 원문 문장. 원문에 없는 문장 금지"
    )
    confidence: Literal["high", "medium", "low"] = "low"


class MatchVerdict(BaseModel):
    verdict: Literal["same", "different", "unsure"]
    reason: str = Field(description="한 문장. 이름·주소·전화·업종 중 무엇이 근거인지")
    conflicting_fields: list[str] = Field(default_factory=list)


class FacilityClass(BaseModel):
    sports: list[str] = Field(
        default_factory=list, description="이 시설에서 운영할 법한 종목(이용권 종목명 기준)"
    )
    child_suitability: Literal["likely", "unlikely", "unknown"] = "unknown"
    confidence: Literal["high", "medium", "low"] = "low"
    reason: str = ""
