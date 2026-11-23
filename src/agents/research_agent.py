"""Pesquisa: recuperação existente, gate pré-LLM e extração com citações."""

import re
from pathlib import PureWindowsPath
from typing import Protocol

from .llm import StructuredLLM
from .schemas import EvidenceChunk, ResearchNotes, RetrievalResult


def normalize(text):
    return " ".join(text.split()).casefold()


class Retriever(Protocol):
    def retrieve(self, question: str) -> list[EvidenceChunk]: ...


class QdrantRetriever:
    def __init__(self, local_path=None, collection=None, user_id=None):
        # Imports tardios: testes simulados não abrem banco nem carregam modelos.
        from qdrant_client.models import Distance

        from src.data_pipeline.retrieval import (
            DEFAULT_COLLECTION,
            get_client,
            load_embedder,
        )

        self.collection = collection or DEFAULT_COLLECTION
        self.user_id = user_id
        if self.collection == "vezo_user_private" and not user_id:
            raise ValueError("Sessão obrigatória para consulta privada")
        self.client = get_client(local_path)
        try:
            info = self.client.get_collection(self.collection)
            vectors = info.config.params.vectors
            if (
                isinstance(vectors, dict)
                or vectors.distance != Distance.COSINE
                or vectors.size != 384
            ):
                raise ValueError(
                    "Coleção deve usar vetor único de 384 dimensões e distância COSINE"
                )
            self.model = load_embedder()
        except Exception:
            self.client.close()
            raise

    def retrieve(self, question):
        from src.data_pipeline.retrieval import search

        hits = search(
            self.client,
            self.model,
            question,
            top_k=3,
            collection=self.collection,
            user_id=self.user_id,
        )
        return [
            EvidenceChunk(
                source_id=f"C{i}",
                source=PureWindowsPath(hit.source.replace("/", "\\")).name,
                text=hit.text,
                score=hit.score,
                chunk_index=hit.chunk_index,
                task_type=hit.task_type,
                title=hit.title,
                page_or_time=hit.page_or_time,
            )
            for i, hit in enumerate(hits, 1)
            if hit.text.strip()
        ]

    def close(self):
        self.client.close()


class ResearchAgent:
    def __init__(self, retriever: Retriever, llm: StructuredLLM, threshold=0.50):
        if not -1 <= threshold <= 1:
            raise ValueError("Limiar deve ser uma similaridade finita entre -1 e 1")
        self.retriever, self.llm, self.threshold = retriever, llm, threshold

    def execute(self, question):
        # Busca complementar apenas quando a pergunta contém duas orações interrogativas.
        # Não usa gabarito e não chama LLM antes do gate.
        parts = re.split(
            r"\s+e\s+(?=(?:o que|qual|quais|como|quando|quanto)\b)",
            question,
            maxsplit=1,
            flags=re.IGNORECASE,
        )
        queries = list(
            dict.fromkeys([question, *parts] if len(parts) == 2 else [question])
        )
        batches = [
            sorted(self.retriever.retrieve(query), key=lambda c: c.score, reverse=True)[
                :3
            ]
            for query in queries
        ]
        candidates = [batch[0] for batch in batches[1:] if batch] + [
            c for batch in batches for c in batch
        ]
        chosen = []
        seen = set()
        for chunk in candidates:
            key = (chunk.source, chunk.chunk_index, chunk.text)
            if key not in seen:
                chosen.append(chunk)
                seen.add(key)
            if len(chosen) == (5 if len(queries) > 1 else 3):
                break
        chunks = [
            chunk.model_copy(update={"source_id": f"C{i}"})
            for i, chunk in enumerate(
                sorted(chosen, key=lambda c: c.score, reverse=True), 1
            )
        ]
        score = max((c.score for c in chunks), default=None)
        if score is None or score < self.threshold:
            return RetrievalResult(
                abstained=True,
                top_score=score,
                queries=queries,
                chunks=chunks,
                gaps=["Evidência abaixo do limiar pré-LLM"],
                needs_review=False,
            )
        rounds = []
        for research_attempt in range(2):
            notes = self.llm.complete(
                "research",
                "Extraia fatos relevantes à pergunta explicitamente presentes nos trechos. "
                "Preserve fatos parciais mesmo quando outra parte da pergunta não foi encontrada. "
                "Cada fato precisa de source_id e quote literal contínua, sem paráfrase dentro de quote. "
                "Não misture perfis de estudantes nem atribua ao usuário o perfil de um documento. "
                "Registre as lacunas documentais em gaps. Planejamento é calculado por outro componente. "
                "Se uma informação documental essencial faltar, additional_queries deve conter pelo menos uma busca "
                "curta específica para encontrá-la (máximo duas); reformule com sinônimos e termos do domínio, sem inventar valores. "
                "facts vazio somente se nenhum trecho contiver qualquer fato útil à pergunta.",
                {
                    "question": question,
                    "chunks": [c.model_dump() for c in chunks],
                    "refinement_available": research_attempt == 0,
                },
                ResearchNotes,
            )
            rounds.append(
                {
                    "chunks": [c.model_dump() for c in chunks],
                    "notes": notes.model_dump(),
                }
            )
            additions = [
                q
                for q in notes.additional_queries
                if q.strip() and q not in queries and len(q) <= 500
            ]
            if research_attempt or not notes.gaps or not additions:
                break
            extra = [
                sorted(self.retriever.retrieve(q), key=lambda c: c.score, reverse=True)[
                    :3
                ]
                for q in additions
            ]
            queries.extend(additions)
            fact_ids = {f.source_id for f in notes.facts}
            candidates = [c for c in chunks if c.source_id in fact_ids] or chunks[:1]
            candidates += (
                [batch[0] for batch in extra if batch]
                + [c for batch in extra for c in batch]
                + chunks
            )
            chosen, seen = [], set()
            for chunk in candidates:
                key = (chunk.source, chunk.chunk_index, chunk.text)
                if key not in seen:
                    chosen.append(chunk)
                    seen.add(key)
                if len(chosen) == (5 if len(queries) > 1 else 3):
                    break
            chunks = [
                chunk.model_copy(update={"source_id": f"C{i}"})
                for i, chunk in enumerate(
                    sorted(chosen, key=lambda c: c.score, reverse=True), 1
                )
            ]
        score = max((c.score for c in chunks), default=None)
        by_id = {c.source_id: c for c in chunks}
        facts = [
            f
            for f in notes.facts
            if f.source_id in by_id
            and normalize(f.quote) in normalize(by_id[f.source_id].text)
        ]
        gaps = list(notes.gaps)
        if len(facts) != len(notes.facts):
            gaps.append("Extrações sem citação literal válida foram descartadas")
        return RetrievalResult(
            rounds=rounds,
            abstained=not facts,
            top_score=score,
            queries=queries,
            chunks=chunks,
            citations=list(dict.fromkeys(f.source_id for f in facts)),
            verified_facts=facts,
            gaps=gaps,
            needs_review=True,
        )
