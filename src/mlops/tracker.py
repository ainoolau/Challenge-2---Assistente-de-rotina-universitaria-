"""Rastreamento MLflow para retrieval, ingestão e sistema multiagentes (TASK-F5-06).

Regras obrigatórias de operação e segurança:
- Fallback silencioso seguro (*no-op*) quando `mlflow` não estiver instalado,
  quando `VEZO_MLFLOW_ENABLED=false` ou quando o servidor MLflow estiver offline.
- Nunca lança exceção que interrompa ingestão, avaliação ou `MultiAgentOrchestrator`.
- Nunca registra chaves (`GROQ_API_KEY`, tokens), prompts, perguntas do usuário,
  respostas textuais, trechos de documentos ou PII (CPF, e-mail, telefone, matrícula).
"""

from __future__ import annotations

import math
import os
import re
import urllib.request
from contextlib import AbstractContextManager
from typing import Any, Protocol
from uuid import uuid4

DEFAULT_MLFLOW_URI = "http://localhost:5000"
DEFAULT_RETRIEVAL_EXPERIMENT = "vezo-retrieval-evaluation"
DEFAULT_INGESTION_EXPERIMENT = "vezo-ingestion"
DEFAULT_MULTIAGENT_EXPERIMENT = "vezo-multiagents"

_ALLOWED_TOKEN_COUNT_METRICS = frozenset(
    {
        "input_tokens",
        "output_tokens",
        "total_tokens",
    }
)

_FORBIDDEN_KEY_FRAGMENTS = (
    "api_key",
    "apikey",
    "secret",
    "token",
    "password",
    "passwd",
    "authorization",
    "cookie",
    "prompt",
    "question",
    "answer",
    "quote",
    "text",
    "content",
    "cpf",
    "email",
    "phone",
    "telefone",
    "matricula",
    "schedule_slots",
    "study_goals",
)

_SECRET_AND_PII_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bgsk_[A-Za-z0-9_-]{8,}\b"), "[REDACTED_KEY]"),
    (re.compile(r"\bBearer\s+[A-Za-z0-9._-]{8,}\b", re.IGNORECASE), "[REDACTED_TOKEN]"),
    (re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b"), "[CPF_OCULTO]"),
    (
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
        "[EMAIL_OCULTO]",
    ),
    (
        re.compile(
            r"(?<!\d)(?:\+?55\s?)?(?:\(?\d{2}\)?\s?)(?:9\d{4}|\d{4})-?\d{4}(?!\d)"
        ),
        "[TELEFONE_OCULTO]",
    ),
    (
        re.compile(r"(?i)\b(matr[íi]cula|ra|rga)(\s*[:#_-]?\s*)(\d[\d./-]{3,20})\b"),
        r"\1\2[MATRICULA_OCULTA]",
    ),
)

_MAX_PARAM_LEN = 250


class MLflowBackend(Protocol):
    """Subconjunto mínimo da API do módulo `mlflow` usado pelo tracker."""

    def set_tracking_uri(self, uri: str) -> Any: ...

    def set_experiment(self, experiment_name: str) -> Any: ...

    def start_run(
        self, *, run_name: str | None = None
    ) -> AbstractContextManager[Any]: ...

    def log_params(self, params: dict[str, Any]) -> Any: ...

    def log_metrics(self, metrics: dict[str, float]) -> Any: ...

    def set_tags(self, tags: dict[str, Any]) -> Any: ...


def sanitize_mlflow_text(value: str, *, max_length: int = _MAX_PARAM_LEN) -> str:
    """Remove padrões de credenciais/PII e limita o tamanho de strings logadas."""
    cleaned = " ".join(str(value).split())
    for pattern, replacement in _SECRET_AND_PII_PATTERNS:
        cleaned = pattern.sub(replacement, cleaned)
    if len(cleaned) > max_length:
        cleaned = cleaned[: max_length - 3] + "..."
    return cleaned


def _is_forbidden_key(key: str) -> bool:
    normalized = key.strip().lower()
    if not normalized:
        return True
    return any(fragment in normalized for fragment in _FORBIDDEN_KEY_FRAGMENTS)


def sanitize_mlflow_params(params: dict[str, Any] | None) -> dict[str, str]:
    """Filtra chaves sensíveis e serializa valores seguros para `mlflow.log_params`."""
    if not params:
        return {}
    safe: dict[str, str] = {}
    for raw_key, raw_val in params.items():
        key = str(raw_key).strip()
        if _is_forbidden_key(key) or raw_val is None:
            continue
        if isinstance(raw_val, bool):
            safe[key] = "true" if raw_val else "false"
        elif isinstance(raw_val, (int, float)):
            if isinstance(raw_val, float) and not math.isfinite(raw_val):
                continue
            safe[key] = str(raw_val)
        else:
            safe[key] = sanitize_mlflow_text(str(raw_val))
    return safe


