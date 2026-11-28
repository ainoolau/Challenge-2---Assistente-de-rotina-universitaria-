"""Testes de invariantes do motor determinístico compartilhado (TASK-F3-05/07/08)."""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from src.agents import planning as agents_planning
from src.core.planning import (
    audit_plan,
    audit_rebalance,
    detect_input_conflicts,
    free_windows,
    plan,
    protected_slots,
    rebalance,
)
from src.core.schemas import (
    Interval,
    PlanningRequest,
    ProposedBlock,
    RebalanceRequest,
    ScheduleSlot,
    StudyGoal,
)

BRT = timezone(timedelta(hours=-3))


def _dt(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 11, day, hour, minute, tzinfo=BRT)


def test_core_decoupled_from_agents_and_agents_facade_compatible():
    assert agents_planning.plan is plan
    assert agents_planning.audit_plan is audit_plan
    assert agents_planning.rebalance is rebalance
    assert agents_planning.audit_rebalance is audit_rebalance

    req = PlanningRequest(
        horizon=Interval(start=_dt(17, 6), end=_dt(17, 22)),
        schedule_slots=[
            ScheduleSlot(
                slot_id="s1",
                start=_dt(17, 8),
                end=_dt(17, 12),
                label="Residência IA",
                kind="work",
            )
        ],
        study_goals=[
            StudyGoal(
                goal_id="g1",
                title="Revisão de Estatística",
                duration_minutes=90,
                deadline=_dt(17, 20),
                priority=4,
            )
        ],
    )
    proposal = plan(req)
    assert proposal is not None
    assert proposal.requires_confirmation is True
    assert proposal.unallocated == []
    assert audit_plan(req, proposal) == []


def test_global_and_per_slot_buffers_respected_and_audited():
    req = PlanningRequest(
        horizon=Interval(start=_dt(17, 6), end=_dt(17, 22)),
        buffer_minutes=15,
        schedule_slots=[
            ScheduleSlot(
                slot_id="aula",
                start=_dt(17, 8),
                end=_dt(17, 10),
                label="Aula de Econometria",
                kind="class",
                buffer_before_minutes=20,
                buffer_after_minutes=30,
            ),
            ScheduleSlot(
                slot_id="trabalho",
                start=_dt(17, 14),
                end=_dt(17, 18),
                label="Estágio",
                kind="work",
            ),
        ],
        study_goals=[
            StudyGoal(
                goal_id="econ",
                title="Estudo de Econometria",
                duration_minutes=150,
                deadline=_dt(17, 22),
                priority=5,
            )
        ],
    )
    windows = free_windows(req)
    # 06:00 -> 07:40 (20m antes da aula), 10:30 (30m após aula) -> 13:45 (15m antes estágio),
    # 18:15 (15m após estágio) -> 22:00 (limite exato do sono).
    assert [(w.start, w.end) for w in windows] == [
        (_dt(17, 6, 0), _dt(17, 7, 40)),
        (_dt(17, 10, 30), _dt(17, 13, 45)),
        (_dt(17, 18, 15), _dt(17, 22, 0)),
    ]

    proposal = plan(req)
    assert proposal is not None
    assert proposal.unallocated == []
    assert audit_plan(req, proposal) == []

    # Confirma folga >= 15 min entre quaisquer dois blocos de estudo consecutivos.
    ordered = sorted(proposal.proposed_blocks, key=lambda b: b.start)
    for prev_blk, next_blk in zip(ordered, ordered[1:], strict=False):
        assert (next_blk.start - prev_blk.end) >= timedelta(minutes=15)

    # Audita violação ao invadir buffer de compromisso fixo.
    tampered = proposal.model_copy(deep=True)
    tampered.proposed_blocks[0] = ProposedBlock(
        goal_id="econ",
        title="Estudo de Econometria",
        start=_dt(17, 6, 50),
        end=_dt(17, 7, 50),  # entra no buffer_before de 20m (07:40-08:00)
    )
    assert "Bloco invade buffer de compromisso fixo" in audit_plan(req, tampered)

    # Audita violação ao colar dois blocos de estudo com buffer global > 0.
    tampered_gap = proposal.model_copy(deep=True)
    b0 = tampered_gap.proposed_blocks[0]
    tampered_gap.proposed_blocks[1] = ProposedBlock(
        goal_id="econ",
        title="Estudo de Econometria",
        start=b0.end + timedelta(minutes=5),
        end=b0.end + timedelta(minutes=65),
    )
    assert "Buffer entre blocos de estudo violado" in audit_plan(req, tampered_gap)


