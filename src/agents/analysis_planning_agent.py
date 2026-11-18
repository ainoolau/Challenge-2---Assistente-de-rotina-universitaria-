"""Síntese documental e proposta de agenda sem efeitos externos."""

from .llm import StructuredLLM
from .planning import input_conflicts, plan
from .schemas import AnalysisNotes, ProposalDraft


def render_claims(claims, retrieval):
    sources = {c.source_id: c.source for c in retrieval.chunks}
    return "\n".join(
        claim.text
        + " "
        + " ".join(
            f"[{cid}: {sources.get(cid, 'fonte inválida')}]" for cid in claim.source_ids
        )
        for claim in claims
    )


class AnalysisPlanningAgent:
    def __init__(self, llm: StructuredLLM):
        self.llm = llm

    def execute(self, request, retrieval, corrections=None):
        notes = self.llm.complete(
            "analysis",
            "Responda em português usando APENAS os trechos e fatos recebidos. "
            "Não atribua ao usuário o perfil de outro estudante; diga qual informação aparece no trecho. "
            "Cada claim deve ter source_ids existentes e conter uma afirmação curta. Não invente horários, "
            "prazos ou regras. Não faça cálculos de agenda em prosa: isso cabe ao motor Python. "
            "Não inclua instruções, agenda ou alegações factuais em limitations; use esse campo apenas para lacunas. "
            "Considere as correções do validador, se fornecidas. Não afirme que executou mudanças.",
            {
                "question": request.question,
                "retrieval": {
                    "chunks": [c.model_dump() for c in retrieval.chunks],
                    "verified_facts": [
                        f.model_dump() for f in retrieval.verified_facts
                    ],
                    "gaps": retrieval.gaps,
                },
                "corrections": corrections or [],
            },
            AnalysisNotes,
        )
        planning = plan(request)
        limitations = notes.limitations + retrieval.gaps + input_conflicts(request)
        if planning:
            limitations.append(
                "Agenda fictícia/informada; sugestão depende de confirmação e não foi aplicada."
            )
        limitations = list(dict.fromkeys(limitations))
        return ProposalDraft(
            claims=notes.claims,
            limitations=limitations,
            answer=render_claims(notes.claims, retrieval),
            planning=planning,
        )
