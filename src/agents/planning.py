"""Motor de intervalos sem LLM e sem persistência de agenda."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from .schemas import (
    AgentRequest,
    PlanningProposal,
    ProposedBlock,
    ScheduleSlot,
    Unallocated,
)


def overlaps(a, b):
    return (
        a.start.timestamp() < b.end.timestamp()
        and b.start.timestamp() < a.end.timestamp()
    )


def protected_slots(request: AgentRequest) -> list[ScheduleSlot]:
    slots = list(request.schedule_slots)
    if not request.horizon:
        return slots
    zone = ZoneInfo(request.timezone)
    day = request.horizon.start.astimezone(zone).date() - timedelta(days=1)
    last = request.horizon.end.astimezone(zone).date()
    while day <= last:
        end_day = (
            day + timedelta(days=1) if request.sleep_end < request.sleep_start else day
        )
        slots.append(
            ScheduleSlot(
                start=datetime.combine(day, request.sleep_start, zone),
                end=datetime.combine(end_day, request.sleep_end, zone),
                label="Sono protegido",
                kind="sleep",
            )
        )
        day += timedelta(days=1)
    return slots


def input_conflicts(request: AgentRequest) -> list[str]:
    slots = request.schedule_slots
    return [
        f"Compromissos fixos sobrepostos: {a.label} / {b.label} ({max(a.start, b.start).isoformat()})"
        for i, a in enumerate(slots)
        for b in slots[i + 1 :]
        if overlaps(a, b)
    ]


def plan(request: AgentRequest) -> PlanningProposal | None:
    if not request.study_goals:
        return None
    assert request.horizon is not None
    start = request.horizon.start.timestamp()
    end = request.horizon.end.timestamp()
    busy = sorted(
        (max(start, s.start.timestamp()), min(end, s.end.timestamp()))
        for s in protected_slots(request)
        if s.end.timestamp() > start and s.start.timestamp() < end
    )
    free = []
    cursor = start
    for left, right in busy:
        if left > cursor:
            free.append((cursor, left))
        cursor = max(cursor, right)
    if cursor < end:
        free.append((cursor, end))
    blocks = []
    unallocated = []
    zone = ZoneInfo(request.timezone)
    for goal in sorted(
        request.study_goals,
        key=lambda g: (g.deadline.timestamp(), -g.priority, g.goal_id),
    ):
        remaining = goal.duration_minutes * 60
        updated = []
        for left, right in free:
            available = min(right, goal.deadline.timestamp()) - left
            use = min(remaining, max(0, int(available // 60) * 60))
            point = left
            # Blocos de até 60 min; metas e intervalos são informados, nunca inferidos pelo LLM.
            while use > 0:
                duration = min(3600, use)
                blocks.append(
                    ProposedBlock(
                        goal_id=goal.goal_id,
                        title=goal.title,
                        start=datetime.fromtimestamp(point, UTC).astimezone(zone),
                        end=datetime.fromtimestamp(point + duration, UTC).astimezone(
                            zone
                        ),
                    )
                )
                point += duration
                use -= duration
                remaining -= duration
            if point < right:
                updated.append((point, right))
        free = updated
        if remaining:
            unallocated.append(
                Unallocated(goal_id=goal.goal_id, remaining_minutes=remaining // 60)
            )
    return PlanningProposal(
        proposed_blocks=blocks,
        unallocated=unallocated,
        diff_summary=f"{len(blocks)} blocos sugeridos; {len(unallocated)} objetivos com tempo pendente. Nenhuma agenda foi alterada.",
    )


def audit_plan(request: AgentRequest, proposal: PlanningProposal | None) -> list[str]:
    violations = []
    if not request.study_goals:
        return ["Planejamento inesperado"] if proposal else []
    if proposal is None or request.horizon is None:
        return ["Planejamento ausente"]
    goals = {g.goal_id: g for g in request.study_goals}
    totals = dict.fromkeys(goals, 0.0)
    slots = protected_slots(request)
    for i, block in enumerate(proposal.proposed_blocks):
        goal = goals.get(block.goal_id)
        if goal is None:
            violations.append("Objetivo desconhecido")
            continue
        seconds = block.end.timestamp() - block.start.timestamp()
        totals[block.goal_id] += seconds
        if block.title != goal.title:
            violations.append("Título de objetivo alterado")
        if (
            block.start.timestamp() < request.horizon.start.timestamp()
            or block.end.timestamp()
            > min(request.horizon.end.timestamp(), goal.deadline.timestamp())
        ):
            violations.append("Bloco fora do horizonte ou prazo")
        if any(overlaps(block, slot) for slot in slots):
            violations.append("Bloco invade sono ou compromisso fixo")
        if any(overlaps(block, other) for other in proposal.proposed_blocks[i + 1 :]):
            violations.append("Blocos sobrepostos")
    missing = {}
    for item in proposal.unallocated:
        if item.goal_id not in goals or item.goal_id in missing:
            violations.append("Pendência desconhecida ou duplicada")
        missing[item.goal_id] = item.remaining_minutes * 60
    for gid, goal in goals.items():
        if totals[gid] + missing.get(gid, 0) != goal.duration_minutes * 60:
            violations.append("Duração alocada e pendente diverge da meta")
    return list(dict.fromkeys(violations))