def test_min_block_minutes_avoids_invalid_slivers():
    req = PlanningRequest(
        horizon=Interval(start=_dt(17, 6), end=_dt(17, 22)),
        buffer_minutes=10,
        min_block_minutes=30,
        max_block_minutes=60,
        study_goals=[
            StudyGoal(
                goal_id="g70",
                title="Lista de Cálculo",
                duration_minutes=70,
                deadline=_dt(17, 12),
                priority=3,
            )
        ],
    )
    proposal = plan(req)
    assert proposal is not None
    assert proposal.unallocated == []
    assert audit_plan(req, proposal) == []
    durations = [
        int((b.end - b.start).total_seconds() // 60) for b in proposal.proposed_blocks
    ]
    assert durations == [40, 30]
    assert all(30 <= d <= 60 for d in durations)


def test_rebalance_minimal_perturbation_moves_only_affected_blocks():
    horizon = Interval(start=_dt(17, 6), end=_dt(18, 22))
    fixed_slots = [
        ScheduleSlot(
            slot_id="clt",
            start=_dt(17, 8),
            end=_dt(17, 12),
            label="Trabalho CLT",
            kind="work",
        )
    ]
    goals = [
        StudyGoal(
            goal_id="econ",
            title="Estudo de Econometria",
            duration_minutes=180,
            deadline=_dt(18, 20),
            priority=5,
        )
    ]
    existing = [
        ProposedBlock(
            goal_id="econ",
            title="Estudo de Econometria",
            start=_dt(17, 14),
            end=_dt(17, 15),
        ),
        ProposedBlock(
            goal_id="econ",
            title="Estudo de Econometria",
            start=_dt(17, 16),
            end=_dt(17, 17),
        ),
        ProposedBlock(
            goal_id="econ",
            title="Estudo de Econometria",
            start=_dt(18, 9),
            end=_dt(18, 10),
        ),
    ]
    # Imprevisto atinge APENAS o bloco de 17/11 14h-15h.
    disruption = ScheduleSlot(
        slot_id="imp-1",
        start=_dt(17, 13, 30),
        end=_dt(17, 15, 30),
        label="Reunião emergencial de projeto",
        kind="work",
    )

    req = RebalanceRequest(
        horizon=horizon,
        schedule_slots=fixed_slots,
        disruptions=[disruption],
        existing_blocks=existing,
        study_goals=goals,
        buffer_minutes=15,
        disruption_note="Reunião extra convocada pelo cliente",
    )
    original_json = req.model_dump_json()
    proposal = rebalance(req)

    # Entrada nunca é mutada; proposta sempre requer confirmação.
    assert req.model_dump_json() == original_json
    assert proposal.requires_confirmation is True
    assert proposal.unallocated == []
    assert audit_rebalance(req, proposal) == []

    # Mínima perturbação: os 2 blocos não afetados permanecem intactos em `kept`.
    assert len(proposal.diff.kept) == 2
    kept_starts = {b.start for b in proposal.diff.kept}
    assert kept_starts == {_dt(17, 16), _dt(18, 9)}

    # Apenas o bloco afetado foi movido, com motivo explícito.
    assert len(proposal.diff.moved) == 1
    assert proposal.diff.removed == []
    assert proposal.diff.added == []
    moved = proposal.diff.moved[0]
    assert moved.previous_start == _dt(17, 14)
    assert moved.previous_end == _dt(17, 15)
    assert "Reunião emergencial de projeto" in moved.reason
    assert any("Reunião extra" in r for r in proposal.reasons)


def test_rebalance_overcrowded_day_preserves_sleep_and_reports_unallocated():
    # Dia completamente lotado exceto 1 hora livre antes do imprevisto; imprevisto ocupa essa hora.
    horizon = Interval(start=_dt(17, 6), end=_dt(17, 22))
    fixed_slots = [
        ScheduleSlot(
            start=_dt(17, 6),
            end=_dt(17, 12),
            label="Residência IA manhã",
            kind="work",
        ),
        ScheduleSlot(
            start=_dt(17, 12),
            end=_dt(17, 18),
            label="Residência IA tarde",
            kind="work",
        ),
        ScheduleSlot(
            start=_dt(17, 18),
            end=_dt(17, 19),
            label="Deslocamento",
            kind="commute",
        ),
        ScheduleSlot(
            start=_dt(17, 20),
            end=_dt(17, 22),
            label="Aula noturna",
            kind="class",
        ),
    ]
    existing = [
        ProposedBlock(
            goal_id="prova",
            title="Revisão para Prova",
            start=_dt(17, 19),
            end=_dt(17, 20),
        )
    ]
    disruption = ScheduleSlot(
        start=_dt(17, 19),
        end=_dt(17, 20),
        label="Trânsito intenso / atraso",
        kind="commute",
    )
    req = RebalanceRequest(
        horizon=horizon,
        schedule_slots=fixed_slots,
        disruptions=[disruption],
        existing_blocks=existing,
        study_goals=[
            StudyGoal(
                goal_id="prova",
                title="Revisão para Prova",
                duration_minutes=60,
                deadline=_dt(17, 22),
                priority=5,
            )
        ],
    )
    proposal = rebalance(req)
    assert proposal.requires_confirmation is True
    assert proposal.proposed_blocks == []
    assert proposal.diff.kept == []
    assert proposal.diff.moved == []
    assert len(proposal.diff.removed) == 1
    assert len(proposal.unallocated) == 1
    assert proposal.unallocated[0].goal_id == "prova"
    assert proposal.unallocated[0].remaining_minutes == 60
    assert any("sono protegido" in r.lower() for r in proposal.reasons)
    assert audit_rebalance(req, proposal) == []


def test_rebalance_disruption_overlapping_fixed_slot_reports_conflict_without_moving_fixed():
    req = RebalanceRequest(
        horizon=Interval(start=_dt(17, 6), end=_dt(17, 22)),
        schedule_slots=[
            ScheduleSlot(
                start=_dt(17, 8),
                end=_dt(17, 12),
                label="Aula presencial",
                kind="class",
            )
        ],
        disruptions=[
            ScheduleSlot(
                start=_dt(17, 10),
                end=_dt(17, 13),
                label="Plantão inesperado",
                kind="work",
            )
        ],
        existing_blocks=[
            ProposedBlock(
                goal_id="g1",
                title="Leitura",
                start=_dt(17, 12),
                end=_dt(17, 13),
            )
        ],
        study_goals=[
            StudyGoal(
                goal_id="g1",
                title="Leitura",
                duration_minutes=60,
                deadline=_dt(17, 21),
                priority=3,
            )
        ],
    )
    proposal = rebalance(req)
    assert any("Aula presencial" in c for c in proposal.input_conflicts)
    assert any("Plantão inesperado" in c for c in proposal.input_conflicts)
    assert len(proposal.diff.moved) == 1
    assert audit_rebalance(req, proposal) == []


def test_rebalance_split_block_records_removed_and_added_cleanly():
    # Janelas livres restantes são duas de 30 min; bloco deslocado de 60 min precisa ser dividido.
    req = RebalanceRequest(
        horizon=Interval(start=_dt(17, 6), end=_dt(17, 22)),
        schedule_slots=[
            ScheduleSlot(start=_dt(17, 6, 30), end=_dt(17, 12), label="Bloco A"),
            ScheduleSlot(start=_dt(17, 12, 30), end=_dt(17, 18), label="Bloco B"),
            ScheduleSlot(start=_dt(17, 19), end=_dt(17, 22), label="Bloco C"),
        ],
        disruptions=[
            ScheduleSlot(
                start=_dt(17, 18), end=_dt(17, 19), label="Imprevisto", kind="other"
            )
        ],
        existing_blocks=[
            ProposedBlock(
                goal_id="split",
                title="Exercícios",
                start=_dt(17, 18),
                end=_dt(17, 19),
            )
        ],
        study_goals=[
            StudyGoal(
                goal_id="split",
                title="Exercícios",
                duration_minutes=60,
                deadline=_dt(17, 22),
                priority=4,
            )
        ],
    )
    proposal = rebalance(req)
    assert proposal.unallocated == []
    assert len(proposal.diff.removed) == 1
    assert len(proposal.diff.added) == 2
    assert proposal.diff.moved == []
    assert audit_rebalance(req, proposal) == []


def test_overcrowded_day_plan_respects_priority_and_unallocated_accounting():
    # Apenas 2 horas livres no dia (18h-20h); 3 metas somam 3h -> 1h fica em unallocated.
    req = PlanningRequest(
        horizon=Interval(start=_dt(17, 6), end=_dt(17, 22)),
        schedule_slots=[
            ScheduleSlot(start=_dt(17, 6), end=_dt(17, 18), label="Jornada integral"),
            ScheduleSlot(start=_dt(17, 20), end=_dt(17, 22), label="Aula noturna"),
        ],
        study_goals=[
            StudyGoal(
                goal_id="baixa",
                title="Leitura complementar",
                duration_minutes=60,
                deadline=_dt(17, 22),
                priority=1,
            ),
            StudyGoal(
                goal_id="alta",
                title="Prova urgente",
                duration_minutes=120,
                deadline=_dt(17, 22),
                priority=5,
            ),
        ],
    )
    proposal = plan(req)
    assert proposal is not None
    assert audit_plan(req, proposal) == []
    assert {b.goal_id for b in proposal.proposed_blocks} == {"alta"}
    assert len(proposal.unallocated) == 1
    assert proposal.unallocated[0].goal_id == "baixa"
    assert proposal.unallocated[0].remaining_minutes == 60


def test_audit_rebalance_detects_sleep_invasion_and_diff_tampering():
    req = RebalanceRequest(
        horizon=Interval(start=_dt(17, 6), end=_dt(18, 22)),
        disruptions=[
            ScheduleSlot(start=_dt(17, 14), end=_dt(17, 15), label="Imprevisto")
        ],
        existing_blocks=[
            ProposedBlock(
                goal_id="g1", title="Estudo", start=_dt(17, 14), end=_dt(17, 15)
            )
        ],
        study_goals=[
            StudyGoal(
                goal_id="g1",
                title="Estudo",
                duration_minutes=60,
                deadline=_dt(18, 20),
                priority=3,
            )
        ],
    )
    proposal = rebalance(req)
    assert audit_rebalance(req, proposal) == []

    # Força invasão de sono (23h-00h).
    bad = proposal.model_copy(deep=True)
    bad.proposed_blocks[0] = ProposedBlock(
        goal_id="g1", title="Estudo", start=_dt(17, 23), end=_dt(18, 0)
    )
    violations = audit_rebalance(req, bad)
    assert "Bloco invade sono, compromisso fixo ou imprevisto" in violations
    assert "Diff inconsistente com proposed_blocks" in violations


def test_randomized_buffers_and_rebalance_invariants():
    rng = random.Random(2026)
    horizon = Interval(start=_dt(17, 6), end=_dt(20, 22))
    for _ in range(40):
        buf = rng.choice([0, 5, 10, 15])
        slots: list[ScheduleSlot] = []
        for i in range(8):
            st = _dt(17, 6) + timedelta(minutes=rng.randrange(0, 4800))
            slots.append(
                ScheduleSlot(
                    start=st,
                    end=st + timedelta(minutes=rng.randrange(30, 180)),
                    label=f"Fixo {i}",
                    kind=rng.choice(["work", "class", "commute", "other"]),
                    buffer_before_minutes=rng.choice([0, 5, 10]),
                    buffer_after_minutes=rng.choice([0, 5, 10]),
                )
            )
        goals = [
            StudyGoal(
                goal_id=f"g{j}",
                title=f"Meta {j}",
                duration_minutes=rng.randrange(30, 240),
                deadline=_dt(17, 12) + timedelta(minutes=rng.randrange(60, 4400)),
                priority=rng.randint(1, 5),
            )
            for j in range(3)
        ]
        plan_req = PlanningRequest(
            horizon=horizon,
            schedule_slots=slots,
            study_goals=goals,
            buffer_minutes=buf,
        )
        initial = plan(plan_req)
        assert initial is not None
        assert audit_plan(plan_req, initial) == []

        # Injeta 1 a 2 imprevistos sobre o plano inicial e audita o rebalanceamento.
        disruptions = []
        for k in range(rng.randint(1, 2)):
            dst = _dt(17, 7) + timedelta(minutes=rng.randrange(0, 4200))
            disruptions.append(
                ScheduleSlot(
                    start=dst,
                    end=dst + timedelta(minutes=rng.randrange(30, 150)),
                    label=f"Imprevisto {k}",
                    kind="other",
                )
            )
        reb_req = RebalanceRequest(
            horizon=horizon,
            schedule_slots=slots,
            disruptions=disruptions,
            existing_blocks=initial.proposed_blocks,
            study_goals=goals,
            buffer_minutes=buf,
        )
        rebalanced = rebalance(reb_req)
        assert audit_rebalance(reb_req, rebalanced) == []
        # Garante zero invasão de sono protegido em todas as iterações.
        sleep_slots = [s for s in protected_slots(plan_req) if s.kind == "sleep"]
        assert all(
            not (
                b.start.timestamp() < s.end.timestamp()
                and s.start.timestamp() < b.end.timestamp()
            )
            for b in rebalanced.proposed_blocks
            for s in sleep_slots
        )


def test_rebalance_dst_midnight_sleep_protected():
    req = RebalanceRequest(
        timezone="America/New_York",
        horizon=Interval(
            start=datetime.fromisoformat("2026-03-07T22:00:00-05:00"),
            end=datetime.fromisoformat("2026-03-09T08:00:00-04:00"),
        ),
        disruptions=[
            ScheduleSlot(
                start=datetime.fromisoformat("2026-03-08T08:00:00-04:00"),
                end=datetime.fromisoformat("2026-03-08T10:00:00-04:00"),
                label="Imprevisto pós-DST",
                kind="other",
            )
        ],
        existing_blocks=[
            ProposedBlock(
                goal_id="dst",
                title="Estudo DST",
                start=datetime.fromisoformat("2026-03-08T08:00:00-04:00"),
                end=datetime.fromisoformat("2026-03-08T09:00:00-04:00"),
            )
        ],
        study_goals=[
            StudyGoal(
                goal_id="dst",
                title="Estudo DST",
                duration_minutes=120,
                deadline=datetime.fromisoformat("2026-03-09T08:00:00-04:00"),
                priority=4,
            )
        ],
        buffer_minutes=15,
    )
    proposal = rebalance(req)
    assert proposal.unallocated == []
    assert audit_rebalance(req, proposal) == []
    assert all(6 <= b.start.hour < 22 for b in proposal.proposed_blocks)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"min_block_minutes": 90, "max_block_minutes": 60},
        {"buffer_minutes": -5},
    ],
)
def test_invalid_planning_request_parameters_rejected(kwargs):
    with pytest.raises(ValidationError):
        PlanningRequest(
            horizon=Interval(start=_dt(17, 6), end=_dt(17, 22)),
            **kwargs,
        )


