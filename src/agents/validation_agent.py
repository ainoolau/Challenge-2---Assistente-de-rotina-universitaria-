"""Auditoria semântica por LLM e invariantes por código."""

from .analysis_planning_agent import render_claims
from .llm import StructuredLLM
from .planning import audit_plan
from .schemas import ValidationNotes, ValidationResult


class ValidationAgent:
    def __init__(self, llm: StructuredLLM):
        self.llm = llm

    def execute(self, request, retrieval, proposal, attempt=0):
        ids = {c.source_id for c in retrieval.chunks}
        structural = []
        if not proposal.claims:
            structural.append("Resposta sem afirmações documentais")
        for claim in proposal.claims:
            if not set(claim.source_ids) <= ids:
                structural.append("Citação inexistente")
        if proposal.answer != render_claims(proposal.claims, retrieval):
            structural.append("Resposta diverge das afirmações auditáveis")
        schedule_errors = audit_plan(request, proposal.planning)
        if structural or schedule_errors:
            violations = list(dict.fromkeys(structural + schedule_errors))
            return ValidationResult(
                valid=False,
                factual_ok=not structural,
                invariants_ok=not schedule_errors,
                violations=violations,
                corrections_needed=violations,
                attempt=attempt,
            )
        notes = self.llm.complete(
            "validation",
            "Audite em português a resposta e as limitations contra os trechos originais. "
            "Confira cada número, regra, data e associação de pessoa. Citação existente não comprova "
            "que a afirmação é verdadeira. Reprove qualquer afirmação sem apoio, instrução indevida, "
            "prazo inferido ou lacuna relevante omitida. Não use conhecimento externo. "
            "As limitações também não podem introduzir fatos sem fonte. factual_ok só é true se tudo estiver sustentado.",
            {
                "question": request.question,
                "chunks": [c.model_dump() for c in retrieval.chunks],
                "proposal": proposal.model_dump(mode="json"),
            },
            ValidationNotes,
        )
        valid = (
            notes.factual_ok and not notes.violations and not notes.corrections_needed
        )
        corrections = notes.corrections_needed or notes.violations
        if not valid and not corrections:
            corrections = ["Reescrever somente afirmações sustentadas pelos trechos"]
        return ValidationResult(
            valid=valid,
            factual_ok=notes.factual_ok,
            invariants_ok=True,
            violations=notes.violations,
            corrections_needed=corrections,
            attempt=attempt,
        )
