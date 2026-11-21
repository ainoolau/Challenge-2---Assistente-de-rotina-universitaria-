"""Colaboração, bloqueio pré-LLM, contratos e invariantes da agenda."""

import json
from datetime import timedelta
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from scripts.demo_multiagents import main
from src.agents.analysis_planning_agent import AnalysisPlanningAgent
from src.agents.demo import SimulatedLLM, SimulatedRetriever, demo_request
from src.agents.llm import GroqLLM, LLMConfig
from src.agents.orchestrator import ABSTENTION, MultiAgentOrchestrator
from src.agents.planning import audit_plan, input_conflicts, plan, protected_slots
from src.agents.research_agent import ResearchAgent
from src.agents.schemas import (
    AgentRequest,
    AgentRunResult,
    EvidenceFact,
    ResearchNotes,
    ValidationNotes,
)
from src.agents.validation_agent import ValidationAgent


def runner(llm=None, retriever=None):
    llm = llm or SimulatedLLM()
    return MultiAgentOrchestrator(
        ResearchAgent(retriever or SimulatedRetriever(), llm),
        AnalysisPlanningAgent(llm),
        ValidationAgent(llm),
        llm,
        mode="simulated",
    )


def test_documental_handoffs():
    result = runner().run(demo_request("documental"))
    assert result.status == "completed"
    assert [e.agent for e in result.trace] == ["research", "analysis", "validation"]
    assert result.trace[1].input["retrieval"] == result.trace[0].output
    assert result.trace[2].input["proposal"] == result.trace[1].output
    assert result.metrics.llm_calls == 3
    assert "[C1: fixture_simulada.txt]" in result.final_answer
    assert result.metrics.input_tokens is None
    AgentRunResult.model_validate_json(result.model_dump_json())


def test_blocked_calls_no_llm():
    result = runner().run(demo_request("fora_dominio"))
    assert result.status == "abstained"
    assert result.metrics.llm_calls == 0
    assert result.metrics.input_tokens == result.metrics.output_tokens == 0
    assert result.proposal is None and result.validation is None
    assert result.final_answer == ABSTENTION


def test_correction_handoff_once():
    result = runner(SimulatedLLM(force_correction=True)).run(demo_request("correcao"))
    assert result.status == "completed"
    assert len(result.trace) == 5
    assert result.trace[2].output["valid"] is False
    assert result.trace[3].input["corrections"] == ["Citação inexistente"]
    assert result.validation.attempt == 1
    assert "C999" not in result.final_answer


def test_persistent_semantic_failure_stops_at_five_calls():
    class RejectingLLM(SimulatedLLM):
        def complete(self, role, instructions, data, output):
            value = super().complete(role, instructions, data, output)
            if role == "validation":
                return ValidationNotes(
                    factual_ok=False,
                    violations=["Número sem suporte"],
                    corrections_needed=["Remover número"],
                )
            return value

    result = runner(RejectingLLM()).run(demo_request("documental"))
    assert result.status == "abstained"
    assert result.metrics.llm_calls == 5
    assert len(result.trace) == 5
    assert result.final_answer == ABSTENTION


def test_failure_sanitized_and_partial_trace_preserved():
    class BrokenLLM(SimulatedLLM):
        def complete(self, *args):
            raise RuntimeError("secret-content-never-export")

    result = runner(BrokenLLM()).run(demo_request("documental"))
    assert result.status == "error"
    assert result.trace[-1].status == "error"
    assert "secret-content" not in result.model_dump_json()


def test_research_rejects_fabricated_quotes():
    llm = SimulatedLLM()
    with patch.object(
        llm,
        "complete",
        return_value=ResearchNotes(
            facts=[
                EvidenceFact(
                    statement="Inventado", source_id="C1", quote="Não existe no trecho"
                )
            ],
            gaps=[],
        ),
    ):
        result = ResearchAgent(SimulatedRetriever(), llm).execute("Pergunta factual?")
    assert result.abstained
    assert not result.verified_facts


def test_exact_threshold_allowed_and_empty_retrieval_blocked():
    class Boundary(SimulatedRetriever):
        def retrieve(self, question):
            return [
                c.model_copy(update={"score": 0.5}) for c in super().retrieve(question)
            ]

    assert (
        runner(retriever=Boundary()).run(demo_request("documental")).status
        == "completed"
    )
    with patch.object(SimulatedRetriever, "retrieve", return_value=[]):
        assert runner().run(demo_request("documental")).metrics.llm_calls == 0


