"""Orquestração determinística com uma única rodada de correção."""

import time
import urllib.error
from dataclasses import asdict
from typing import Any

from src.mlops.tracker import get_default_tracker

from .schemas import AgentRunResult, RunMetrics, TraceEvent

ABSTENTION = "Não encontrei informações suficientes nos documentos disponíveis para responder a essa pergunta com segurança."


class MultiAgentOrchestrator:
    def __init__(
        self,
        research,
        analysis,
        validation,
        llm,
        *,
        mode="live",
        config=None,
        tracker: Any = None,
    ):
        self.research, self.analysis, self.validation, self.llm = (
            research,
            analysis,
            validation,
            llm,
        )
        self.mode, self.config = mode, config or {}
        self.tracker = tracker

    def run(self, request):
        trace = []
        retrieval = proposal = validation = None
        status, final_answer, error = "abstained", ABSTENTION, None
        start = time.perf_counter()
        call_start = len(self.llm.calls)

        def step(agent, attempt, data, action):
            t0 = time.perf_counter()
            try:
                value = action()
            except Exception as exc:
                trace.append(
                    TraceEvent(
                        step=len(trace) + 1,
                        agent=agent,
                        attempt=attempt,
                        status="error",
                        input=data,
                        output={"error_type": type(exc).__name__},
                        latency_ms=(time.perf_counter() - t0) * 1000,
                    )
                )
                raise
            trace.append(
                TraceEvent(
                    step=len(trace) + 1,
                    agent=agent,
                    attempt=attempt,
                    status="success",
                    input=data,
                    output=value.model_dump(mode="json"),
                    latency_ms=(time.perf_counter() - t0) * 1000,
                )
            )
            return value

        try:
            retrieval = step(
                "research",
                0,
                {"question": request.question},
                lambda: self.research.execute(request.question),
            )
            if not retrieval.abstained:
                corrections = []
                for attempt in range(2):
                    proposal = step(
                        "analysis",
                        attempt,
                        {
                            "request": request.model_dump(mode="json"),
                            "retrieval": retrieval.model_dump(mode="json"),
                            "corrections": corrections,
                        },
                        lambda corrections=corrections: self.analysis.execute(
                            request, retrieval, corrections
                        ),
                    )
                    validation = step(
                        "validation",
                        attempt,
                        {
                            "proposal": proposal.model_dump(mode="json"),
                            "source_ids": retrieval.citations,
                        },
                        lambda proposal=proposal, attempt=attempt: (
                            self.validation.execute(
                                request, retrieval, proposal, attempt
                            )
                        ),
                    )
                    if validation.valid:
                        status, final_answer = "completed", proposal.answer
                        if proposal.limitations:
                            final_answer += "\n\nLimitações: " + "; ".join(
                                proposal.limitations
                            )
                        if proposal.planning:
                            final_answer += "\n\nProposta de estudo (não aplicada; requer confirmação):"
                            for block in proposal.planning.proposed_blocks:
                                final_answer += f"\n- {block.title}: {block.start.isoformat()} a {block.end.isoformat()}"
                            final_answer += "\n" + proposal.planning.diff_summary
                        break
                    corrections = validation.corrections_needed
        except Exception as exc:
            status = "error"
            final_answer = (
                "Não foi possível concluir o fluxo. Nenhuma agenda foi alterada."
            )
            # Nunca serializar corpo HTTP, prompt ou credenciais em mensagens de erro.
            error = {
                "type": type(exc).__name__,
                "message": "Falha em etapa multiagente; consulte o trace sanitizado"
                + (
                    f" (HTTP {exc.code})"
                    if isinstance(exc, urllib.error.HTTPError)
                    else ""
                ),
            }
        calls = self.llm.calls[call_start:]

        def tokens(key):
            values = [call.get(key) for call in calls]
            return None if any(v is None for v in values) else sum(values)

        config = dict(self.config)
        if hasattr(self.llm, "config"):
            config["llm"] = asdict(self.llm.config)
        config.update(
            threshold=self.research.threshold,
            max_corrections=1,
            top_k=3,
            llm_calls=calls,
            timezone=request.timezone,
        )
        result = AgentRunResult(
            run_id=request.run_id,
            request=request,
            status=status,
            mode=self.mode,
            config=config,
            retrieval=retrieval,
            proposal=proposal,
            validation=validation,
            final_answer=final_answer,
            trace=trace,
            metrics=RunMetrics(
                total_latency_ms=(time.perf_counter() - start) * 1000,
                llm_calls=len(calls),
                input_tokens=tokens("input_tokens"),
                output_tokens=tokens("output_tokens"),
            ),
            error=error,
        )
        active_tracker = (
            self.tracker
            if self.tracker is not None
            else (get_default_tracker() if self.mode == "live" else None)
        )
        if active_tracker is not None:
            try:
                active_tracker.log_multiagent_run(result)
            except Exception:
                pass
        return result
