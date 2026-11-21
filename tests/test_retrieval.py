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
                payload={
                    "text": t,
                    "source": s,
                    "task_type": "texto",
                    "chunk_index": 0,
                },
            )
            for i, ((t, s), v) in enumerate(zip(TRECHOS, vectors, strict=True))
        ],
    )
    yield client, model
    client.close()


def test_search_returns_top_k_ordered_with_source_and_exact_text(base):
    client, model = base
    hits = search(
        client,
        model,
        "quantas horas semanais de estágio",
        top_k=3,
        collection=COLLECTION,
    )

    assert len(hits) == 3
    assert hits[0].source == "data/samples/edital.pdf"
    assert hits[0].text == TRECHOS[1][0]
    assert hits[0].task_type == "texto"
    assert hits[0].score >= hits[1].score >= hits[2].score


def test_search_on_empty_collection_returns_nothing():
    client = qdrant_client.QdrantClient(":memory:")
    client.create_collection(
        "vazia",
        vectors_config=models.VectorParams(size=DIM, distance=models.Distance.COSINE),
    )
    assert search(client, FakeEmbedder(), "qualquer coisa", collection="vazia") == []


def _hit(source, text):
    return SearchHit(
        score=0.5, source=source, text=text, task_type="ocr", chunk_index=0
    )