def test_multijornada_stress_40h_overload_zero_violations():
    """Teste de estresse multijornada (TASK-F1-07): 40h de metas sobre semana pesada."""
    horizon = Interval(start=_dt(23, 6), end=_dt(29, 22))
    slots: list[ScheduleSlot] = []
    # Trabalho fixo Seg-Sex 09:00-18:00 + buffer 30m
    for day in range(23, 28):
        slots.append(
            ScheduleSlot(
                slot_id=f"work-{day}",
                start=_dt(day, 9),
                end=_dt(day, 18),
                label="Trabalho fixo",
                kind="work",
                buffer_before_minutes=30,
                buffer_after_minutes=30,
            )
        )
    # Faculdade fixa Seg/Qua/Sex 19:00-21:30 + buffer 15m
    for day in (23, 25, 27):
        slots.append(
            ScheduleSlot(
                slot_id=f"class-{day}",
                start=_dt(day, 19),
                end=_dt(day, 21, 30),
                label="Faculdade noturna",
                kind="class",
                buffer_before_minutes=15,
                buffer_after_minutes=15,
            )
        )

    goals = [
        StudyGoal(
            goal_id="p5-prova",
            title="Prova crítica",
            duration_minutes=1200,
            deadline=_dt(26, 21),
            priority=5,
        ),
        StudyGoal(
            goal_id="p4-entrega",
            title="Entrega de projeto",
            duration_minutes=1200,
            deadline=_dt(28, 20),
            priority=4,
        ),
        StudyGoal(
            goal_id="p2-leitura",
            title="Leituras extras",
            duration_minutes=1800,
            deadline=_dt(29, 22),
            priority=2,
        ),
    ]
    req = PlanningRequest(
        horizon=horizon,
        schedule_slots=slots,
        study_goals=goals,
        buffer_minutes=10,
        min_block_minutes=30,
        max_block_minutes=60,
    )
    proposal = plan(req)
    assert proposal is not None
    assert proposal.requires_confirmation is True
    assert audit_plan(req, proposal) == []
    assert any(u.remaining_minutes > 0 for u in proposal.unallocated)


