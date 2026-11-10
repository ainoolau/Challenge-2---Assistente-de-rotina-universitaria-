"""Consulta à base vetorial populada pela ingestão (TASK-03).

Lê a mesma collection, o mesmo modelo de embeddings e o mesmo formato de
payload gravados por src/data_pipeline/ingestion.py:
    payload = {"text", "source", "task_type", "user_id", "created_at", "chunk_index"}

Configuração por variáveis de ambiente:
    QDRANT_URL         URL do servidor Qdrant (ex.: http://localhost:6333, TASK-02).
                       Se ausente, usa o modo local em QDRANT_PATH, como a ingestão.
    QDRANT_API_KEY     Chave do servidor, se houver.
    QDRANT_PATH        Pasta do modo local (padrão: data/qdrant).
    QDRANT_COLLECTION  Nome da collection (padrão: rotina_estudante_multimodal).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from qdrant_client import QdrantClient

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Precisam ser iguais aos da ingestão (TASK-03).
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
DEFAULT_COLLECTION = os.getenv("QDRANT_COLLECTION", "rotina_estudante_multimodal")
DEFAULT_LOCAL_PATH = Path(os.getenv("QDRANT_PATH", PROJECT_ROOT / "data" / "qdrant"))


class Embedder(Protocol):
    def encode(self, sentences, **kwargs): ...


@dataclass(frozen=True)
class SearchHit:
    score: float
    source: str
    text: str
    task_type: str | None
    chunk_index: int | None


def _normalize(text: str) -> str:
    # OCR e PDF quebram linhas no meio de frases: compara ignorando espaços e caixa.
    return " ".join(text.split()).casefold()


def expected_rank(
    hits: list[SearchHit],
    expected_source: str | None = None,
    expected_text: str | None = None,
) -> int | None:
    """Posição (1-based) do primeiro trecho cuja fonte contém expected_source e
    cujo texto contém expected_text, ou None se nenhum dos hits atende."""
    for rank, hit in enumerate(hits, start=1):
        source_ok = expected_source is None or _normalize(
            expected_source
        ) in _normalize(hit.source)
        text_ok = expected_text is None or _normalize(expected_text) in _normalize(
            hit.text
        )
        if source_ok and text_ok:
            return rank
    return None


def get_client(local_path: Path | str | None = None) -> QdrantClient:
    """Servidor se QDRANT_URL estiver definido; senão, o Qdrant local em disco.

    Atenção: no modo local só um processo abre a pasta por vez. Rode a demo
    depois que a ingestão terminar.
    """
    from qdrant_client import QdrantClient

    url = os.getenv("QDRANT_URL")
    if url:
        return QdrantClient(url=url, api_key=os.getenv("QDRANT_API_KEY"))
    path = Path(local_path or DEFAULT_LOCAL_PATH)
    if not path.is_dir():
        raise FileNotFoundError(
            f"Base vetorial local não encontrada em {path}. "
            "Rode a ingestão (python -m src.data_pipeline.ingestion) ou defina QDRANT_URL."
        )
    return QdrantClient(path=str(path))


def load_embedder(model_name: str = EMBEDDING_MODEL) -> Embedder:
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name, device="cpu")


def search(
    client: QdrantClient,
    model: Embedder,
    query: str,
    top_k: int = 3,
    collection: str = DEFAULT_COLLECTION,
) -> list[SearchHit]:
    """Busca os top_k trechos mais próximos da pergunta.

    A collection usa distância cosseno, então o score fica em [-1, 1]
    (maior = mais próximo), com ou sem normalização do vetor.
    """
    vector = model.encode([query], normalize_embeddings=True, show_progress_bar=False)[
        0
    ]
    response = client.query_points(
        collection_name=collection,
        query=[float(x) for x in vector],
        limit=top_k,
        with_payload=True,
    )
    hits = []
    for point in response.points:
        payload = point.payload or {}
        hits.append(
            SearchHit(
                score=float(point.score),
                source=str(payload.get("source", "?")),
                text=str(payload.get("text", "")),
                task_type=payload.get("task_type"),
                chunk_index=payload.get("chunk_index"),
            )
        )
    return hits
