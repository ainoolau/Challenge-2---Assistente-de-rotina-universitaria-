"""Testes da busca sem baixar o modelo: embedder falso determinístico e
Qdrant em memória, com pontos no mesmo formato gravado pela ingestão (TASK-03)."""

import hashlib
import math

import pytest

from data_pipeline.retrieval import SearchHit, expected_rank, search

qdrant_client = pytest.importorskip("qdrant_client")
from qdrant_client import models  # noqa: E402

DIM = 384
COLLECTION = "teste_demo"


class FakeEmbedder:
    """Bag-of-words com hashing: textos que compartilham palavras ficam próximos."""

    def encode(self, sentences, normalize_embeddings=True, **kwargs):
        vectors = []
        for s in sentences:
            v = [0.0] * DIM
            for word in s.lower().split():
                word = word.strip(".,?!:;")
                v[int(hashlib.md5(word.encode()).hexdigest(), 16) % DIM] += 1.0
            norm = math.sqrt(sum(x * x for x in v)) or 1.0
            vectors.append([x / norm for x in v])
        return vectors


TRECHOS = [
    ("Quarta-feira: Cálculo 2 das 8h às 10h, sala B1.", "data/samples/horario.pdf"),
    ("O estágio não pode ultrapassar 30 horas semanais.", "data/samples/edital.pdf"),
    ("A prova final de Física será em 12 de dezembro.", "data/samples/provas.txt"),
    ("Cardápio do restaurante universitário.", "data/samples/ru.png"),
]


@pytest.fixture
def base():
    client = qdrant_client.QdrantClient(":memory:")
    client.create_collection(
        COLLECTION,
        vectors_config=models.VectorParams(size=DIM, distance=models.Distance.COSINE),
    )
    model = FakeEmbedder()
    vectors = model.encode([t for t, _ in TRECHOS])
    client.upsert(
        COLLECTION,
        points=[
            models.PointStruct(
                id=i,
                vector=v,
                payload={"text": t, "source": s, "task_type": "texto", "chunk_index": 0},
            )
            for i, ((t, s), v) in enumerate(zip(TRECHOS, vectors, strict=True))
        ],
    )
    yield client, model
    client.close()


def test_search_returns_top_k_ordered_with_source_and_exact_text(base):
    client, model = base
    hits = search(
        client, model, "quantas horas semanais de estágio", top_k=3, collection=COLLECTION
    )

    assert len(hits) == 3
    assert hits[0].source == "data/samples/edital.pdf"
    assert hits[0].text == TRECHOS[1][0]
    assert hits[0].task_type == "texto"
    assert hits[0].score >= hits[1].score >= hits[2].score


def test_search_on_empty_collection_returns_nothing():
    client = qdrant_client.QdrantClient(":memory:")
    client.create_collection(
        "vazia", vectors_config=models.VectorParams(size=DIM, distance=models.Distance.COSINE)
    )
    assert search(client, FakeEmbedder(), "qualquer coisa", collection="vazia") == []


def _hit(source, text):
    return SearchHit(score=0.5, source=source, text=text, task_type="ocr", chunk_index=0)


def test_expected_rank_ignores_line_breaks_and_case():
    hits = [
        _hit("data/samples/Outro.pdf", "nada relevante"),
        _hit("data/samples/Geovanna_pdf.jpg", "exigem dedicação em período\nintegral, de segunda"),
    ]
    assert expected_rank(hits, "geovanna_pdf", "Período Integral") == 2


def test_expected_rank_requires_source_and_text_in_the_same_hit():
    hits = [
        _hit("data/samples/A.pdf", "aula de econometria"),
        _hit("data/samples/B.pdf", "outra coisa"),
    ]
    assert expected_rank(hits, "B.pdf", "econometria") is None
    assert expected_rank(hits, None, "econometria") == 1
    assert expected_rank([], "A.pdf") is None