def test_rebalance_priority_preemption_displaces_low_priority_for_critical_goal():
    """Preempção controlada (TASK-F1-07): P5 atingido por imprevisto desloca P1 com folga."""
    horizon = Interval(start=_dt(25, 6), end=_dt(29, 22))
    # Quarta (25) e Quinta (26) lotadas exceto 19h-21h de quarta e 19h-21h de quinta.
    fixed_slots = [
        ScheduleSlot(
            start=_dt(25, 6), end=_dt(25, 19), label="Jornada Qua", kind="work"
        ),
        ScheduleSlot(
            start=_dt(25, 21), end=_dt(25, 22), label="Compromisso Qua", kind="other"
        ),
        ScheduleSlot(
            start=_dt(26, 6), end=_dt(26, 19), label="Jornada Qui", kind="work"
        ),
        ScheduleSlot(
            start=_dt(26, 21), end=_dt(26, 22), label="Compromisso Qui", kind="other"
        ),
    ]
    goals = [
        StudyGoal(
            goal_id="critica",
            title="Prova A1",
            duration_minutes=60,
            deadline=_dt(26, 21),
            priority=5,
        ),
        StudyGoal(
            goal_id="baixa",
            title="Leitura opcional",
            duration_minutes=60,
            deadline=_dt(29, 21),
            priority=1,
        ),
    ]
    existing = [
        ProposedBlock(
            goal_id="critica",
            title="Prova A1",
            start=_dt(25, 19),
            end=_dt(25, 20),
        ),
        ProposedBlock(
            goal_id="baixa",
            title="Leitura opcional",
            start=_dt(26, 19),
            end=_dt(26, 20),
        ),
    ]
    # Imprevisto ocupa toda a janela de quarta 19h-21h; na quinta 19h-20h há apenas 1h (ocupada por P1).
    disruptions = [
        ScheduleSlot(
            start=_dt(25, 19),
            end=_dt(25, 21),
            label="Reunião urgente",
            kind="work",
        ),
        ScheduleSlot(
            start=_dt(26, 20),
            end=_dt(26, 21),
            label="Plantão extra",
            kind="work",
        ),
    ]
    req = RebalanceRequest(
        horizon=horizon,
        schedule_slots=fixed_slots,
        disruptions=disruptions,
        existing_blocks=existing,
        study_goals=goals,
        buffer_minutes=0,
        min_block_minutes=30,
    )
    proposal = rebalance(req)
    assert audit_rebalance(req, proposal) == []
    # P5 foi realocado para Quinta 19h-20h e P1 foi movido para Sexta/fim de semana!
    assert proposal.unallocated == []
    p5_blocks = [b for b in proposal.proposed_blocks if b.goal_id == "critica"]
    p1_blocks = [b for b in proposal.proposed_blocks if b.goal_id == "baixa"]
    assert len(p5_blocks) == 1
    assert p5_blocks[0].start == _dt(26, 19)
    assert len(p1_blocks) == 1
    assert p1_blocks[0].start >= _dt(27, 6)
    assert any(m.goal_id == "baixa" for m in proposal.diff.moved)


