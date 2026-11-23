"""Contratos Pydantic v2 (DTOs) da API FastAPI do Vezo."""

from __future__ import annotations

from datetime import datetime, time
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator, model_validator

from src.core.schemas import (
    Contract,
    Interval,
    PlanningProposal,
    ProposedBlock,
    RebalanceProposal,
    ScheduleSlot,
    StudyGoal,
)

ScheduleItemKind = Literal["sleep", "work", "class", "commute", "study", "other"]


class HealthResponse(Contract):
    status: Literal["ok"] = "ok"
    version: str = "0.1.0"
    db_ok: bool = True
    qdrant_configured: bool = False
    qdrant_ok: bool = False
    llm_configured: bool = False


class SessionPreferences(Contract):
    timezone: str = "America/Sao_Paulo"
    sleep_start: time = time(22)
    sleep_end: time = time(6)
    buffer_minutes: int = Field(default=0, ge=0, le=120)
    max_block_minutes: int = Field(default=60, ge=15, le=240)
    min_block_minutes: int = Field(default=1, ge=1, le=60)
    consent_accepted: bool = False
    consent_timestamp: str | None = None

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("Fuso IANA inválido") from exc
        return value

    @model_validator(mode="after")
    def valid_bounds(self) -> SessionPreferences:
        if self.sleep_start == self.sleep_end:
            raise ValueError("Horários de sono devem ser diferentes")
        if any(t.tzinfo is not None for t in (self.sleep_start, self.sleep_end)):
            raise ValueError("Horários de sono usam o fuso da sessão")
        if self.min_block_minutes > self.max_block_minutes:
            raise ValueError("min_block_minutes não pode exceder max_block_minutes")
        return self


class SessionCreateRequest(Contract):
    timezone: str = "America/Sao_Paulo"
    sleep_start: time = time(22)
    sleep_end: time = time(6)
    buffer_minutes: int = Field(default=0, ge=0, le=120)
    max_block_minutes: int = Field(default=60, ge=15, le=240)
    min_block_minutes: int = Field(default=1, ge=1, le=60)
    consent_accepted: bool = False

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("Fuso IANA inválido") from exc
        return value

    @model_validator(mode="after")
    def valid_bounds(self) -> SessionCreateRequest:
        if self.sleep_start == self.sleep_end:
            raise ValueError("Horários de sono devem ser diferentes")
        if any(t.tzinfo is not None for t in (self.sleep_start, self.sleep_end)):
            raise ValueError("Horários de sono usam o fuso da sessão")
        if self.min_block_minutes > self.max_block_minutes:
            raise ValueError("min_block_minutes não pode exceder max_block_minutes")
        return self


class PreferencesUpdateRequest(Contract):
    timezone: str | None = None
    sleep_start: time | None = None
    sleep_end: time | None = None
    buffer_minutes: int | None = Field(default=None, ge=0, le=120)
    max_block_minutes: int | None = Field(default=None, ge=15, le=240)
    min_block_minutes: int | None = Field(default=None, ge=1, le=60)
    consent_accepted: bool | None = None

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("Fuso IANA inválido") from exc
        return value


class SessionResponse(Contract):
    session_id: str
    session_token: str | None = None
    schedule_version: int = Field(ge=1)
    preferences: SessionPreferences
    created_at: str
    auth_note: str = (
        "Sessão de MVP com token opaco (cookie HttpOnly / X-Session-Token); "
        "não substitui autenticação completa de produção."
    )


class ScheduleItemCreate(Interval):
    label: str = Field(min_length=1, max_length=200)
    kind: ScheduleItemKind = "other"
    fixed: bool = True
    goal_id: str | None = Field(default=None, max_length=100)
    buffer_before_minutes: int = Field(default=0, ge=0, le=180)
    buffer_after_minutes: int = Field(default=0, ge=0, le=180)


class ScheduleItemUpdate(Contract):
    start: datetime | None = None
    end: datetime | None = None
    label: str | None = Field(default=None, min_length=1, max_length=200)
    kind: ScheduleItemKind | None = None
    fixed: bool | None = None
    goal_id: str | None = Field(default=None, max_length=100)
    buffer_before_minutes: int | None = Field(default=None, ge=0, le=180)
    buffer_after_minutes: int | None = Field(default=None, ge=0, le=180)


class ScheduleItemResponse(Interval):
    item_id: str
    label: str
    kind: ScheduleItemKind
    fixed: bool
    goal_id: str | None = None
    buffer_before_minutes: int = 0
    buffer_after_minutes: int = 0
    created_at: str
    updated_at: str


class ScheduleListResponse(Contract):
    schedule_version: int = Field(ge=1)
    preferences: SessionPreferences
    items: list[ScheduleItemResponse] = Field(default_factory=list)
    input_conflicts: list[str] = Field(default_factory=list)
    free_windows: list[Interval] = Field(default_factory=list)


class OptimizeScheduleRequest(Contract):
    horizon: Interval
    study_goals: list[StudyGoal] = Field(min_length=1, max_length=50)
    buffer_minutes: int | None = Field(default=None, ge=0, le=120)
    max_block_minutes: int | None = Field(default=None, ge=15, le=240)
    min_block_minutes: int | None = Field(default=None, ge=1, le=60)


class ReallocateScheduleRequest(Contract):
    horizon: Interval
    disruptions: list[ScheduleSlot] = Field(default_factory=list, max_length=100)
    study_goals: list[StudyGoal] = Field(default_factory=list, max_length=50)
    disruption_note: str | None = Field(default=None, max_length=500)
    buffer_minutes: int | None = Field(default=None, ge=0, le=120)
    max_block_minutes: int | None = Field(default=None, ge=15, le=240)
    min_block_minutes: int | None = Field(default=None, ge=1, le=60)


class ScheduleProposalResponse(Contract):
    proposal_id: str
    proposal_type: Literal["optimize", "reallocate", "chat"]
    status: Literal["pending", "confirmed", "rejected"]
    base_version: int = Field(ge=1)
    requires_confirmation: Literal[True] = True
    planning: PlanningProposal | None = None
    rebalance: RebalanceProposal | None = None
    input_conflicts: list[str] = Field(default_factory=list)
    created_at: str


class ProposalActionResponse(Contract):
    proposal_id: str
    status: Literal["confirmed", "rejected"]
    schedule_version: int = Field(ge=1)
    applied_blocks: list[ProposedBlock] = Field(default_factory=list)
    items_count: int = Field(ge=0)
    message: str


class ChatQueryRequest(Contract):
    question: str = Field(min_length=5, max_length=4000)
    horizon: Interval | None = None
    study_goals: list[StudyGoal] = Field(default_factory=list, max_length=50)
    include_session_schedule: bool = True


class CitationItem(Contract):
    source_id: str
    source: str
    title: str | None = None
    page_or_time: str | None = None
    text: str
    score: float
    task_type: str | None = None


class ChatQueryResponse(Contract):
    run_id: str
    status: Literal["completed", "abstained", "error"]
    abstained: bool
    answer: str
    citations: list[CitationItem] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    input_conflicts: list[str] = Field(default_factory=list)
    planning: PlanningProposal | None = None
    proposal_id: str | None = None
    requires_confirmation: Literal[True] = True
    llm_calls: int = Field(default=0, ge=0)
    total_latency_ms: float = Field(default=0.0, ge=0.0)


class ChatHistoryMessage(Contract):
    message_id: str
    role: Literal["user", "assistant"]
    content: str
    abstained: bool | None = None
    proposal_id: str | None = None
    citations: list[CitationItem] = Field(default_factory=list)
    created_at: str