def sanitize_mlflow_metrics(metrics: dict[str, Any] | None) -> dict[str, float]:
    """Converte e mantém apenas métricas numéricas finitas e chaves não sensíveis."""
    if not metrics:
        return {}
    safe: dict[str, float] = {}
    for raw_key, raw_val in metrics.items():
        key = str(raw_key).strip()
        normalized = key.lower()
        if (
            (_is_forbidden_key(key) and normalized not in _ALLOWED_TOKEN_COUNT_METRICS)
            or raw_val is None
            or isinstance(raw_val, bool)
        ):
            continue
        if isinstance(raw_val, (int, float)):
            val = float(raw_val)
            if math.isfinite(val):
                safe[key] = val
    return safe


def _probe_http_health(tracking_uri: str, timeout: float) -> bool:
    """Verifica rapidamente se o servidor MLflow HTTP está alcançável."""
    base = tracking_uri.rstrip("/")
    req = urllib.request.Request(
        f"{base}/health",
        headers={"User-Agent": "vezo-mlops-tracker/1.0"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= int(resp.status) < 300
    except Exception:
        return False


def _env_enabled() -> bool:
    raw = os.getenv("VEZO_MLFLOW_ENABLED", "true").strip().lower()
    return raw not in {"0", "false", "no", "off"}


class VezoMLflowTracker:
    """Cliente MLflow resiliente (no-op seguro) e sanitizado para o Vezo."""

    def __init__(
        self,
        tracking_uri: str | None = None,
        *,
        enabled: bool | None = None,
        timeout: float = 0.5,
        backend: MLflowBackend | None = None,
    ) -> None:
        self.tracking_uri = (
            tracking_uri
            if tracking_uri is not None
            else os.getenv("MLFLOW_TRACKING_URI", DEFAULT_MLFLOW_URI)
        )
        self.enabled = _env_enabled() if enabled is None else enabled
        self.timeout = max(0.05, float(timeout))
        self._injected_backend = backend

    def _load_backend(self) -> MLflowBackend | None:
        if self._injected_backend is not None:
            return self._injected_backend
        try:
            import mlflow  # type: ignore[import-not-found]
        except Exception:
            return None
        return mlflow

    def is_available(self) -> bool:
        """Retorna True somente se o tracker estiver ativo e o destino acessível."""
        if not self.enabled or not self.tracking_uri:
            return False
        if self._load_backend() is None:
            return False
        if self._injected_backend is not None:
            return True
        lowered = self.tracking_uri.lower()
        if lowered.startswith(("http://", "https://")):
            return _probe_http_health(self.tracking_uri, timeout=self.timeout)
        return True

    def _record_run(
        self,
        *,
        experiment_name: str,
        run_name: str | None,
        params: dict[str, Any] | None,
        metrics: dict[str, Any] | None,
        tags: dict[str, Any] | None,
    ) -> bool:
        if not self.is_available():
            return False

        backend = self._load_backend()
        if backend is None:
            return False

        safe_params = sanitize_mlflow_params(params)
        safe_metrics = sanitize_mlflow_metrics(metrics)
        safe_tags = sanitize_mlflow_params(tags)
        safe_run_name = (
            sanitize_mlflow_text(run_name, max_length=120) if run_name else None
        )

        try:
            backend.set_tracking_uri(self.tracking_uri)
            backend.set_experiment(experiment_name)
            with backend.start_run(run_name=safe_run_name):
                if safe_params:
                    backend.log_params(safe_params)
                if safe_metrics:
                    backend.log_metrics(safe_metrics)
                if safe_tags:
                    backend.set_tags(safe_tags)
            return True
        except Exception:
            return False

    def log_retrieval_evaluation(
        self,
        *,
        metrics: dict[str, Any],
        params: dict[str, Any] | None = None,
        tags: dict[str, Any] | None = None,
        experiment_name: str = DEFAULT_RETRIEVAL_EXPERIMENT,
        run_name: str | None = None,
    ) -> bool:
        """Registra benchmark de retrieval (Hit@1/3/5, MRR, latência, chunking)."""
        merged_tags = {"component": "retrieval_evaluation", **(tags or {})}
        return self._record_run(
            experiment_name=experiment_name,
            run_name=run_name or "retrieval-eval",
            params=params,
            metrics=metrics,
            tags=merged_tags,
        )

    def log_ingestion_run(
        self,
        summary: Any,
        *,
        params: dict[str, Any] | None = None,
        tags: dict[str, Any] | None = None,
        experiment_name: str = DEFAULT_INGESTION_EXPERIMENT,
        run_name: str | None = None,
    ) -> bool:
        """Registra métricas agregadas de uma carga batch de ingestão (sem PII)."""
        pii_redactions = getattr(summary, "pii_redactions", None) or {}
        pii_total = (
            sum(int(v) for v in pii_redactions.values())
            if isinstance(pii_redactions, dict)
            else 0
        )
        run_params: dict[str, Any] = {
            "collection": getattr(summary, "collection", None),
            "ingestion_version": getattr(summary, "ingestion_version", None),
            **(params or {}),
        }
        run_metrics: dict[str, Any] = {
            "processed_files": getattr(summary, "processed_files", 0),
            "skipped_unchanged": getattr(summary, "skipped_unchanged", 0),
            "deduplicated_files": getattr(summary, "deduplicated_files", 0),
            "failed_files": getattr(summary, "failed_files", 0),
            "total_chunks_upserted": getattr(summary, "total_chunks_upserted", 0),
            "orphan_chunks_deleted": getattr(summary, "orphan_chunks_deleted", 0),
            "points_in_collection": getattr(summary, "points_in_collection", 0),
            "pii_redactions_total": pii_total,
            "quality_warnings_count": len(
                getattr(summary, "quality_warnings", None) or []
            ),
        }
        merged_tags = {"component": "ingestion", **(tags or {})}
        return self._record_run(
            experiment_name=experiment_name,
            run_name=run_name or "ingestion-batch",
            params=run_params,
            metrics=run_metrics,
            tags=merged_tags,
        )

    def log_multiagent_run(
        self,
        result: Any,
        *,
        tags: dict[str, Any] | None = None,
        experiment_name: str = DEFAULT_MULTIAGENT_EXPERIMENT,
        run_name: str | None = None,
    ) -> bool:
        """Registra telemetria sanitizada de uma execução do `MultiAgentOrchestrator`."""
        config = getattr(result, "config", None) or {}
        metrics_obj = getattr(result, "metrics", None)
        retrieval = getattr(result, "retrieval", None)
        proposal = getattr(result, "proposal", None)
        validation = getattr(result, "validation", None)
        trace = getattr(result, "trace", None) or []

        llm_calls_raw = config.get("llm_calls") if isinstance(config, dict) else []
        llm_calls_list = llm_calls_raw if isinstance(llm_calls_raw, list) else []

        http_latency_ms = sum(
            float(call["latency_ms"])
            for call in llm_calls_list
            if isinstance(call, dict)
            and isinstance(call.get("latency_ms"), (int, float))
        )
        rate_limit_wait_ms = sum(
            float(call["rate_limit_wait_ms"])
            for call in llm_calls_list
            if isinstance(call, dict)
            and isinstance(call.get("rate_limit_wait_ms"), (int, float))
        )

        corrections_count = sum(
            1
            for event in trace
            if getattr(event, "agent", None) == "analysis"
            and int(getattr(event, "attempt", 0)) > 0
        )

        status_str = str(getattr(result, "status", "unknown"))
        mode_str = str(getattr(result, "mode", "unknown"))
        llm_cfg = config.get("llm") if isinstance(config, dict) else None
        llm_model = llm_cfg.get("model") if isinstance(llm_cfg, dict) else None

        run_params: dict[str, Any] = {
            "mode": mode_str,
            "status": status_str,
            "source": config.get("source") if isinstance(config, dict) else None,
            "llm_model": llm_model,
            "threshold": config.get("threshold") if isinstance(config, dict) else None,
            "top_k": config.get("top_k") if isinstance(config, dict) else None,
            "max_corrections": (
                config.get("max_corrections") if isinstance(config, dict) else None
            ),
            "timezone": config.get("timezone") if isinstance(config, dict) else None,
            "has_planning": bool(getattr(proposal, "planning", None) is not None),
            "validation_valid": (
                bool(getattr(validation, "valid", False))
                if validation is not None
                else None
            ),
        }

        run_metrics: dict[str, Any] = {
            "total_latency_ms": getattr(metrics_obj, "total_latency_ms", None),
            "http_latency_ms": http_latency_ms,
            "rate_limit_wait_ms": rate_limit_wait_ms,
            "llm_calls": getattr(metrics_obj, "llm_calls", 0),
            "input_tokens": getattr(metrics_obj, "input_tokens", None),
            "output_tokens": getattr(metrics_obj, "output_tokens", None),
            "top_score": getattr(retrieval, "top_score", None),
            "chunks_count": len(getattr(retrieval, "chunks", None) or []),
            "citations_count": len(getattr(retrieval, "citations", None) or []),
            "gaps_count": len(getattr(retrieval, "gaps", None) or []),
            "corrections_count": corrections_count,
            "abstained_flag": 1.0 if status_str == "abstained" else 0.0,
            "completed_flag": 1.0 if status_str == "completed" else 0.0,
            "error_flag": 1.0 if status_str == "error" else 0.0,
        }

        # Gera identificador interno opaco para telemetria; nunca propaga
        # `result.run_id` informado pelo usuário (pode conter matrícula/PII).
        telemetry_run_name = run_name or f"multiagent-{uuid4().hex[:12]}"
        merged_tags = {
            "component": "multiagent_orchestrator",
            "mode": mode_str,
            "status": status_str,
            **(tags or {}),
        }
        return self._record_run(
            experiment_name=experiment_name,
            run_name=telemetry_run_name,
            params=run_params,
            metrics=run_metrics,
            tags=merged_tags,
        )


def get_default_tracker() -> VezoMLflowTracker:
    """Instancia o tracker padrão configurado via variáveis de ambiente."""
    return VezoMLflowTracker()