def test_expected_rank_ignores_line_breaks_and_case():
    hits = [
        _hit("data/samples/Outro.pdf", "nada relevante"),
        _hit(
            "data/samples/Geovanna_pdf.jpg",
            "exigem dedicação em período\nintegral, de segunda",
        ),
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


def test_batch_ingestion_is_idempotent_and_populates_citation_metadata(tmp_path):
    from data_pipeline.ingestion import INGESTION_VERSION, ingest_files

    pdf_file = tmp_path / "edital_residencia_02.pdf"
    img_file = tmp_path / "grade_aluno_05.jpeg"
    aud_file = tmp_path / "audio_rotina_01.ogg"
    for f in (pdf_file, img_file, aud_file):
        f.write_bytes(b"fixture")

    fake_segments = {
        pdf_file.name: [
            ("p. 1", "Regulamento da residência: frequência mínima presencial de 90%."),
            ("p. 2", "O residente que acumular 3 advertências será desligado."),
        ],
        img_file.name: [
            ("imagem", "Econometria terça e quinta das 08h às 09h50 na UnB.")
        ],
        aud_file.name: [
            ("00:00-00:12", "Acordo às seis horas para ir à residência em IA."),
            ("00:12-00:25", "À noite assisto às aulas presenciais da graduação."),
        ],
    }

    client = qdrant_client.QdrantClient(":memory:")
    model = FakeEmbedder()
    try:
        first = ingest_files(
            [pdf_file, img_file, aud_file],
            collection_name="audit_idempotency",
            client=client,
            embedder=model,
            segment_extractor=lambda path: fake_segments[path.name],
        )
        assert first.processed_files == 3
        assert first.skipped_unchanged == 0
        assert first.failed_files == 0
        assert first.points_in_collection == 4  # 2 PDF + 1 OCR + 1 áudio agrupado

        # Segunda execução sobre os mesmos arquivos: zero duplicatas e skip total.
        second = ingest_files(
            [pdf_file, img_file, aud_file],
            collection_name="audit_idempotency",
            client=client,
            embedder=model,
            segment_extractor=lambda path: fake_segments[path.name],
        )
        assert second.processed_files == 0
        assert second.skipped_unchanged == 3
        assert second.total_chunks_upserted == 0
        assert second.points_in_collection == first.points_in_collection

        hits = search(
            client,
            model,
            "frequência mínima presencial 90%",
            top_k=4,
            collection="audit_idempotency",
        )
        pdf_hit = next(h for h in hits if h.source_id == "edital_residencia_02")
        assert pdf_hit.title == "Edital Residencia 02"
        assert pdf_hit.page_or_time in {"p. 1", "p. 2"}
        assert pdf_hit.task_type == "texto"
        assert pdf_hit.corpus_scope == "institutional"
        assert pdf_hit.ingestion_version == INGESTION_VERSION

        points, _ = client.scroll("audit_idempotency", limit=20, with_payload=True)
        by_type = {p.payload["task_type"]: p.payload for p in points}
        assert set(by_type) == {"texto", "ocr", "audio"}
        assert by_type["ocr"]["page_or_time"] == "imagem"
        assert by_type["audio"]["page_or_time"] == "00:00-00:25"
        for p in points:
            for required_key in (
                "text",
                "source",
                "task_type",
                "user_id",
                "created_at",
                "chunk_index",
                "source_id",
                "title",
                "page_or_time",
                "content_hash",
                "file_hash",
                "corpus_scope",
                "ingestion_version",
            ):
                assert required_key in p.payload
    finally:
        client.close()


def test_batch_ingestion_deduplicates_and_removes_orphan_chunks(tmp_path):
    from data_pipeline.ingestion import ingest_files

    doc = tmp_path / "manual_academico.txt"
    dup = tmp_path / "manual_academico_copia.txt"
    conteudo_longo = ("Regra de avaliação universitária detalhada. " * 25).strip()
    doc.write_text(conteudo_longo, encoding="utf-8")
    dup.write_text(conteudo_longo, encoding="utf-8")

    client = qdrant_client.QdrantClient(":memory:")
    model = FakeEmbedder()
    try:
        # Mesmo arquivo repetido + arquivo com conteúdo idêntico são deduplicados.
        first = ingest_files(
            [doc, doc, dup],
            collection_name="audit_orphans",
            client=client,
            embedder=model,
        )
        assert first.processed_files == 1
        assert first.deduplicated_files == 2
        assert first.points_in_collection >= 2

        # Atualiza o arquivo com texto curto (1 único chunk): órfãos devem sumir.
        doc.write_text(
            "Regra atualizada: prazo único de entrega na sexta-feira.",
            encoding="utf-8",
        )
        second = ingest_files(
            [doc],
            collection_name="audit_orphans",
            client=client,
            embedder=model,
        )
        assert second.processed_files == 1
        assert second.orphan_chunks_deleted >= 1
        assert second.points_in_collection == 1
    finally:
        client.close()


def test_ingestion_masks_pii_and_blocks_private_corpus(tmp_path):
    from data_pipeline.ingestion import ingest_files
    from data_pipeline.sanitizer import CORPUS_SCOPE_PRIVATE, mask_pii

    leaky = tmp_path / "comunicado_vazamento.txt"
    leaky.write_text(
        "Nome: João Carlos da Silva\n"
        "Matrícula: 211039482\n"
        "Contato: Maria Oliveira (RA: 202312345), CPF 123.456.789-01, "
        "e-mail aluno.teste@unb.br, WhatsApp (61) 99876-5432.\n"
        "Regra preservada: frequência mínima de 90%, aula das 08h às 09h50, "
        "vigência 17/08/2026 e bolsa de R$ 1.500,00.",
        encoding="utf-8",
    )

    client = qdrant_client.QdrantClient(":memory:")
    model = FakeEmbedder()
    try:
        summary = ingest_files(
            [leaky],
            collection_name="audit_pii",
            client=client,
            embedder=model,
        )
        assert summary.processed_files == 1
        assert summary.pii_redactions
        points, _ = client.scroll("audit_pii", limit=10, with_payload=True)
        stored_text = " ".join(p.payload["text"] for p in points)
        for leaked in (
            "João Carlos da Silva",
            "Maria Oliveira",
            "211039482",
            "202312345",
            "123.456.789-01",
            "aluno.teste@unb.br",
            "99876-5432",
        ):
            assert leaked not in stored_text
        for preserved in ("90%", "08h às 09h50", "17/08/2026", "R$ 1.500,00"):
            assert preserved in stored_text

        # Bloqueio de escopo privado no índice institucional compartilhado.
        with pytest.raises(PermissionError):
            ingest_files(
                [leaky],
                collection_name="audit_pii",
                corpus_scope=CORPUS_SCOPE_PRIVATE,
                client=client,
                embedder=model,
            )

        # Bloqueio de caminho em diretório privado no índice institucional.
        private_dir = tmp_path / "private"
        private_dir.mkdir()
        private_file = private_dir / "anotacoes.txt"
        private_file.write_text(
            "Diário pessoal confidencial do estudante.", encoding="utf-8"
        )
        with pytest.raises(PermissionError):
            ingest_files(
                [private_file],
                collection_name="audit_pii",
                client=client,
                embedder=model,
            )
    finally:
        client.close()

    # Audita amostra real textual do repositório contra vazamento de PII.
    from pathlib import Path

    sample_profiles = Path("data/samples/perfis_rotina_forms.txt").read_text(
        encoding="utf-8-sig"
    )
    assert not mask_pii(sample_profiles).had_pii


def test_ingestion_flags_empty_and_low_quality_files(tmp_path):
    from data_pipeline.ingestion import ingest_files

    empty_doc = tmp_path / "vazio.txt"
    short_doc = tmp_path / "ocr_ruido.txt"
    empty_doc.write_text("   \n  ", encoding="utf-8")
    short_doc.write_text("texto curto", encoding="utf-8")

    client = qdrant_client.QdrantClient(":memory:")
    model = FakeEmbedder()
    try:
        summary = ingest_files(
            [empty_doc, short_doc],
            collection_name="audit_quality",
            client=client,
            embedder=model,
        )
        assert summary.failed_files == 1
        assert summary.processed_files == 1
        assert len(summary.quality_warnings) == 2
        points, _ = client.scroll("audit_quality", limit=10, with_payload=True)
        assert len(points) == 1
        assert points[0].payload["quality_warning"] is not None
    finally:
        client.close()
