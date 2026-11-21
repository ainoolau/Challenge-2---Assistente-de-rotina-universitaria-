"""Motor determinístico compartilhado de janelas, otimização e rebalanceamento.

Sem LLM, sem efeitos colaterais e sem persistência direta de agenda.
Todas as propostas exigem confirmação explícita (`requires_confirmation=True`).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, time, timedelta
from typing import Protocol
from zoneinfo import ZoneInfo

from .schemas import (
    Interval,
    MovedBlock,
    PlanningProposal,
    ProposedBlock,
    RebalanceProposal,
    RebalanceRequest,
    ScheduleDiff,
    ScheduleSlot,
    StudyGoal,
    Unallocated,
)


class PlanningContext(Protocol):
    """Contrato estrutural aceito por `plan`, `audit_plan`, `protected_slots` e `free_windows`."""

    timezone: str
    schedule_slots: list[ScheduleSlot]
    study_goals: list[StudyGoal]
    horizon: Interval | None
    sleep_start: time
    sleep_end: time
    buffer_minutes: int
    max_block_minutes: int
    min_block_minutes: int


def overlaps(a: Interval, b: Interval) -> bool:
    """Retorna True se dois intervalos possuem interseção estritamente positiva."""
    return (
        a.start.timestamp() < b.end.timestamp()
        and b.start.timestamp() < a.end.timestamp()
    )


def _overlaps_ts(a_start: float, a_end: float, b_start: float, b_end: float) -> bool:
    return a_start < b_end and b_start < a_end


def expand_sleep_slots(
    *,
    horizon: Interval | None,
    timezone: str,
    sleep_start: time,
    sleep_end: time,
) -> list[ScheduleSlot]:
    """Expande a janela recorrente de sono protegido no fuso IANA (inclui virada e DST)."""
    if horizon is None:
        return []
    zone = ZoneInfo(timezone)
    slots: list[ScheduleSlot] = []
    day = horizon.start.astimezone(zone).date() - timedelta(days=1)
    last = horizon.end.astimezone(zone).date()
    while day <= last:
        end_day = day + timedelta(days=1) if sleep_end < sleep_start else day
        slots.append(
            ScheduleSlot(
                start=datetime.combine(day, sleep_start, zone),
                end=datetime.combine(end_day, sleep_end, zone),
                label="Sono protegido",
                kind="sleep",
                fixed=True,
            )
        )
        day += timedelta(days=1)
    return slots


def protected_slots(request: PlanningContext) -> list[ScheduleSlot]:
    """Combina compromissos fixos informados com o sono protegido expandido no horizonte."""
    slots = list(request.schedule_slots)
    slots.extend(
        expand_sleep_slots(
            horizon=request.horizon,
            timezone=request.timezone,
            sleep_start=request.sleep_start,
            sleep_end=request.sleep_end,
        )
    )
    return slots


def _effective_blocked_bounds(
    slot: ScheduleSlot, global_buffer_minutes: int
) -> tuple[float, float]:
    """Retorna intervalo bloqueado (em segundos epoch) incluindo buffers de eventos fixos."""
    if slot.kind == "sleep":
        return slot.start.timestamp(), slot.end.timestamp()
    before_sec = max(global_buffer_minutes, slot.buffer_before_minutes) * 60
    after_sec = max(global_buffer_minutes, slot.buffer_after_minutes) * 60
    return slot.start.timestamp() - before_sec, slot.end.timestamp() + after_sec


def detect_input_conflicts(slots: list[ScheduleSlot]) -> list[str]:
    """Detecta conflitos pré-existentes entre compromissos fixos sem movê-los."""
    return [
        f"Compromissos fixos sobrepostos: {a.label} / {b.label} ({max(a.start, b.start).isoformat()})"
        for i, a in enumerate(slots)
        for b in slots[i + 1 :]
        if overlaps(a, b)
    ]


def input_conflicts(request: PlanningContext) -> list[str]:
    """Detecta conflitos entre compromissos fixos informados na requisição."""
    return detect_input_conflicts(request.schedule_slots)


def _subtract_intervals(
    horizon_start: float,
    horizon_end: float,
    busy_intervals: list[tuple[float, float]],
) -> list[tuple[float, float]]:
    """Subtrai intervalos ocupados do horizonte retornando janelas livres ordenadas."""
    clipped = sorted(
        (max(horizon_start, left), min(horizon_end, right))
        for left, right in busy_intervals
        if right > horizon_start and left < horizon_end
    )
    free: list[tuple[float, float]] = []
    cursor = horizon_start
    for left, right in clipped:
        if left > cursor:
            free.append((cursor, left))
        cursor = max(cursor, right)
    if cursor < horizon_end:
        free.append((cursor, horizon_end))
    return free


def free_windows(
    request: PlanningContext,
    *,
    extra_busy: list[tuple[float, float]] | None = None,
) -> list[Interval]:
    """Detecta janelas livres reais no horizonte descontando sono, fixos e buffers."""
    if request.horizon is None:
        return []
    global_buffer = getattr(request, "buffer_minutes", 0)
    busy = [
        _effective_blocked_bounds(slot, global_buffer)
        for slot in protected_slots(request)
    ]
    if extra_busy:
        busy.extend(extra_busy)
    raw_windows = _subtract_intervals(
        request.horizon.start.timestamp(),
        request.horizon.end.timestamp(),
        busy,
    )
    zone = ZoneInfo(request.timezone)
    return [
        Interval(
            start=datetime.fromtimestamp(left, UTC).astimezone(zone),
            end=datetime.fromtimestamp(right, UTC).astimezone(zone),
        )
        for left, right in raw_windows
        if right > left
    ]


def _allocate_goals_into_windows(
    goals: list[StudyGoal],
    free: list[tuple[float, float]],
    *,
    timezone: str,
    buffer_minutes: int,
    max_block_minutes: int,
    min_block_minutes: int,
) -> tuple[list[ProposedBlock], list[Unallocated]]:
    """Aloca metas em blocos determinísticos respeitando prazo, prioridade, duração e buffers."""
    blocks: list[ProposedBlock] = []
    unallocated: list[Unallocated] = []
    zone = ZoneInfo(timezone)
    buffer_sec = buffer_minutes * 60
    max_sec = max_block_minutes * 60
    min_sec = min_block_minutes * 60

    current_free = list(free)
    for goal in sorted(
        goals,
        key=lambda g: (g.deadline.timestamp(), -g.priority, g.goal_id),
    ):
        remaining = goal.duration_minutes * 60
        goal_min_sec = min(min_sec, remaining)
        deadline_ts = goal.deadline.timestamp()
        updated: list[tuple[float, float]] = []

        for left, right in current_free:
            if remaining <= 0:
                updated.append((left, right))
                continue

            point = left
            placed_here = False
            while remaining > 0:
                available_raw = min(right, deadline_ts) - point
                available = max(0, int(available_raw // 60) * 60)
                if available < goal_min_sec:
                    break

                if remaining <= max_sec and available >= remaining:
                    duration = remaining
                elif remaining < 2 * goal_min_sec:
                    # Não é possível dividir sem gerar bloco abaixo de `min_block_minutes`.
                    if available < remaining:
                        break
                    duration = remaining
                else:
                    candidate = min(max_sec, available, remaining)
                    leftover = remaining - candidate
                    if 0 < leftover < goal_min_sec:
                        candidate = remaining - goal_min_sec
                    if candidate < goal_min_sec:
                        break
                    duration = candidate

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
                remaining -= duration
                point += duration + buffer_sec
                placed_here = True

            if placed_here:
                if point < right:
                    updated.append((point, right))
            else:
                updated.append((left, right))

        current_free = updated
        if remaining > 0:
            unallocated.append(
                Unallocated(goal_id=goal.goal_id, remaining_minutes=remaining // 60)
            )

    return blocks, unallocated


def plan(request: PlanningContext) -> PlanningProposal | None:
    """Gera proposta determinística de blocos de estudo sem alterar a agenda."""
    if not request.study_goals:
        return None
    assert request.horizon is not None
    global_buffer = getattr(request, "buffer_minutes", 0)
    max_block = getattr(request, "max_block_minutes", 60)
    min_block = getattr(request, "min_block_minutes", 1)

    busy = [
        _effective_blocked_bounds(slot, global_buffer)
        for slot in protected_slots(request)
    ]
    free = _subtract_intervals(
        request.horizon.start.timestamp(),
        request.horizon.end.timestamp(),
        busy,
    )
    blocks, unallocated = _allocate_goals_into_windows(
        request.study_goals,
        free,
        timezone=request.timezone,
        buffer_minutes=global_buffer,
        max_block_minutes=max_block,
        min_block_minutes=min_block,
    )
    return PlanningProposal(
        proposed_blocks=blocks,
        unallocated=unallocated,
        diff_summary=(
            f"{len(blocks)} blocos sugeridos; {len(unallocated)} objetivos com "
            "tempo pendente. Nenhuma agenda foi alterada."
        ),
    )


def audit_plan(
    request: PlanningContext, proposal: PlanningProposal | None
) -> list[str]:
    """Audita deterministicamente todas as invariantes do planejamento proposto."""
    violations: list[str] = []
    if not request.study_goals:
        return ["Planejamento inesperado"] if proposal else []
    if proposal is None or request.horizon is None:
        return ["Planejamento ausente"]

    global_buffer = getattr(request, "buffer_minutes", 0)
    max_block_sec = getattr(request, "max_block_minutes", 60) * 60
    min_block_sec = getattr(request, "min_block_minutes", 1) * 60
    buffer_sec = global_buffer * 60

    goals = {g.goal_id: g for g in request.study_goals}
    totals = dict.fromkeys(goals, 0.0)
    slots = protected_slots(request)
    buffered_bounds = [
        (slot, *_effective_blocked_bounds(slot, global_buffer)) for slot in slots
    ]

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
        if seconds > max_block_sec:
            violations.append("Bloco excede duração máxima configurada")
        if seconds < min(min_block_sec, goal.duration_minutes * 60):
            violations.append("Bloco abaixo da duração mínima configurada")

        b_start, b_end = block.start.timestamp(), block.end.timestamp()
        for slot, eff_start, eff_end in buffered_bounds:
            if overlaps(block, slot):
                violations.append("Bloco invade sono ou compromisso fixo")
            elif _overlaps_ts(b_start, b_end, eff_start, eff_end):
                violations.append("Bloco invade buffer de compromisso fixo")

        for other in proposal.proposed_blocks[i + 1 :]:
            if overlaps(block, other):
                violations.append("Blocos sobrepostos")
            elif buffer_sec > 0:
                gap = max(
                    other.start.timestamp() - b_end,
                    b_start - other.end.timestamp(),
                )
                if gap < buffer_sec:
                    violations.append("Buffer entre blocos de estudo violado")

    missing: dict[str, int] = {}
    for item in proposal.unallocated:
        if item.goal_id not in goals or item.goal_id in missing:
            violations.append("Pendência desconhecida ou duplicada")
        missing[item.goal_id] = item.remaining_minutes * 60

    for gid, goal in goals.items():
        if totals[gid] + missing.get(gid, 0) != goal.duration_minutes * 60:
            violations.append("Duração alocada e pendente diverge da meta")

    return list(dict.fromkeys(violations))


def _resolve_rebalance_goals(request: RebalanceRequest) -> dict[str, StudyGoal]:
    """Garante que cada `goal_id` presente em `existing_blocks` ou `study_goals` tenha meta."""
    goals = {g.goal_id: g for g in request.study_goals}
    grouped_durations: dict[str, int] = defaultdict(int)
    grouped_titles: dict[str, str] = {}
    for block in request.existing_blocks:
        if block.goal_id not in goals:
            minutes = int(round((block.end.timestamp() - block.start.timestamp()) / 60))
            grouped_durations[block.goal_id] += max(1, minutes)
            grouped_titles.setdefault(block.goal_id, block.title)

    for gid, total_minutes in grouped_durations.items():
        goals[gid] = StudyGoal(
            goal_id=gid,
            title=grouped_titles[gid],
            duration_minutes=total_minutes,
            deadline=request.horizon.end,
            priority=1,
        )
    return goals


def _diagnose_block_conflict(
    block: ProposedBlock,
    *,
    goal: StudyGoal,
    horizon: Interval,
    sleep_slots: list[ScheduleSlot],
    disruptions: list[ScheduleSlot],
    fixed_slots: list[ScheduleSlot],
    kept: list[ProposedBlock],
    buffer_minutes: int,
) -> str | None:
    """Retorna motivo objetivo caso o bloco existente não possa ser mantido intacto."""
    b_start = block.start.timestamp()
    b_end = block.end.timestamp()
    if b_start < horizon.start.timestamp() or b_end > min(
        horizon.end.timestamp(), goal.deadline.timestamp()
    ):
        return "Bloco original fora do horizonte ou após o prazo da meta"

    for sleep in sleep_slots:
        if overlaps(block, sleep):
            return "Bloco original invadia janela de sono protegido"

    for disruption in disruptions:
        eff_start, eff_end = _effective_blocked_bounds(disruption, buffer_minutes)
        if _overlaps_ts(b_start, b_end, eff_start, eff_end):
            return f"Imprevisto '{disruption.label}' conflitou com o horário original"

    for slot in fixed_slots:
        eff_start, eff_end = _effective_blocked_bounds(slot, buffer_minutes)
        if _overlaps_ts(b_start, b_end, eff_start, eff_end):
            return f"Compromisso fixo ou buffer '{slot.label}' conflitou com o horário original"

    buffer_sec = buffer_minutes * 60
    for kept_block in kept:
        if overlaps(block, kept_block):
            return "Sobreposição com outro bloco flexível preservado"
        if buffer_sec > 0:
            gap = max(
                kept_block.start.timestamp() - b_end,
                b_start - kept_block.end.timestamp(),
            )
            if gap < buffer_sec:
                return "Buffer mínimo entre blocos flexíveis não atendido"

    return None


def rebalance(request: RebalanceRequest) -> RebalanceProposal:
    """Rebalanceia blocos flexíveis após imprevisto com mínima perturbação.

    Regras inegociáveis:
    - Sono protegido e compromissos fixos (originais + imprevistos) nunca são movidos.
    - Blocos flexíveis não afetados permanecem intactos (`diff.kept`).
    - Retorna diff explícito (`added`, `removed`, `moved`, `kept`), justificativas e
      `requires_confirmation=True`, sem persistir nada.
    """
    sleep_slots = expand_sleep_slots(
        horizon=request.horizon,
        timezone=request.timezone,
        sleep_start=request.sleep_start,
        sleep_end=request.sleep_end,
    )
    all_fixed = [*request.schedule_slots, *request.disruptions]
    conflicts = detect_input_conflicts(all_fixed)
    goals_map = _resolve_rebalance_goals(request)

    kept: list[ProposedBlock] = []
    kept_seconds_by_goal: dict[str, int] = defaultdict(int)
    disrupted: list[tuple[ProposedBlock, str]] = []

    ordered_existing = sorted(
        request.existing_blocks,
        key=lambda b: (b.start.timestamp(), b.end.timestamp(), b.goal_id),
    )

    for block in ordered_existing:
        goal = goals_map[block.goal_id]
        block_seconds = int(round(block.end.timestamp() - block.start.timestamp()))
        reason = _diagnose_block_conflict(
            block,
            goal=goal,
            horizon=request.horizon,
            sleep_slots=sleep_slots,
            disruptions=request.disruptions,
            fixed_slots=request.schedule_slots,
            kept=kept,
            buffer_minutes=request.buffer_minutes,
        )
        if reason is None and (
            kept_seconds_by_goal[block.goal_id] + block_seconds
            > goal.duration_minutes * 60
        ):
            reason = "Duração preservada excederia a carga total da meta"

        if reason is None:
            kept.append(block)
            kept_seconds_by_goal[block.goal_id] += block_seconds
        else:
            disrupted.append((block, reason))

    # Monta metas pendentes apenas para minutos ainda não cobertos pelos blocos preservados.
    pending_goals: list[StudyGoal] = []
    for goal in goals_map.values():
        needed_seconds = goal.duration_minutes * 60 - kept_seconds_by_goal[goal.goal_id]
        if needed_seconds > 0:
            pending_goals.append(
                goal.model_copy(
                    update={"duration_minutes": max(1, needed_seconds // 60)}
                )
            )

    # Janelas livres descontam sono, fixos + imprevistos (com buffer) e blocos mantidos (com buffer).
    buffer_sec = request.buffer_minutes * 60
    busy_intervals = [
        _effective_blocked_bounds(slot, request.buffer_minutes)
        for slot in [*all_fixed, *sleep_slots]
    ]
    for kept_block in kept:
        busy_intervals.append(
            (
                kept_block.start.timestamp() - buffer_sec,
                kept_block.end.timestamp() + buffer_sec,
            )
        )

    free = _subtract_intervals(
        request.horizon.start.timestamp(),
        request.horizon.end.timestamp(),
        busy_intervals,
    )

    newly_allocated, unallocated = _allocate_goals_into_windows(
        pending_goals,
        free,
        timezone=request.timezone,
        buffer_minutes=request.buffer_minutes,
        max_block_minutes=request.max_block_minutes,
        min_block_minutes=request.min_block_minutes,
    )

    # Construção do diff exato (`moved`, `removed`, `added`, `kept`).
    disrupted_by_goal: dict[str, list[tuple[ProposedBlock, str]]] = defaultdict(list)
    for blk, rsn in disrupted:
        disrupted_by_goal[blk.goal_id].append((blk, rsn))

    new_by_goal: dict[str, list[ProposedBlock]] = defaultdict(list)
    for blk in newly_allocated:
        new_by_goal[blk.goal_id].append(blk)

    moved: list[MovedBlock] = []
    removed: list[ProposedBlock] = []
    added: list[ProposedBlock] = []
    reasons: list[str] = []

    if request.disruption_note:
        reasons.append(f"Imprevisto informado: {request.disruption_note}")

    for gid in sorted(set(disrupted_by_goal) | set(new_by_goal)):
        old_items = disrupted_by_goal.get(gid, [])
        new_items = list(new_by_goal.get(gid, []))
        used_new_indices: set[int] = set()

        for old_blk, old_reason in old_items:
            old_dur = int(round(old_blk.end.timestamp() - old_blk.start.timestamp()))
            matched_idx: int | None = None
            for idx, cand in enumerate(new_items):
                if idx in used_new_indices:
                    continue
                cand_dur = int(round(cand.end.timestamp() - cand.start.timestamp()))
                if cand_dur == old_dur:
                    matched_idx = idx
                    break

            if matched_idx is not None:
                used_new_indices.add(matched_idx)
                dest = new_items[matched_idx]
                moved.append(
                    MovedBlock(
                        goal_id=gid,
                        title=dest.title,
                        previous_start=old_blk.start,
                        previous_end=old_blk.end,
                        new_start=dest.start,
                        new_end=dest.end,
                        reason=old_reason,
                    )
                )
                reasons.append(
                    f"Bloco '{dest.title}' movido de {old_blk.start.isoformat()} "
                    f"para {dest.start.isoformat()} ({old_reason})."
                )
            else:
                removed.append(old_blk)
                reasons.append(
                    f"Bloco '{old_blk.title}' ({old_blk.start.isoformat()}) removido "
                    f"do horário original ({old_reason})."
                )

        for idx, cand in enumerate(new_items):
            if idx not in used_new_indices:
                added.append(cand)
                reasons.append(
                    f"Novo bloco '{cand.title}' sugerido em {cand.start.isoformat()} "
                    f"a {cand.end.isoformat()}."
                )

    if kept:
        reasons.append(
            f"{len(kept)} bloco(s) flexível(is) não afetado(s) preservado(s) sem alteração."
        )

    for pending in unallocated:
        goal_title = goals_map[pending.goal_id].title
        reasons.append(
            f"Objetivo '{goal_title}' ficou com {pending.remaining_minutes} min sem "
            "encaixe antes do prazo; o sono protegido e compromissos fixos foram preservados."
        )

    proposed_blocks = sorted(
        [*kept, *newly_allocated],
        key=lambda b: (b.start.timestamp(), b.end.timestamp(), b.goal_id),
    )
    diff = ScheduleDiff(added=added, removed=removed, moved=moved, kept=kept)
    diff_summary = (
        f"{len(kept)} mantidos, {len(moved)} movidos, {len(added)} adicionados, "
        f"{len(removed)} removidos; {len(unallocated)} objetivos com tempo pendente. "
        "Nenhuma agenda foi alterada."
    )
    return RebalanceProposal(
        proposed_blocks=proposed_blocks,
        diff=diff,
        reasons=list(dict.fromkeys(reasons)),
        unallocated=unallocated,
        input_conflicts=conflicts,
        diff_summary=diff_summary,
    )


def audit_rebalance(
    request: RebalanceRequest, proposal: RebalanceProposal
) -> list[str]:
    """Audita invariantes de segurança, preservação de fixos/sono e consistência do diff."""
    violations: list[str] = []
    if proposal.requires_confirmation is not True:
        violations.append("Confirmação obrigatória ausente")

    goals_map = _resolve_rebalance_goals(request)
    sleep_slots = expand_sleep_slots(
        horizon=request.horizon,
        timezone=request.timezone,
        sleep_start=request.sleep_start,
        sleep_end=request.sleep_end,
    )
    all_protected = [*request.schedule_slots, *request.disruptions, *sleep_slots]
    buffered_bounds = [
        (slot, *_effective_blocked_bounds(slot, request.buffer_minutes))
        for slot in all_protected
    ]
    buffer_sec = request.buffer_minutes * 60
    totals = dict.fromkeys(goals_map, 0.0)

    for i, block in enumerate(proposal.proposed_blocks):
        goal = goals_map.get(block.goal_id)
        if goal is None:
            violations.append("Objetivo desconhecido")
            continue
        seconds = block.end.timestamp() - block.start.timestamp()
        totals[block.goal_id] += seconds
        if (
            block.start.timestamp() < request.horizon.start.timestamp()
            or block.end.timestamp()
            > min(request.horizon.end.timestamp(), goal.deadline.timestamp())
        ):
            violations.append("Bloco fora do horizonte ou prazo")

        b_start, b_end = block.start.timestamp(), block.end.timestamp()
        for slot, eff_start, eff_end in buffered_bounds:
            if overlaps(block, slot):
                violations.append("Bloco invade sono, compromisso fixo ou imprevisto")
            elif _overlaps_ts(b_start, b_end, eff_start, eff_end):
                violations.append(
                    "Bloco invade buffer de compromisso fixo ou imprevisto"
                )

        for other in proposal.proposed_blocks[i + 1 :]:
            if overlaps(block, other):
                violations.append("Blocos sobrepostos")
            elif buffer_sec > 0:
                gap = max(
                    other.start.timestamp() - b_end,
                    b_start - other.end.timestamp(),
                )
                if gap < buffer_sec:
                    violations.append("Buffer entre blocos de estudo violado")

    existing_keys = {
        (b.goal_id, b.start.timestamp(), b.end.timestamp())
        for b in request.existing_blocks
    }
    proposed_keys = [
        (b.goal_id, b.start.timestamp(), b.end.timestamp())
        for b in proposal.proposed_blocks
    ]
    for kept_blk in proposal.diff.kept:
        key = (kept_blk.goal_id, kept_blk.start.timestamp(), kept_blk.end.timestamp())
        if key not in existing_keys:
            violations.append("Bloco marcado como mantido não existia antes")

    expected_keys = sorted(
        [
            (b.goal_id, b.start.timestamp(), b.end.timestamp())
            for b in proposal.diff.kept
        ]
        + [
            (m.goal_id, m.new_start.timestamp(), m.new_end.timestamp())
            for m in proposal.diff.moved
        ]
        + [
            (b.goal_id, b.start.timestamp(), b.end.timestamp())
            for b in proposal.diff.added
        ]
    )
    if sorted(proposed_keys) != expected_keys:
        violations.append("Diff inconsistente com proposed_blocks")

    missing: dict[str, int] = {}
    for item in proposal.unallocated:
        if item.goal_id not in goals_map or item.goal_id in missing:
            violations.append("Pendência desconhecida ou duplicada")
        missing[item.goal_id] = item.remaining_minutes * 60

    for gid, goal in goals_map.items():
        if totals[gid] + missing.get(gid, 0) != goal.duration_minutes * 60:
            violations.append("Duração alocada e pendente diverge da meta")

    return list(dict.fromkeys(violations))