@pytest.mark.parametrize("threshold", [float("nan"), float("inf"), 1.1, -1.1])
def test_invalid_threshold(threshold):
    with pytest.raises(ValueError):
        ResearchAgent(SimulatedRetriever(), SimulatedLLM(), threshold)


def test_planning_preserves_input_protects_sleep_and_fixed_slots():
    request = demo_request("planejamento")
    original = request.model_dump_json()
    result = runner().run(request)
    assert request.model_dump_json() == original
    assert result.status == "completed"
    assert result.proposal.planning.requires_confirmation is True
    assert not audit_plan(request, result.proposal.planning)
    assert input_conflicts(request)  # CLT e aula já conflitam; não são movidos.
    assert "Compromissos fixos sobrepostos" in result.final_answer
    assert "não aplicada" in result.final_answer


def test_no_capacity_and_expired_deadline():
    request = demo_request("planejamento")
    request.study_goals[0].deadline = request.horizon.start - timedelta(days=1)
    proposal = plan(request)
    assert not proposal.proposed_blocks
    assert proposal.unallocated[0].remaining_minutes == 240
    assert not audit_plan(request, proposal)


def test_audit_detects_sleep_overlap_deadline_duration_and_unknown_goal():
    request = demo_request("planejamento")
    proposal = plan(request)
    first = proposal.proposed_blocks[0]
    sleep = next(
        s for s in protected_slots(request) if s.start >= request.horizon.start
    )
    first.start, first.end = sleep.start, sleep.start + timedelta(minutes=60)
    assert "Bloco invade sono ou compromisso fixo" in audit_plan(request, proposal)
    proposal.proposed_blocks.append(first.model_copy())
    violations = audit_plan(request, proposal)
    assert "Blocos sobrepostos" in violations
    assert "Duração alocada e pendente diverge da meta" in violations
    first.goal_id = "unknown"
    assert "Objetivo desconhecido" in audit_plan(request, proposal)


def test_multi_goal_nonoverlap_and_accounting():
    request = demo_request("planejamento")
    goal = request.study_goals[0].model_copy(
        update={"goal_id": "second", "title": "Outra meta", "duration_minutes": 1000}
    )
    request.study_goals.append(goal)
    proposal = plan(request)
    assert not audit_plan(request, proposal)


@pytest.mark.parametrize(
    "patch_data",
    [
        {"timezone": "Wrong/Zone"},
        {"horizon": {"start": "2026-11-17T06:00:00", "end": "2026-11-18T22:00:00"}},
        {
            "horizon": {
                "start": "2026-11-18T06:00:00-03:00",
                "end": "2026-11-17T22:00:00-03:00",
            }
        },
        {"sleep_start": "22:00", "sleep_end": "22:00"},
        {"horizon": None},
    ],
)
def test_invalid_schedule_contract(patch_data):
    data = demo_request("planejamento").model_dump(mode="json")
    data.update(patch_data)
    with pytest.raises(ValidationError):
        AgentRequest.model_validate(data)


def test_cli_four_simulated_scenarios(tmp_path):
    assert main(["--output-dir", str(tmp_path)]) == 0
    reports = list(tmp_path.rglob("*.json"))
    assert len(reports) == 4
    results = [
        AgentRunResult.model_validate_json(p.read_text(encoding="utf-8"))
        for p in reports
    ]
    assert all(r.mode == "simulated" for r in results)
    assert any(r.validation and r.validation.attempt == 1 for r in results)


def test_cli_invalid_request_stops_before_network(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text('{"question":"bad"}')
    with patch("urllib.request.urlopen") as http, pytest.raises(SystemExit):
        main(["--mode", "live", "--request", str(path)])
    http.assert_not_called()


def test_groq_payload_usage_and_secret_not_in_trace(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "unit-test-secret")

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self):
            return json.dumps(
                {
                    "choices": [
                        {
                            "finish_reason": "stop",
                            "message": {
                                "content": '{"factual_ok":true,"violations":[],"corrections_needed":[]}'
                            },
                        }
                    ],
                    "usage": {"prompt_tokens": 20, "completion_tokens": 30},
                }
            ).encode()

    llm = GroqLLM(LLMConfig())
    with patch("urllib.request.urlopen", return_value=Response()) as http:
        result = llm.complete(
            "validation", "Audite", {"question": "Pergunta?"}, ValidationNotes
        )
    assert result.factual_ok
    payload = json.loads(http.call_args.args[0].data)
    assert payload["tool_choice"] == "none"
    assert "tools" not in payload
    assert payload["response_format"] == {"type": "json_object"}
    assert llm.calls[0]["input_tokens"] == 20
    assert llm.calls[0]["output_tokens"] == 30
    assert "unit-test-secret" not in json.dumps(llm.calls)


