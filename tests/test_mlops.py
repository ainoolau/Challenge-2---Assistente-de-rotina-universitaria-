"""Testes offline da camada de observabilidade MLflow (TASK-F5-06)."""

from __future__ import annotations

import json
import math
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

import pytest

from src.mlops.tracker import (
    DEFAULT_INGESTION_EXPERIMENT,
    DEFAULT_MULTIAGENT_EXPERIMENT,
    DEFAULT_RETRIEVAL_EXPERIMENT,
    VezoMLflowTracker,
    sanitize_mlflow_metrics,
    sanitize_mlflow_params,
    sanitize_mlflow_text,
)


class FakeMLflowBackend:
    """Backend MLflow em memória para testes determinísticos sem rede."""

    def __init__(self, *, fail_on_log: bool = False) -> None:
        self.fail_on_log = fail_on_log
        self.tracking_uri: str | None = None
        self.experiment: str | None = None
        self.runs: list[dict[str, Any]] = []
        self._active: dict[str, Any] | None = None

    def set_tracking_uri(self, uri: str) -> None:
        self.tracking_uri = uri

    def set_experiment(self, experiment_name: str) -> None:
        self.experiment = experiment_name

    @contextmanager
    def start_run(self, *, run_name: str | None = None):
        if self.fail_on_log:
            raise RuntimeError("MLflow backend indisponível")
        run = {
            "experiment": self.experiment,
            "run_name": run_name,
            "params": {},
            "metrics": {},
            "tags": {},
        }
        self._active = run
        try:
            yield run
            self.runs.append(run)
        finally:
            self._active = None

    def log_params(self, params: dict[str, Any]) -> None:
        assert self._active is not None
        self._active["params"].update(params)

    def log_metrics(self, metrics: dict[str, float]) -> None:
        assert self._active is not None
        self._active["metrics"].update(metrics)

    def set_tags(self, tags: dict[str, Any]) -> None:
        assert self._active is not None
        self._active["tags"].update(tags)


def test_noop_when_disabled_or_server_unreachable(monkeypatch: pytest.MonkeyPatch):
    backend = FakeMLflowBackend()
    disabled = VezoMLflowTracker(enabled=False, backend=backend)
    assert not disabled.is_available()
    assert not disabled.log_retrieval_evaluation(metrics={"mrr": 0.72})
    assert backend.runs == []

    # Sem backend injetado + probe HTTP retornando False -> fallback silencioso seguro
    monkeypatch.setattr("src.mlops.tracker._probe_http_health", lambda *_a, **_k: False)
    offline = VezoMLflowTracker(
        tracking_uri="http://127.0.0.1:59999", enabled=True, timeout=0.05
    )
    assert not offline.is_available()
    assert not offline.log_retrieval_evaluation(metrics={"mrr": 0.72})


def test_backend_exception_is_swallowed_safely():
    broken = FakeMLflowBackend(fail_on_log=True)
    tracker = VezoMLflowTracker(
        tracking_uri="http://localhost:5000", enabled=True, backend=broken
    )
    assert tracker.log_retrieval_evaluation(metrics={"mrr": 0.8}) is False
    assert broken.runs == []


def test_sanitization_blocks_secrets_pii_prompts_and_non_finite_metrics():
    raw_params = {
        "embedding_model": "paraphrase-multilingual-MiniLM-L12-v2",
        "groq_api_key": "gsk_supersecretkey1234567890",
        "session_token": "tok_sensitive_999",
        "question": "Qual o CPF 123.456.789-00 do aluno?",
        "final_answer": "O e-mail é teste@unb.br",
        "prompt": "System prompt secreto",
        "note": (
            "Chave gsk_leak9999999999 CPF 123.456.789-00 "
            "email aluno@unb.br tel (61) 99999-8888 Bearer tok_abcdefgh123"
        ),
        "nan_val": float("nan"),
        "flag": True,
    }
    clean_params = sanitize_mlflow_params(raw_params)

    for forbidden in (
        "groq_api_key",
        "session_token",
        "question",
        "final_answer",
        "prompt",
        "nan_val",
    ):
        assert forbidden not in clean_params

    assert clean_params["embedding_model"] == "paraphrase-multilingual-MiniLM-L12-v2"
    assert clean_params["flag"] == "true"

    note = clean_params["note"]
    assert "gsk_leak9999999999" not in note
    assert "123.456.789-00" not in note
    assert "aluno@unb.br" not in note
    assert "99999-8888" not in note
    assert "tok_abcdefgh123" not in note
    assert "[REDACTED_KEY]" in note
    assert "[CPF_OCULTO]" in note
    assert "[EMAIL_OCULTO]" in note
    assert "[TELEFONE_OCULTO]" in note
    assert "[REDACTED_TOKEN]" in note

    assert sanitize_mlflow_text("x" * 300, max_length=20).endswith("...")

    clean_metrics = sanitize_mlflow_metrics(
        {
            "mrr": 0.75,
            "chunks": 162,
            "bad_nan": math.nan,
            "bad_inf": math.inf,
            "bool_ignored": True,
            "api_key_count": 99,
        }
    )
    assert clean_metrics == {"mrr": 0.75, "chunks": 162.0}


