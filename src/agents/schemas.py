"""Contratos independentes do benchmark da Sprint 3."""

from datetime import time
from typing import Any, Literal
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator, model_validator

from src.core.schemas import (
    Contract,
    Interval,
    MovedBlock,
    PlanningProposal,
    PlanningRequest,
    ProposedBlock,
    RebalanceProposal,
    RebalanceRequest,
    ScheduleDiff,
    ScheduleSlot,
    StudyGoal,
    Unallocated,
)

__all__ = [
    "AgentRequest",
    "AgentRunResult",
    "AnalysisNotes",
    "Claim",
    "Contract",
    "EvidenceChunk",
    "EvidenceFact",
    "Interval",
    "MovedBlock",
    "PlanningProposal",
    "PlanningRequest",
    "ProposalDraft",
    "ProposedBlock",
    "RebalanceProposal",
    "RebalanceRequest",
    "ResearchNotes",
    "RetrievalResult",
    "RunMetrics",
    "ScheduleDiff",
    "ScheduleSlot",
    "StudyGoal",
    "TraceEvent",
    "Unallocated",
    "ValidationNotes",
    "ValidationResult",
]


class AgentRequest(Contract):
    run_id: str = Field(
        default_factory=lambda: "multiagent-" + uuid4().hex,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$",
    )
    question: str = Field(min_length=5, max_length=4000)
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
    def valid_timezone(cls, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("Fuso IANA inválido") from exc
        return value

    @model_validator(mode="after")
    def planning_bounds(self):
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


class EvidenceChunk(Contract):
    source_id: str
    source: str
    chunk_index: int | None = None
    text: str = Field(min_length=1, max_length=20000)
    score: float = Field(ge=-1, le=1)
    task_type: str | None = None
    title: str | None = None
    page_or_time: str | None = None


class EvidenceFact(Contract):
    statement: str = Field(min_length=1, max_length=2000)
    source_id: str
    quote: str = Field(min_length=1, max_length=2000)


class ResearchNotes(Contract):
    additional_queries: list[str] = Field(default_factory=list, max_length=2)
    facts: list[EvidenceFact] = Field(max_length=20)
    gaps: list[str] = Field(max_length=20)


class RetrievalResult(Contract):
    rounds: list[dict[str, Any]] = Field(default_factory=list)
    queries: list[str] = Field(default_factory=list)
    abstained: bool
    top_score: float | None
    chunks: list[EvidenceChunk]
    citations: list[str] = Field(default_factory=list)
    verified_facts: list[EvidenceFact] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    needs_review: bool = True


class Claim(Contract):
    text: str = Field(min_length=1, max_length=2000)
    source_ids: list[str] = Field(min_length=1, max_length=5)


class AnalysisNotes(Contract):
    claims: list[Claim] = Field(max_length=20)
    limitations: list[str] = Field(max_length=10)


class ProposalDraft(Contract):
    claims: list[Claim]
    limitations: list[str]
    answer: str
    planning: PlanningProposal | None = None


class ValidationNotes(Contract):
    factual_ok: bool
    violations: list[str] = Field(max_length=30)
    corrections_needed: list[str] = Field(max_length=30)


class ValidationResult(Contract):
    valid: bool
    factual_ok: bool
    invariants_ok: bool
    violations: list[str]
    corrections_needed: list[str]
    attempt: int = Field(ge=0, le=1)


class TraceEvent(Contract):
    step: int
    agent: str
    attempt: int
    status: Literal["success", "error"]
    input: dict[str, Any]
    output: dict[str, Any]
    latency_ms: float = Field(ge=0)


class RunMetrics(Contract):
    total_latency_ms: float = Field(ge=0)
    llm_calls: int = Field(ge=0)
    input_tokens: int | None
    output_tokens: int | None


class AgentRunResult(Contract):
    contract_version: Literal["1.0.0"] = "1.0.0"
    run_id: str
    request: AgentRequest
    status: Literal["completed", "abstained", "error"]
    mode: Literal["live", "simulated"]
    config: dict[str, Any]
    retrieval: RetrievalResult | None
    proposal: ProposalDraft | None
    validation: ValidationResult | None
    final_answer: str
    trace: list[TraceEvent]
    metrics: RunMetrics
    error: dict[str, str] | None = None
