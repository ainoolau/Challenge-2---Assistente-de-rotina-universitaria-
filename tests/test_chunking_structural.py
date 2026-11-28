"""Regression checks for structural/contextual chunking (no Qdrant or Groq)."""

from __future__ import annotations

from src.data_pipeline.ingestion import (
    INGESTION_VERSION,
    _fit_token_budget,
    dividir_segmentos,
    dividir_texto,
)


class FakeTokenizer:
    """Deterministic tokenizer used only for unit tests, not for evidence."""

    def encode(self, text: str, add_special_tokens: bool = True) -> list[int]:
        return [0] * (len(text.split()) + (2 if add_special_tokens else 0))


def test_profile_isolation():
    text = (
        "## Perfil Estudante 01 (aluno_01)\n"
        + "Atividade 01: estágio às 08:00\n" * 30
        + "---\n## Perfil Estudante 02 (aluno_02)\n"
        + "Atividade 02: estudar às 19:00\n" * 30
    )
    chunks = dividir_texto(text, tamanho=240, sobreposicao=36)
    assert len(chunks) > 2
    assert all(not ("aluno_01" in c and "aluno_02" in c) for c in chunks)
    assert any("aluno_01" in c for c in chunks)
    assert any("aluno_02" in c for c in chunks)


def test_table_row_keeps_date_and_activity():
    text = "Data | Atividade\n12/11/2026 | Prova de Matemática\n13/11/2026 | Entrega do projeto"
    chunks = dividir_texto(text, tamanho=90, sobreposicao=10)
    assert any("12/11/2026 | Prova de Matemática" in c for c in chunks)
    assert any("13/11/2026 | Entrega do projeto" in c for c in chunks)


def test_contextual_payload_preserves_citation_locator_and_hash():
    chunks = dividir_segmentos(
        [("p. 3", "## Frequência\nA presença mínima é de 75 por cento.")],
        task_type="texto",
        source="edital.pdf",
        tokenizer=FakeTokenizer(),
    )
    assert len(chunks) == 1
    assert chunks[0].text.startswith("[Documento: edital.pdf | Seção: Frequência]")
    assert "A presença mínima é de 75 por cento." in chunks[0].text
    assert chunks[0].page_or_time == "p. 3"
    assert len(chunks[0].content_hash) == 64


def test_token_budget_and_version():
    token = FakeTokenizer()
    header = "[Documento: edital.pdf | Localização: p. 2]"
    segments = _fit_token_budget("texto " * 400, header, token)
    assert len(segments) > 1
    assert all(len(token.encode(f"{header}\n{p}")) <= 128 for p in segments)
    assert INGESTION_VERSION == "3.0.2"


def test_form_field_isolation():
    from src.data_pipeline.ingestion import _form_profile_blocks

    original = (
        "## Perfil Estudante 01 (aluno_01)\n"
        "- Maior Gargalo na Gestão da Rotina: excesso de tarefas.\n"
        "- Jornadas Conciliadas: trabalho e estudos.\n"
        "---\n"
        "## Perfil Estudante 02 (aluno_02)\n"
        "- Maior Gargalo na Gestão da Rotina: prazos esquecidos.\n"
    )
    blocks = _form_profile_blocks(original)
    assert len(blocks) == 3
    assert all(not ("aluno_01" in b and "aluno_02" in b) for b in blocks)
    assert all("Perfil Estudante" in b for b in blocks)
    assert sum("Maior Gargalo na Gestão da Rotina:" in b for b in blocks) == 2
