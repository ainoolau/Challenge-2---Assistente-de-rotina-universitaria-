"""Contratos Pydantic v2 compartilhados do núcleo de agenda e planejamento."""

from __future__ import annotations

from datetime import datetime, time
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Interval(Contract):
    start: datetime
    end: datetime

    @model_validator(mode="after")
    def ordered(self) -> Interval:
        if self.start.utcoffset() is None or self.end.utcoffset() is None:
            raise ValueError("Datas precisam de fuso explícito")
        if self.end.timestamp() <= self.start.timestamp():
            raise ValueError("Intervalo deve ter duração positiva")
        return self


ScheduleModality = Literal["presencial", "remoto", "hibrido"]


class ScheduleSlot(Interval):
    slot_id: str | None = Field(default=None, max_length=100)
    label: str = Field(min_length=1, max_length=200)
    kind: Literal["sleep", "work", "class", "commute", "other"] = "other"
    fixed: bool = True
    modality: ScheduleModality = "presencial"
    allow_overlap: bool = False
    buffer_before_minutes: int = Field(default=0, ge=0, le=180)
    buffer_after_minutes: int = Field(default=0, ge=0, le=180)


class StudyGoal(Contract):
    goal_id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    duration_minutes: int = Field(gt=0, le=10080)
    deadline: datetime
    priority: int = Field(default=1, ge=1, le=5)

    @field_validator("deadline")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("Prazo precisa de fuso explícito")
        return value


class ProposedBlock(Interval):
    goal_id: str
    title: str


class Unallocated(Contract):
    goal_id: str
    remaining_minutes: int = Field(gt=0)


class PlanningProposal(Contract):
    proposed_blocks: list[ProposedBlock] = Field(default_factory=list)
    unallocated: list[Unallocated] = Field(default_factory=list)
    diff_summary: str
    requires_confirmation: Literal[True] = True


class MovedBlock(Contract):
    goal_id: str
    title: str
    previous_start: datetime
    previous_end: datetime
    new_start: datetime
    new_end: datetime
    reason: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def valid_intervals(self) -> MovedBlock:
        for dt in (
            self.previous_start,
            self.previous_end,
            self.new_start,
            self.new_end,
        ):
            if dt.utcoffset() is None:
                raise ValueError("Datas precisam de fuso explícito")
        if self.previous_end.timestamp() <= self.previous_start.timestamp():
            raise ValueError("Intervalo anterior deve ter duração positiva")
        if self.new_end.timestamp() <= self.new_start.timestamp():
            raise ValueError("Novo intervalo deve ter duração positiva")
        return self


class ScheduleDiff(Contract):
    added: list[ProposedBlock] = Field(default_factory=list)
    removed: list[ProposedBlock] = Field(default_factory=list)
    moved: list[MovedBlock] = Field(default_factory=list)
    kept: list[ProposedBlock] = Field(default_factory=list)


class PlanningRequest(Contract):
    """Entrada direta do motor determinístico (reutilizada pela API FastAPI)."""

    timezone: str = "America/Sao_Paulo"
    schedule_slots: list[ScheduleSlot] = Field(default_factory=list, max_length=500)
    study_goals: list[StudyGoal] = Field(default_factory=list, max_length=50)
    horizon: Interval | None = None
    sleep_start: time = time(22)
    sleep_end: time = time(6)
    buffer_minutes: int = Field(default=0, ge=0, le=120)
    max_block_minutes: int = Field(default=60, ge=15, le=240)
    min_block_minutes: int = Field(default=1, ge=1, le=60)

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("Fuso IANA inválido") from exc
        return value

    @model_validator(mode="after")
    def planning_bounds(self) -> PlanningRequest:
        if self.study_goals and self.horizon is None:
            raise ValueError("Planejamento exige horizonte explícito")
        if (
            self.horizon
            and self.horizon.end.timestamp() - self.horizon.start.timestamp()
            > 14 * 86400
        ):
            raise ValueError("Horizonte máximo: 14 dias")
        if self.sleep_start == self.sleep_end:
            raise ValueError("Horários de sono devem ser diferentes")
        if any(t.tzinfo is not None for t in (self.sleep_start, self.sleep_end)):
            raise ValueError("Horários de sono usam o fuso do pedido")
        if self.min_block_minutes > self.max_block_minutes:
            raise ValueError("min_block_minutes não pode exceder max_block_minutes")
        ids = [g.goal_id for g in self.study_goals]
        if len(set(ids)) != len(ids):
            raise ValueError("IDs dos objetivos devem ser únicos")
        return self


class RebalanceRequest(Contract):
    """Entrada do rebalanceamento diante de imprevistos com mínima perturbação."""

    timezone: str = "America/Sao_Paulo"
    horizon: Interval
    schedule_slots: list[ScheduleSlot] = Field(default_factory=list, max_length=500)
    disruptions: list[ScheduleSlot] = Field(default_factory=list, max_length=100)
    existing_blocks: list[ProposedBlock] = Field(default_factory=list, max_length=200)
    study_goals: list[StudyGoal] = Field(default_factory=list, max_length=50)
    sleep_start: time = time(22)
    sleep_end: time = time(6)
    buffer_minutes: int = Field(default=0, ge=0, le=120)
    max_block_minutes: int = Field(default=60, ge=15, le=240)
    min_block_minutes: int = Field(default=1, ge=1, le=60)
    disruption_note: str | None = Field(default=None, max_length=500)

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("Fuso IANA inválido") from exc
        return value

    @model_validator(mode="after")
    def rebalance_bounds(self) -> RebalanceRequest:
        if self.horizon.end.timestamp() - self.horizon.start.timestamp() > 14 * 86400:
            raise ValueError("Horizonte máximo: 14 dias")
        if self.sleep_start == self.sleep_end:
            raise ValueError("Horários de sono devem ser diferentes")
        if any(t.tzinfo is not None for t in (self.sleep_start, self.sleep_end)):
            raise ValueError("Horários de sono usam o fuso do pedido")
        if self.min_block_minutes > self.max_block_minutes:
            raise ValueError("min_block_minutes não pode exceder max_block_minutes")
        ids = [g.goal_id for g in self.study_goals]
        if len(set(ids)) != len(ids):
            raise ValueError("IDs dos objetivos devem ser únicos")
        return self


class RebalanceProposal(Contract):
    """Proposta auditável de rebalanceamento (nunca aplicada automaticamente)."""

    proposed_blocks: list[ProposedBlock] = Field(default_factory=list)
    diff: ScheduleDiff
    reasons: list[str] = Field(default_factory=list)
    unallocated: list[Unallocated] = Field(default_factory=list)
    input_conflicts: list[str] = Field(default_factory=list)
    diff_summary: str
    requires_confirmation: Literal[True] = True