def test_compound_question_retrieves_both_clauses_and_bounds_chunks():
    class ClauseRetriever:
        def retrieve(self, question):
            from src.agents.schemas import EvidenceChunk

            if question.startswith("o que"):
                return [
                    EvidenceChunk(
                        source_id="C1",
                        source="sanctions.txt",
                        chunk_index=0,
                        text="Três advertências levam ao desligamento.",
                        score=0.9,
                    )
                ]
            return [
                EvidenceChunk(
                    source_id="C1",
                    source="attendance.txt",
                    chunk_index=0,
                    text="Frequência mínima de 90%.",
                    score=0.7,
                )
            ]

    result = runner(retriever=ClauseRetriever()).run(demo_request("documental"))
    assert len(result.retrieval.queries) == 3
    assert {c.source for c in result.retrieval.chunks} == {
        "attendance.txt",
        "sanctions.txt",
    }
    assert len({c.source_id for c in result.retrieval.chunks}) == 2
    assert len(result.retrieval.chunks) <= 3


def test_tokens_do_not_leak_between_runs():
    shared = runner()
    first = shared.run(demo_request("documental"))
    second = shared.run(demo_request("fora_dominio"))
    assert first.metrics.llm_calls == 3
    assert second.metrics.llm_calls == 0
    assert second.config["llm_calls"] == []


def test_randomized_schedule_invariants():
    import random

    from src.agents.schemas import ScheduleSlot

    rng = random.Random(42)
    for _ in range(50):
        request = demo_request("planejamento")
        for index in range(10):
            start = request.horizon.start + timedelta(minutes=rng.randrange(0, 4000))
            request.schedule_slots.append(
                ScheduleSlot(
                    start=start,
                    end=start + timedelta(minutes=rng.randrange(1, 240)),
                    label=f"Ocupação {index}",
                    kind="other",
                )
            )
        request.study_goals[0].duration_minutes = rng.randrange(1, 1800)
        assert audit_plan(request, plan(request)) == []


def test_dst_and_midnight_sleep_protected():
    request = AgentRequest.model_validate(
        {
            "question": "Como planejar estudo?",
            "timezone": "America/New_York",
            "horizon": {
                "start": "2026-03-07T22:00:00-05:00",
                "end": "2026-03-09T08:00:00-04:00",
            },
            "study_goals": [
                {
                    "goal_id": "g",
                    "title": "Estudo",
                    "duration_minutes": 180,
                    "deadline": "2026-03-09T08:00:00-04:00",
                }
            ],
        }
    )
    proposal = plan(request)
    assert audit_plan(request, proposal) == []
    assert all(6 <= b.start.hour < 22 for b in proposal.proposed_blocks)


def test_research_refinement_bounded_and_recorded():
    class RefiningLLM(SimulatedLLM):
        def complete(self, role, instructions, data, output):
            value = super().complete(role, instructions, data, output)
            if role == "research":
                value.gaps = ["Falta um dado"]
                value.additional_queries = ["Busca complementar"]
            return value

    llm = RefiningLLM()
    with patch.object(
        SimulatedRetriever, "retrieve", wraps=SimulatedRetriever().retrieve
    ) as retrieval:
        result = runner(llm).run(demo_request("correcao"))
    assert len(result.retrieval.rounds) == 2
    assert result.retrieval.queries == [
        demo_request("correcao").question,
        "Busca complementar",
    ]
    assert retrieval.call_count == 2
    assert result.metrics.llm_calls == 4


def test_approving_validator_cannot_override_invalid_schedule():
    from src.agents.schemas import ProposalDraft

    request = demo_request("planejamento")
    research = ResearchAgent(SimulatedRetriever(), SimulatedLLM()).execute(
        request.question
    )
    proposal = AnalysisPlanningAgent(SimulatedLLM()).execute(request, research)
    data = proposal.model_dump(mode="json")
    data["planning"]["proposed_blocks"][0]["start"] = "2026-11-17T03:00:00-03:00"
    data["planning"]["proposed_blocks"][0]["end"] = "2026-11-17T04:00:00-03:00"
    invalid = ProposalDraft.model_validate(data)
    llm = SimulatedLLM()
    verdict = ValidationAgent(llm).execute(request, research, invalid)
    assert not verdict.valid and not verdict.invariants_ok
    assert not llm.calls