def test_log_retrieval_evaluation_and_ingestion_summary():
    backend = FakeMLflowBackend()
    tracker = VezoMLflowTracker(
        tracking_uri="http://localhost:5000", enabled=True, backend=backend
    )

    ok_eval = tracker.log_retrieval_evaluation(
        metrics={
            "hit_rate_at_1": 63.6,
            "hit_rate_at_3": 90.9,
            "hit_rate_at_5": 100.0,
            "mrr": 0.7197,
            "avg_latency_ms": 49.68,
            "chunk_count": 162,
            "negative_top_score": 0.4328,
        },
        params={
            "embedding_model": "paraphrase-multilingual-MiniLM-L12-v2",
            "ingestion_version": "2.0.0",
            "chunk_strategy": "fixed_500_50",
            "chunk_size": 500,
            "chunk_overlap": 50,
            "top_k": 3,
            "threshold": 0.50,
        },
    )
    assert ok_eval is True
    assert len(backend.runs) == 1
    eval_run = backend.runs[0]
    assert eval_run["experiment"] == DEFAULT_RETRIEVAL_EXPERIMENT
    assert eval_run["metrics"]["hit_rate_at_3"] == pytest.approx(90.9)
    assert eval_run["metrics"]["mrr"] == pytest.approx(0.7197)
    assert eval_run["metrics"]["chunk_count"] == pytest.approx(162.0)
    assert eval_run["params"]["ingestion_version"] == "2.0.0"

    @dataclass
    class FakeSummary:
        collection: str = "rotina_estudante_multimodal"
        ingestion_version: str = "2.0.0"
        processed_files: int = 25
        skipped_unchanged: int = 0
        deduplicated_files: int = 0
        failed_files: int = 0
        total_chunks_upserted: int = 162
        orphan_chunks_deleted: int = 0
        points_in_collection: int = 162
        pii_redactions: dict[str, int] = field(default_factory=lambda: {"cpf": 2})
        quality_warnings: list[str] = field(default_factory=list)

    ok_ing = tracker.log_ingestion_run(
        FakeSummary(), params={"chunk_size": 500, "chunk_overlap": 50}
    )
    assert ok_ing is True
    assert len(backend.runs) == 2
    ing_run = backend.runs[1]
    assert ing_run["experiment"] == DEFAULT_INGESTION_EXPERIMENT
    assert ing_run["metrics"]["points_in_collection"] == pytest.approx(162.0)
    assert ing_run["metrics"]["pii_redactions_total"] == pytest.approx(2.0)


def test_orchestrator_logs_sanitized_multiagent_metrics_without_pii_or_secrets():
    pytest.importorskip("pydantic")

    from src.agents.analysis_planning_agent import AnalysisPlanningAgent
    from src.agents.demo import SimulatedLLM, SimulatedRetriever, demo_request
    from src.agents.orchestrator import MultiAgentOrchestrator
    from src.agents.research_agent import ResearchAgent
    from src.agents.validation_agent import ValidationAgent

    backend = FakeMLflowBackend()
    tracker = VezoMLflowTracker(
        tracking_uri="http://localhost:5000", enabled=True, backend=backend
    )

    llm = SimulatedLLM()
    orch = MultiAgentOrchestrator(
        ResearchAgent(SimulatedRetriever(), llm),
        AnalysisPlanningAgent(llm),
        ValidationAgent(llm),
        llm,
        mode="simulated",
        config={"source": "test-suite", "api_key": "gsk_must_never_leak_9999"},
        tracker=tracker,
    )

    # Injeta pergunta contendo texto sensível para comprovar que nunca vai ao MLflow
    doc_req = demo_request("documental").model_copy(
        update={
            "question": (
                "Qual a frequência mínima da residência? "
                "(CPF 123.456.789-00, email secreto@unb.br)"
            )
        }
    )
    res_doc = orch.run(doc_req)
    res_oos = orch.run(demo_request("fora_dominio"))

    llm_corr = SimulatedLLM(force_correction=True)
    orch_corr = MultiAgentOrchestrator(
        ResearchAgent(SimulatedRetriever(), llm_corr),
        AnalysisPlanningAgent(llm_corr),
        ValidationAgent(llm_corr),
        llm_corr,
        mode="simulated",
        config={"source": "test-correction"},
        tracker=tracker,
    )
    res_corr = orch_corr.run(demo_request("correcao"))

    assert res_doc.status == "completed"
    assert res_oos.status == "abstained"
    assert res_corr.status == "completed"
    assert len(backend.runs) == 3

    doc_run, oos_run, corr_run = backend.runs
    assert doc_run["experiment"] == DEFAULT_MULTIAGENT_EXPERIMENT
    assert doc_run["params"]["status"] == "completed"
    assert doc_run["metrics"]["llm_calls"] >= 1.0
    assert doc_run["metrics"]["total_latency_ms"] >= 0.0
    assert doc_run["metrics"]["top_score"] >= 0.50
    assert doc_run["metrics"]["completed_flag"] == 1.0
    assert doc_run["metrics"]["corrections_count"] == 0.0

    assert oos_run["params"]["status"] == "abstained"
    assert oos_run["metrics"]["llm_calls"] == 0.0
    assert oos_run["metrics"]["abstained_flag"] == 1.0

    assert corr_run["params"]["status"] == "completed"
    assert corr_run["metrics"]["corrections_count"] == 1.0

    serialized = json.dumps(backend.runs, ensure_ascii=False)
    for forbidden_value in (
        "123.456.789-00",
        "secreto@unb.br",
        "gsk_must_never_leak_9999",
        "Qual a frequência mínima",
    ):
        assert forbidden_value not in serialized

    # Falha inesperada no tracker jamais derruba o orquestrador
    class CrashingTracker:
        def log_multiagent_run(self, _result: Any) -> bool:
            raise RuntimeError("falha simulada no tracker")

    resilient = MultiAgentOrchestrator(
        ResearchAgent(SimulatedRetriever(), SimulatedLLM()),
        AnalysisPlanningAgent(SimulatedLLM()),
        ValidationAgent(SimulatedLLM()),
        SimulatedLLM(),
        mode="simulated",
        tracker=CrashingTracker(),
    )
    safe_result = resilient.run(demo_request("fora_dominio"))
    assert safe_result.status == "abstained"
