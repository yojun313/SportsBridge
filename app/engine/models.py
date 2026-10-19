"""시나리오 데이터 모델 (Pydantic). 출처 등급을 값마다 붙입니다."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

Provenance = Literal["public", "rule", "llm_extracted", "llm_reviewed", "confirmed", "assumed"]


class TimeWindow(BaseModel):
    weekday: int = Field(ge=0, le=6)
    startMinute: int = Field(ge=0, le=1440)
    endMinute: int = Field(ge=0, le=1440)

    @field_validator("endMinute")
    @classmethod
    def _end_after_start(cls, v, info):
        if "startMinute" in info.data and v <= info.data["startMinute"]:
            raise ValueError("endMinute는 startMinute보다 커야 합니다")
        return v


class DemandGroup(BaseModel):
    id: str = Field(min_length=1, max_length=40)
    label: str = Field(min_length=1, max_length=80)
    sport: str = Field(min_length=1, max_length=40)
    size: int = Field(ge=1, le=500)
    availability: list[TimeWindow] = Field(default_factory=list, max_length=56)
    sessionsPerWeek: int | None = Field(default=None, ge=1, le=7)
    ageMin: int | None = Field(default=None, ge=3, le=100)
    ageMax: int | None = Field(default=None, ge=3, le=100)
    bufferMinutes: int = Field(default=0, ge=0, le=120)
    transport: Literal["walk", "own_vehicle", "needs_support"] = "walk"
    originFacilityId: str | None = None  # 이동 조건 계산용 기준 시설(선택)
    provenance: Provenance = "confirmed"


class Session(BaseModel):
    weekday: int = Field(ge=0, le=6)
    startMinute: int = Field(ge=0, le=1440)
    endMinute: int = Field(ge=0, le=1440)


class SupplyOption(BaseModel):
    """공급 옵션: 기존 가맹 강좌 또는 신설 가능한 강좌 슬롯."""

    id: str = Field(min_length=1, max_length=60)
    label: str = Field(min_length=1, max_length=120)
    facilityId: str = Field(min_length=1, max_length=60)
    facilityName: str = Field(default="", max_length=120)
    sport: str = Field(min_length=1, max_length=40)
    sessions: list[Session] = Field(default_factory=list, max_length=14)
    attendanceRule: Literal["all_required", "selectable", "unknown"] = "unknown"
    ageMin: int | None = None
    ageMax: int | None = None
    capacity: int | None = Field(default=None, ge=0, le=1000)
    capacityProvenance: Provenance = "assumed"
    voucherAffiliated: bool | None = None  # None = 미확인
    affiliationProvenance: Provenance = "public"
    priceWon: int | None = None
    exists: bool = True  # False면 조치로 신설되어야 하는 슬롯
    reachable: dict[str, bool] = Field(
        default_factory=dict
    )  # demandGroupId → 이동 가능 여부 (확인·가정)
    provenance: Provenance = "public"


class Action(BaseModel):
    """개선 조치. kind별 효과:
    affiliate: facilityId 시설을 가맹 처리 → 그 시설의 옵션이 이용권 사용 가능
    open_course: supplyOptionId 슬롯을 신설(exists=True) + capacity 부여
    add_capacity: supplyOptionId 정원 증가
    transport: demandGroupId ↔ facilityId 이동 가능 처리
    """

    id: str = Field(min_length=1, max_length=40)
    label: str = Field(min_length=1, max_length=120)
    kind: Literal["affiliate", "open_course", "add_capacity", "transport"]
    facilityId: str | None = None
    supplyOptionId: str | None = None
    demandGroupId: str | None = None
    capacity: int | None = Field(default=None, ge=0, le=1000)
    costWon: int | None = Field(default=None, ge=0, le=1_000_000_000)
    costProvenance: Provenance = "assumed"
    requires: list[str] = Field(default_factory=list, max_length=10)
    conflicts: list[str] = Field(default_factory=list, max_length=10)
    leadWeeks: int | None = Field(default=None, ge=0, le=52)
    provenance: Provenance = "assumed"


class Scenario(BaseModel):
    id: str = Field(default="local", max_length=60)
    title: str = Field(default="", max_length=120)
    regionCode: str = Field(min_length=5, max_length=5)
    sport: str | None = None
    demandGroups: list[DemandGroup] = Field(min_length=1, max_length=10)
    supplyOptions: list[SupplyOption] = Field(default_factory=list, max_length=30)
    actions: list[Action] = Field(default_factory=list, max_length=10)
    budgetWon: int | None = Field(default=None, ge=0, le=10_000_000_000)
    mode: Literal["structure", "capacity"] = "capacity"
    datasetVersion: str | None = None
    notes: str = Field(default="", max_length=2000)

    @field_validator("demandGroups")
    @classmethod
    def _unique_ids(cls, v):
        ids = [g.id for g in v]
        if len(ids) != len(set(ids)):
            raise ValueError("수요 집단 id가 중복됩니다")
        return v