@pytest.mark.parametrize("finish,content", [("length", "{}"), ("stop", "not-json")])
def test_groq_failed_structured_output_keeps_known_usage(monkeypatch, finish, content):
    monkeypatch.setenv("GROQ_API_KEY", "unit-secret")

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self):
            return json.dumps(
                {
                    "choices": [
                        {"finish_reason": finish, "message": {"content": content}}
                    ],
                    "usage": {"prompt_tokens": 12, "completion_tokens": 40},
                }
            ).encode()

    llm = GroqLLM(LLMConfig())
    with (
        patch("urllib.request.urlopen", return_value=Response()),
        pytest.raises(ValueError),
    ):
        llm.complete("research", "Extraia", {}, ResearchNotes)
    assert llm.calls[0]["status"] == "error"
    assert llm.calls[0]["input_tokens"] == 12
    assert llm.calls[0]["output_tokens"] == 40


def test_run_id_cannot_escape_output_directory():
    with pytest.raises(ValidationError):
        AgentRequest(question="Pergunta documental?", run_id="../../outside")


def test_agents_env_loader_preserves_environment_and_loads_only_key(
    tmp_path, monkeypatch
):
    from src.agents.llm import load_api_key

    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("UNRELATED_SETTING", raising=False)
    env = tmp_path / ".env"
    env.write_text("# config\nUNRELATED_SETTING=ignored\nGROQ_API_KEY='test-key'\n")
    load_api_key(env)
    import os

    assert os.environ["GROQ_API_KEY"] == "test-key"
    assert "UNRELATED_SETTING" not in os.environ
    monkeypatch.setenv("GROQ_API_KEY", "existing-key")
    load_api_key(tmp_path / "missing.env")
    assert os.environ["GROQ_API_KEY"] == "existing-key"


@pytest.mark.parametrize(
    "kind,expected", [("simple", 3), ("compound", 5), ("refinement", 5)]
)
def test_research_chunk_budget_preserves_lower_score_evidence(kind, expected):
    from src.agents.schemas import EvidenceChunk

    class BudgetRetriever:
        def retrieve(self, question):
            start = (
                3 if question.startswith("o que") or question == "Complemento" else 0
            )
            return [
                EvidenceChunk(
                    source_id=f"C{i}",
                    source="rules.txt",
                    chunk_index=i,
                    text=f"Regra {i}",
                    score=0.8 - i * 0.03,
                )
                for i in range(start, start + 3)
            ]

    class BudgetLLM(SimulatedLLM):
        def complete(self, role, instructions, data, output):
            return ResearchNotes(
                facts=[],
                gaps=["Falta regra"],
                additional_queries=["Complemento"] if kind == "refinement" else [],
            )

    question = (
        "Qual a frequência e o que ocorre depois?" if kind == "compound" else "Regra?"
    )
    result = ResearchAgent(BudgetRetriever(), BudgetLLM()).execute(question)
    assert len(result.chunks) == expected
    assert len({c.source_id for c in result.chunks}) == expected
    if expected == 5:
        assert any(c.chunk_index >= 3 for c in result.chunks)


def test_anti_hallucination_low_score_abstains_without_llm():
    from src.agents.schemas import EvidenceChunk

    class LowScoreRetriever:
        def retrieve(self, question):
            return [
                EvidenceChunk(
                    source_id="C1",
                    source="edital_residencia_02.pdf",
                    chunk_index=0,
                    text="Trecho pouco relacionado à consulta.",
                    score=0.499,
                )
            ]

    result = runner(retriever=LowScoreRetriever()).run(demo_request("documental"))
    assert result.status == "abstained"
    assert result.retrieval.abstained is True
    assert result.metrics.llm_calls == 0
    assert result.proposal is None
    assert result.final_answer == ABSTENTION


def test_anti_hallucination_high_score_without_evidence_or_valid_quote_abstains():
    from src.agents.schemas import EvidenceChunk

    class HighScoreUnrelatedRetriever:
        def retrieve(self, question):
            return [
                EvidenceChunk(
                    source_id="C1",
                    source="calendario_academico_01.pdf",
                    chunk_index=0,
                    text="Feriado nacional em 15 de novembro.",
                    score=0.92,
                )
            ]

    class FabricatingResearchLLM(SimulatedLLM):
        def complete(self, role, instructions, data, output):
            if role == "research":
                return ResearchNotes(
                    facts=[
                        EvidenceFact(
                            statement="A nota mínima é 7,0.",
                            source_id="C1",
                            quote="Nota mínima exigida de 7,0 pontos.",
                        )
                    ],
                    gaps=["Regra não consta no trecho."],
                )
            return super().complete(role, instructions, data, output)

    result = runner(
        llm=FabricatingResearchLLM(), retriever=HighScoreUnrelatedRetriever()
    ).run(demo_request("correcao"))
    assert result.status == "abstained"
    assert result.retrieval.abstained is True
    assert result.retrieval.verified_facts == []
    assert result.proposal is None
    assert result.final_answer == ABSTENTION


