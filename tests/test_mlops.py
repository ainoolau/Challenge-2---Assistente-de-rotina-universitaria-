"""Testes offline da camada de observabilidade MLflow (TASK-F5-06)."""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
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
    assert "20261234" not in sanitize_mlflow_text("run-matricula-20261234")
    assert "[MATRICULA_OCULTA]" in sanitize_mlflow_text("run-matricula-20261234")
    assert "202612345" not in sanitize_mlflow_text("RA: 202612345")

    clean_metrics = sanitize_mlflow_metrics(
        {
            "mrr": 0.75,
            "chunks": 162,
            "input_tokens": 1200,
            "output_tokens": 350,
            "llm_calls": 4,
            "session_token": 999,
            "access_token": 888,
            "bad_nan": math.nan,
            "bad_inf": math.inf,
            "bool_ignored": True,
            "api_key_count": 99,
        }
    )
    assert clean_metrics == {
        "mrr": 0.75,
        "chunks": 162.0,
        "input_tokens": 1200.0,
        "output_tokens": 350.0,
        "llm_calls": 4.0,
    }


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


def test_log_multiagent_run_preserves_token_counts_and_hides_user_run_id():
    pytest.importorskip("pydantic")

    from src.agents.demo import demo_request
    from src.agents.schemas import AgentRunResult, RetrievalResult, RunMetrics

    backend = FakeMLflowBackend()
    tracker = VezoMLflowTracker(
        tracking_uri="http://localhost:5000", enabled=True, backend=backend
    )

    # run_id fornecido pelo usuário contendo matrícula nunca deve ir ao MLflow
    req = demo_request("documental").model_copy(
        update={"run_id": "run-matricula-20261234"}
    )
    result = AgentRunResult(
        run_id=req.run_id,
        request=req,
        status="completed",
        mode="live",
        config={
            "source": "api-test",
            "threshold": 0.5,
            "top_k": 3,
            "max_corrections": 1,
            "timezone": req.timezone,
            "llm": {"model": "openai/gpt-oss-20b"},
            "llm_calls": [
                {"latency_ms": 420.5, "rate_limit_wait_ms": 0.0},
                {"latency_ms": 380.0, "rate_limit_wait_ms": 150.0},
            ],
        },
        retrieval=RetrievalResult(abstained=False, top_score=0.72, chunks=[]),
        proposal=None,
        validation=None,
        final_answer="Resposta auditada.",
        trace=[],
        metrics=RunMetrics(
            total_latency_ms=950.5,
            llm_calls=2,
            input_tokens=1450,
            output_tokens=280,
        ),
    )

    assert tracker.log_multiagent_run(result) is True
    assert len(backend.runs) == 1
    logged = backend.runs[0]

    # Métricas numéricas de tokens exigidas pela issue #82 devem ser preservadas
    assert logged["metrics"]["llm_calls"] == pytest.approx(2.0)
    assert logged["metrics"]["input_tokens"] == pytest.approx(1450.0)
    assert logged["metrics"]["output_tokens"] == pytest.approx(280.0)
    assert logged["metrics"]["http_latency_ms"] == pytest.approx(800.5)
    assert logged["metrics"]["rate_limit_wait_ms"] == pytest.approx(150.0)

    # Identificador interno opaco — nenhuma parte do run_id do usuário pode vazar
    assert str(logged["run_name"]).startswith("multiagent-")
    serialized = json.dumps(logged, ensure_ascii=False)
    assert "20261234" not in serialized
    assert "matricula" not in serialized.lower()


def test_evaluate_rag_script_imports_src_without_pythonpath(tmp_path: Path):
    """Garante execução direta de `python scripts/evaluate_rag.py` sem PYTHONPATH."""
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "evaluate_rag.py"

    env = os.environ.copy()
    env.pop("PYTHONPATH", None)

    probe = (
        "import runpy, sys; "
        f"sys.path[0] = {str(script_path.parent)!r}; "
        f"ns = runpy.run_path({str(script_path)!r}, run_name='evaluate_rag_probe'); "
        "assert callable(ns['get_default_tracker']); "
        "assert callable(ns['run_evaluation'])"
    )
    proc = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"Falha ao importar evaluate_rag.py: {proc.stderr}"


def test_evaluate_rag_ignores_divergent_env_vars_and_uses_verified_collection_metadata(
    monkeypatch: pytest.MonkeyPatch,
):
    """Variáveis de ambiente divergentes não devem rotular incorretamente a coleção."""
    from scripts.evaluate_rag import build_mlflow_eval_params

    monkeypatch.setenv("VEZO_CHUNK_SIZE", "999")
    monkeypatch.setenv("VEZO_CHUNK_OVERLAP", "333")
    monkeypatch.setenv("VEZO_CHUNK_STRATEGY", "forged_strategy")
    monkeypatch.setenv("VEZO_RERANKER", "forged_reranker")

    # 1. Coleção real sem metadados de chunking -> registra "unknown" (nunca o valor do env)
    params_missing = build_mlflow_eval_params(
        [{"ingestion_version": "2.0.0", "text": "trecho real"}]
    )
    assert params_missing["ingestion_version"] == "2.0.0"
    assert params_missing["chunk_strategy"] == "unknown"
    assert params_missing["chunk_size"] == "unknown"
    assert params_missing["chunk_overlap"] == "unknown"
    assert params_missing["reranker"] == "none"

    # 2. Coleção com metadados gravados na ingestão -> usa valores reais e ignora env 999
    params_verified = build_mlflow_eval_params(
        [
            {
                "ingestion_version": "2.1.0",
                "chunk_strategy": "structural",
                "chunk_size": 800,
                "chunk_overlap": 120,
            }
        ]
    )
    assert params_verified["ingestion_version"] == "2.1.0"
    assert params_verified["chunk_strategy"] == "structural"
    assert params_verified["chunk_size"] == "800"
    assert params_verified["chunk_overlap"] == "120"
    assert params_verified["reranker"] == "none"

    # 3. Coleção com chunks heterogêneos -> sinaliza "mixed" sem mascarar divergência
    params_mixed = build_mlflow_eval_params(
        [
            {"ingestion_version": "2.0.0", "chunk_size": 500},
            {"ingestion_version": "2.1.0", "chunk_size": 800},
        ]
    )
    assert params_mixed["ingestion_version"] == "mixed"
    assert params_mixed["chunk_size"] == "mixed"