def test_modality_remote_skips_global_buffer_and_allow_overlap_suppresses_conflict():
    """TASK-F1-08: remoto não herda buffer global e allow_overlap coexiste sem conflito."""
    presencial = ScheduleSlot(
        slot_id="res",
        start=_dt(17, 8),
        end=_dt(17, 12),
        label="Atividade presencial",
        kind="work",
        modality="presencial",
    )
    remoto_paralelo = ScheduleSlot(
        slot_id="trad",
        start=_dt(17, 10),
        end=_dt(17, 11),
        label="Tradução remota",
        kind="work",
        modality="remoto",
        allow_overlap=True,
    )
    remoto_solo = ScheduleSlot(
        slot_id="ead",
        start=_dt(17, 14),
        end=_dt(17, 16),
        label="Aula EAD",
        kind="class",
        modality="remoto",
    )

    assert detect_input_conflicts([presencial, remoto_paralelo, remoto_solo]) == []

    # Sem allow_overlap, o mesmo par dispara conflito normalmente.
    conflito = remoto_paralelo.model_copy(update={"allow_overlap": False})
    assert len(detect_input_conflicts([presencial, conflito])) == 1

    # Buffer global de 20 min afeta presencial (08:00-12:00 -> 07:40-12:20),
    # mas NÃO afeta remoto (14:00-16:00 permanece livre até 14:00 e retoma às 16:00).
    req = PlanningRequest(
        horizon=Interval(start=_dt(17, 6), end=_dt(17, 22)),
        buffer_minutes=20,
        schedule_slots=[presencial, remoto_paralelo, remoto_solo],
    )
    windows = free_windows(req)
    assert [(w.start, w.end) for w in windows] == [
        (_dt(17, 6, 0), _dt(17, 7, 40)),
        (_dt(17, 12, 20), _dt(17, 14, 0)),
        (_dt(17, 16, 0), _dt(17, 22, 0)),
    ]