def test_anti_hallucination_persistent_invalid_citation_abstains_without_leaking():
    from src.agents.schemas import AnalysisNotes, Claim

    class AlwaysInvalidCitationLLM(SimulatedLLM):
        def complete(self, role, instructions, data, output):
            if role == "analysis":
                return AnalysisNotes(
                    claims=[
                        Claim(
                            text="Afirmação com referência inventada.",
                            source_ids=["C999"],
                        )
                    ],
                    limitations=[],
                )
            return super().complete(role, instructions, data, output)

    llm = AlwaysInvalidCitationLLM()
    result = runner(llm=llm).run(demo_request("correcao"))
    assert result.status == "abstained"
    assert result.validation is not None
    assert result.validation.valid is False
    assert "Citação inexistente" in result.validation.violations
    assert result.final_answer == ABSTENTION
    assert "C999" not in result.final_answer
    # Validação estrutural reprova em código sem chamar o LLM de validação.
    assert not any(call["role"] == "validation" for call in llm.calls)


def test_anti_hallucination_divergent_answer_rejected_deterministically():
    from src.agents.schemas import ProposalDraft

    request = demo_request("correcao")
    retrieval = ResearchAgent(SimulatedRetriever(), SimulatedLLM()).execute(
        request.question
    )
    proposal = AnalysisPlanningAgent(SimulatedLLM()).execute(request, retrieval)
    tampered = ProposalDraft(
        claims=proposal.claims,
        limitations=proposal.limitations,
        answer="Texto alterado manualmente fora das afirmações auditáveis [C1: fixture_simulada.txt]",
        planning=proposal.planning,
    )
    llm = SimulatedLLM()
    verdict = ValidationAgent(llm).execute(request, retrieval, tampered)
    assert verdict.valid is False
    assert "Resposta diverge das afirmações auditáveis" in verdict.violations
    assert llm.calls == []


def test_anti_hallucination_conflicting_sources_keep_only_existing_refs_and_gaps():
    from src.agents.schemas import AnalysisNotes, Claim, EvidenceChunk

    class ConflictingRetriever:
        def retrieve(self, question):
            return [
                EvidenceChunk(
                    source_id="C1",
                    source="calendario_iesb.pdf",
                    chunk_index=0,
                    text="Término do semestre em 12/12/2026.",
                    score=0.81,
                ),
                EvidenceChunk(
                    source_id="C2",
                    source="calendario_unb.pdf",
                    chunk_index=0,
                    text="Fim das aulas em 14/12/2026.",
                    score=0.79,
                ),
            ]

    class ConflictAwareLLM(SimulatedLLM):
        def complete(self, role, instructions, data, output):
            if role == "research":
                return ResearchNotes(
                    facts=[
                        EvidenceFact(
                            statement="No calendário IESB, o término é 12/12/2026.",
                            source_id="C1",
                            quote="Término do semestre em 12/12/2026.",
                        ),
                        EvidenceFact(
                            statement="No calendário UnB, o fim das aulas é 14/12/2026.",
                            source_id="C2",
                            quote="Fim das aulas em 14/12/2026.",
                        ),
                    ],
                    gaps=[
                        "Fontes de instituições distintas informam datas diferentes."
                    ],
                )
            if role == "analysis":
                return AnalysisNotes(
                    claims=[
                        Claim(
                            text="O calendário IESB indica término em 12/12/2026.",
                            source_ids=["C1"],
                        ),
                        Claim(
                            text="O calendário UnB indica fim das aulas em 14/12/2026.",
                            source_ids=["C2"],
                        ),
                    ],
                    limitations=[],
                )
            return super().complete(role, instructions, data, output)

    result = runner(llm=ConflictAwareLLM(), retriever=ConflictingRetriever()).run(
        AgentRequest(question="Quando termina o semestre acadêmico?")
    )
    assert result.status == "completed"
    existing_ids = {c.source_id for c in result.retrieval.chunks}
    for claim in result.proposal.claims:
        assert set(claim.source_ids) <= existing_ids
    assert any("datas diferentes" in lim for lim in result.proposal.limitations)
    assert "Limitações:" in result.final_answer
