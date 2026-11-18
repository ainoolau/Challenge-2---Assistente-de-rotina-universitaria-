"""Cenários fictícios explícitos para demonstração e testes reproduzíveis."""

from .schemas import (
    AgentRequest,
    AnalysisNotes,
    Claim,
    EvidenceChunk,
    EvidenceFact,
    ResearchNotes,
    ValidationNotes,
)

QUESTIONS = {
    "documental": "Qual é a frequência mínima exigida na residência e o que acontece após três advertências?",
    "planejamento": "Tenho prova de Econometria na próxima semana. Quando é a aula e como encaixar estudos sem mexer no meu sono?",
    "fora_dominio": "Qual é a nota de corte do vestibular de Medicina da UnB?",
    "correcao": "Qual é a frequência mínima exigida na residência?",
}


def demo_request(scenario):
    data = {"question": QUESTIONS[scenario]}
    if scenario == "planejamento":
        data.update(
            horizon={
                "start": "2026-11-17T06:00:00-03:00",
                "end": "2026-11-20T22:00:00-03:00",
            },
            study_goals=[
                {
                    "goal_id": "econometria",
                    "title": "Estudo de Econometria",
                    "duration_minutes": 240,
                    "deadline": "2026-11-20T20:00:00-03:00",
                }
            ],
            schedule_slots=[
                {
                    "start": f"2026-11-{day}T08:00:00-03:00",
                    "end": f"2026-11-{day}T18:00:00-03:00",
                    "label": "CLT fictício",
                    "kind": "work",
                }
                for day in (17, 19)
            ]
            + [
                {
                    "start": f"2026-11-{day}T08:00:00-03:00",
                    "end": f"2026-11-{day}T09:50:00-03:00",
                    "label": "Aula de Econometria informada (conflita com CLT)",
                    "kind": "class",
                }
                for day in (17, 19)
            ]
            + [
                {
                    "start": "2026-11-17T06:30:00-03:00",
                    "end": "2026-11-17T07:30:00-03:00",
                    "label": "Deslocamento fictício",
                    "kind": "commute",
                },
            ],
        )
    return AgentRequest.model_validate(data)


class SimulatedRetriever:
    def retrieve(self, question):
        if "Medicina" in question:
            return [
                EvidenceChunk(
                    source_id="C1",
                    source="fixture_simulada.txt",
                    text="Texto fictício sem nota de corte.",
                    score=0.2,
                )
            ]
        if "Econometria" in question:
            text = "Na agenda fictícia, a aula de Econometria ocorre terça e quinta, das 08h às 09h50."
        else:
            text = "Regra fictícia para teste: frequência mínima de 90%. Três advertências levam ao desligamento."
        return [
            EvidenceChunk(
                source_id="C1", source="fixture_simulada.txt", text=text, score=0.8
            )
        ]


class SimulatedLLM:
    """Double de teste; não mede qualidade de LLM nem usa rede."""

    def __init__(self, force_correction=False):
        self.calls = []
        self.force_correction = force_correction
        self.analysis_count = 0

    def complete(self, role, instructions, data, output):
        self.calls.append(
            {
                "role": role,
                "status": "success",
                "input_tokens": None,
                "output_tokens": None,
                "latency_ms": 0.0,
                "simulated": True,
            }
        )
        if role == "research":
            chunk = data["chunks"][0]
            result = ResearchNotes(
                facts=[
                    EvidenceFact(
                        statement=chunk["text"],
                        source_id=chunk["source_id"],
                        quote=chunk["text"],
                    )
                ],
                gaps=[],
            )
        elif role == "analysis":
            self.analysis_count += 1
            fact = data["retrieval"]["verified_facts"][0]
            source_id = (
                "C999"
                if self.force_correction and self.analysis_count == 1
                else fact["source_id"]
            )
            result = AnalysisNotes(
                claims=[Claim(text=fact["statement"], source_ids=[source_id])],
                limitations=[],
            )
        else:
            result = ValidationNotes(
                factual_ok=True, violations=[], corrections_needed=[]
            )
        return output.model_validate(result.model_dump())
