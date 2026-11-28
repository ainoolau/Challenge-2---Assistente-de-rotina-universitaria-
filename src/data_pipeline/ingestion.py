# TASK-03 / TASK-F2-02 / TASK-F2-03 — PIPELINE DE INGESTÃO MULTIMODAL IDEMPOTENTE
#
# 1. Lê arquivos de diferentes formatos (PDF, imagem/OCR, áudio/STT, DOCX, TXT)
# 2. Aplica segregação de corpus e mascaramento determinístico de PII (LGPD)
# 3. Divide os textos em chunks preservando localizador (página ou faixa de tempo)
# 4. Gera hashes SHA-256 e IDs determinísticos (uuid5) para carga batch idempotente
# 5. Envia vetores 384d COSINE (paraphrase-multilingual-MiniLM-L12-v2) ao Qdrant

from __future__ import annotations

import argparse
import hashlib
import os
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol
from uuid import NAMESPACE_URL, uuid5

from .sanitizer import (
    CORPUS_SCOPE_INSTITUTIONAL,
    CORPUS_SCOPE_PRIVATE,
    mask_pii,
    validate_corpus_segregation,
)

if TYPE_CHECKING:
    from qdrant_client import QdrantClient

# CONFIGURAÇÕES DO PROJETO

PASTA_DOCUMENTOS = "data/samples"
QDRANT_HOST = "localhost"
QDRANT_PORT = 6333

# Nome da coleção utilizada pelo pipeline
NOME_COLECAO = "rotina_estudante_multimodal"

# MODELO MULTILÍNGUE (Suporte nativo a Português, 384 dimensões)
MODELO_NOME = "paraphrase-multilingual-MiniLM-L12-v2"
VECTOR_SIZE = 384
INGESTION_VERSION = "3.0.2"
# O SentenceTransformer instalado usa max_seq_length=128.
# Nunca envie mais tokens do que ele realmente processa.
MAX_EMBEDDING_TOKENS = 128
DEFAULT_STRUCTURAL_CHARS = 900
MAX_HEADER_FIELD_CHARS = 80
MAX_HEADING_LINE_CHARS = 120
MIN_QUALITY_CHARS = 25

USUARIO = "usuario_teste"

FORMATOS_ACEITOS = [
    ".png",
    ".jpg",
    ".jpeg",
    ".ogg",
    ".mp3",
    ".wav",
    ".pdf",
    ".docx",
    ".txt",
]


class Embedder(Protocol):
    def encode(self, sentences: list[str], /, **kwargs: Any) -> Any: ...


@dataclass(frozen=True)
class ChunkRecord:
    """Unidade de chunk pronta para vetorização e rastreabilidade."""

    text: str
    page_or_time: str
    chunk_index: int
    content_hash: str


@dataclass
class IngestionSummary:
    """Resumo estruturado da execução batch de ingestão."""

    collection: str
    ingestion_version: str = INGESTION_VERSION
    processed_files: int = 0
    skipped_unchanged: int = 0
    deduplicated_files: int = 0
    failed_files: int = 0
    total_chunks_upserted: int = 0
    orphan_chunks_deleted: int = 0
    points_in_collection: int = 0
    pii_redactions: dict[str, int] = field(default_factory=dict)
    quality_warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# 1 - HELPERS DETERMINÍSTICOS (HASHES, IDS E METADADOS)


def compute_sha256(text: str) -> str:
    """Calcula SHA-256 determinístico de texto normalizado."""
    normalized = " ".join(text.split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def build_source_id(arquivo: Path) -> str:
    """Identificador estável e legível de origem para citações."""
    return arquivo.stem.lower()


def build_title(arquivo: Path) -> str:
    """Título legível derivado do nome do arquivo padronizado."""
    cleaned = arquivo.stem.replace("_", " ").replace("-", " ").strip()
    return " ".join(part.capitalize() for part in cleaned.split()) or arquivo.name


def build_chunk_id(user_id: str, source: str, chunk_index: int) -> str:
    """ID determinístico via uuid5 (compatível com o contrato original)."""
    return str(uuid5(NAMESPACE_URL, f"{user_id}:{source}:{chunk_index}"))


def normalize_source_key(arquivo: Path) -> str:
    """Normaliza o caminho de origem para formato POSIX estável."""
    try:
        rel = arquivo.resolve().relative_to(Path.cwd().resolve())
        return rel.as_posix()
    except ValueError:
        return arquivo.as_posix()


# 2 - DIVIDIR O TEXTO EM BLOCOS


# The same boundaries are used for the payload and the embedding input. Thus,
# a ResearchAgent quote remains a literal substring of payload["text"].
_PROFILE_START = re.compile(r"(?m)^\s*##\s*Perfil\s+Estudante\b[^\n]*", re.IGNORECASE)
_SECTION_START = re.compile(
    r"(?i)^(?:#{1,6}\s+.+|(?:cap[ií]tulo|se[çc][ãa]o|art\.?|cl[áa]usula)\s+"
    r"[\dIVXLCDM]+\b.*|\d+(?:\.\d+)*[.)]\s+.+)$"
)


def _profile_sections(text: str) -> list[tuple[str, str]]:
    """Isolate profiles before any packing or overlap is applied."""
    matches = list(_PROFILE_START.finditer(text))
    if not matches:
        return [("", text)]
    parts: list[tuple[str, str]] = []
    if text[: matches[0].start()].strip():
        parts.append(("", text[: matches[0].start()].strip()))
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        section = text[match.start() : end].strip()
        # A dashed divider belongs to neither profile; keep it out of embeddings.
        section = re.sub(r"(?m)^\s*---+\s*$", "", section).strip()
        parts.append((match.group().strip(), section))
    return parts


def _structural_units(text: str) -> list[str]:
    """Prefer whole paragraphs and table/calendar rows over character slicing."""
    units: list[str] = []
    paragraph: list[str] = []

    def flush() -> None:
        if paragraph:
            units.append("\n".join(paragraph).strip())
            paragraph.clear()

    for original in text.splitlines():
        line = original.strip()
        if not line:
            flush()
            continue
        # Markdown tables, tabular fields, schedule lines and list entries
        # are kept together with the date/time or value on their own line.
        row = (
            line.startswith("|")
            or "\t" in line
            or bool(re.match(r"^(?:[-*+]\s+|\d+[.)]\s+)", line))
            or bool(re.search(r"\b\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?\b", line))
        )
        if _SECTION_START.match(line) or row:
            flush()
            units.append(line)
        else:
            paragraph.append(line)
    flush()
    return [unit for unit in units if unit]


def _split_oversized(text: str, limit: int, overlap: int) -> list[str]:
    """Last-resort windowing with word/line boundaries when possible."""
    pieces: list[str] = []
    remaining = text.strip()
    while len(remaining) > limit:
        end = limit
        boundary = max(remaining.rfind("\n", 0, end), remaining.rfind(" ", 0, end))
        if boundary >= limit // 2:
            end = boundary
        part = remaining[:end].strip()
        if not part:
            end = limit
            part = remaining[:end].strip()
        pieces.append(part)
        advance = max(1, end - overlap)
        remaining = remaining[advance:].strip()
    if remaining:
        pieces.append(remaining)
    return pieces


def dividir_texto(
    texto: str, tamanho: int = DEFAULT_STRUCTURAL_CHARS, sobreposicao: int = 160
) -> list[str]:
    """Chunk by profiles, clauses, paragraphs and full schedule/table rows.

    Overlap is restricted to oversized units; it cannot cross a student boundary.
    """
    if tamanho <= 0:
        raise ValueError("O tamanho deve ser positivo.")
    if sobreposicao < 0 or sobreposicao >= tamanho:
        raise ValueError("Sobreposição inválida.")
    if not texto.strip():
        return []

    results: list[str] = []
    for profile, section in _profile_sections(texto):
        section_results: list[str] = []
        buffer: list[str] = []
        for unit in _structural_units(section):
            if len(unit) > tamanho:
                if buffer:
                    section_results.append("\n\n".join(buffer))
                    buffer = []
                section_results.extend(_split_oversized(unit, tamanho, sobreposicao))
                continue
            candidate = "\n\n".join([*buffer, unit])
            if buffer and len(candidate) > tamanho:
                section_results.append("\n\n".join(buffer))
                buffer = [unit]
            else:
                buffer.append(unit)
        if buffer:
            section_results.append("\n\n".join(buffer))
        # Repeat the profile identifier in each split unit, even if the
        # profile spans many chunks; never include text from another profile.
        for chunk in section_results:
            if profile and not chunk.lstrip().startswith(profile):
                prefix = f"{profile}\n"
                if len(prefix) < tamanho:
                    chunk = prefix + chunk
            results.append(chunk)
    return results


def _compact_header_value(value: str, max_chars: int = MAX_HEADER_FIELD_CHARS) -> str:
    """Compacta metadado de cabeçalho para nunca exceder o orçamento do MiniLM."""
    cleaned = " ".join(value.split()).strip()
    if len(cleaned) <= max_chars:
        return cleaned
    cut = cleaned[: max_chars - 1]
    boundary = cut.rfind(" ")
    if boundary >= max_chars // 2:
        cut = cut[:boundary]
    return f"{cut.rstrip(' ,;:-')}…"


def _context_header(source: str, page_or_time: str, text: str) -> str:
    """Compact, sanitized document locator; text is never replaced."""
    safe_source = _compact_header_value(source, max_chars=64)
    profile = _PROFILE_START.search(text)
    if profile:
        profile_label = _compact_header_value(profile.group().lstrip("# ").strip())
        context = f"Perfil: {profile_label}"
    else:
        heading = next(
            (
                line.strip("# ").strip()
                for line in text.splitlines()
                if _SECTION_START.match(line.strip())
                and len(line.strip()) <= MAX_HEADING_LINE_CHARS
            ),
            "",
        )
        if heading:
            context = f"Seção: {_compact_header_value(heading)}"
        else:
            locator = _compact_header_value(page_or_time, max_chars=48)
            context = f"Localização: {locator}"
    return f"[Documento: {safe_source} | {context}]"


def _token_count(text: str, tokenizer: Any) -> int:
    return len(tokenizer.encode(text, add_special_tokens=True))


def _fit_token_budget(
    text: str, header: str, tokenizer: Any, max_tokens: int = MAX_EMBEDDING_TOKENS
) -> list[str]:
    """Split on word boundaries until the *real tokenizer* fits the full input."""
    if _token_count(f"{header}\n{text}", tokenizer) <= max_tokens:
        return [text]
    units = re.findall(r"\S+\s*", text)
    output: list[str] = []
    current = ""
    for unit in units:
        candidate = current + unit
        if _token_count(f"{header}\n{candidate}", tokenizer) <= max_tokens:
            current = candidate
            continue
        if current.strip():
            output.append(current.strip())
            current = ""
        if _token_count(f"{header}\n{unit}", tokenizer) <= max_tokens:
            current = unit
            continue
        # Exceptionally long, unbreakable word (e.g., OCR noise): use
        # a conservative character-level fallback, checked by tokenizer.
        remainder = unit
        while remainder:
            lo, hi = 1, len(remainder)
            while lo < hi:
                mid = (lo + hi + 1) // 2
                if (
                    _token_count(f"{header}\n{remainder[:mid]}", tokenizer)
                    <= max_tokens
                ):
                    lo = mid
                else:
                    hi = mid - 1
            if _token_count(f"{header}\n{remainder[:lo]}", tokenizer) > max_tokens:
                raise ValueError("Cabeçalho contextual excede o limite do MiniLM.")
            output.append(remainder[:lo].strip())
            remainder = remainder[lo:]
    if current.strip():
        output.append(current.strip())
    return [part for part in output if part]


def _agrupar_segmentos_audio(
    segmentos: list[tuple[str, str]], tamanho: int
) -> list[tuple[str, str]]:
    """Agrupa falas curtas de áudio até `tamanho` preservando faixa MM:SS-MM:SS."""
    agrupados: list[tuple[str, str]] = []
    buffer_textos: list[str] = []
    inicio_atual: str | None = None
    fim_atual: str | None = None

    for faixa, texto in segmentos:
        texto_limpo = texto.strip()
        if not texto_limpo:
            continue
        partes = faixa.split("-", 1)
        seg_inicio = partes[0]
        seg_fim = partes[1] if len(partes) == 2 else partes[0]

        candidato = " ".join([*buffer_textos, texto_limpo])
        if buffer_textos and len(candidato) > tamanho:
            faixa_final = (
                f"{inicio_atual}-{fim_atual}"
                if inicio_atual != fim_atual
                else str(inicio_atual)
            )
            agrupados.append((faixa_final, " ".join(buffer_textos)))
            buffer_textos = [texto_limpo]
            inicio_atual = seg_inicio
            fim_atual = seg_fim
        else:
            if inicio_atual is None:
                inicio_atual = seg_inicio
            fim_atual = seg_fim
            buffer_textos.append(texto_limpo)

    if buffer_textos:
        faixa_final = (
            f"{inicio_atual}-{fim_atual}"
            if inicio_atual != fim_atual
            else str(inicio_atual)
        )
        agrupados.append((faixa_final, " ".join(buffer_textos)))

    return agrupados


def _form_profile_blocks(text: str) -> list[str]:
    """Divide formulários por estudante/campo sem regras para consultas específicas.

    A ficha de um aluno pode exceder os 128 tokens reais do MiniLM.
    Uma linha '- Campo: valor' vira unidade recuperável, sempre com o
    identificador do aluno. Os demais documentos seguem o fluxo normal.
    """
    blocks: list[str] = []
    for profile, section in _profile_sections(text):
        if not profile:
            # Preserve a introdução do documento sem misturá-la a um aluno.
            blocks.extend(dividir_texto(section))
            continue
        lines = [line.strip() for line in section.splitlines() if line.strip()]
        fields = [line for line in lines if line.startswith(("- ", "* "))]
        others = [
            line
            for line in lines
            if not line.startswith(("- ", "* ")) and line != profile
        ]
        if fields:
            blocks.extend(f"{profile}\n{field}" for field in fields)
            blocks.extend(f"{profile}\n{line}" for line in others)
        else:
            blocks.extend(dividir_texto(section))
    return blocks


def dividir_segmentos(
    segmentos: list[tuple[str, str]],
    *,
    task_type: str,
    tamanho: int = DEFAULT_STRUCTURAL_CHARS,
    sobreposicao: int = 160,
    source: str = "documento",
    tokenizer: Any | None = None,
) -> list[ChunkRecord]:
    """Retain page/time provenance and build contextual payload for citation."""
    if task_type == "audio":
        segmentos = _agrupar_segmentos_audio(segmentos, tamanho)

    registros: list[ChunkRecord] = []
    for localizador, texto in segmentos:
        # Campos de formulário são unidades semânticas: nunca misturar
        # estudantes e nunca separar nome do campo do seu valor.
        if _PROFILE_START.search(texto):
            blocos = _form_profile_blocks(texto)
        else:
            blocos = dividir_texto(texto, tamanho=tamanho, sobreposicao=sobreposicao)
        for bloco in blocos:
            header = _context_header(source, localizador, bloco)
            parts = (
                _fit_token_budget(bloco, header, tokenizer)
                if tokenizer is not None
                else [bloco]
            )
            for part in parts:
                contextual = f"{header}\n{part}"
                registros.append(
                    ChunkRecord(
                        text=contextual,
                        page_or_time=localizador,
                        chunk_index=len(registros),
                        content_hash=compute_sha256(contextual),
                    )
                )
    return registros


# 3 - IDENTIFICAR O FORMATO E EXTRAIR O TEXTO


def extrair_segmentos(arquivo: Path) -> list[tuple[str, str]]:
    """Extrai segmentos `(page_or_time, texto)` conforme o formato do arquivo."""
    extensao = arquivo.suffix.lower()

    if extensao == ".txt":
        texto = arquivo.read_text(encoding="utf-8-sig").strip()
        return [("documento", texto)] if texto else []

    from .extractors import (
        extrair_paginas_pdf,
        extrair_texto_imagem,
        extrair_texto_word,
        transcrever_audio_com_tempos,
    )

    if extensao in [".png", ".jpg", ".jpeg"]:
        texto = extrair_texto_imagem(str(arquivo))
        return [("imagem", texto)] if texto else []
    if extensao in [".ogg", ".mp3", ".wav"]:
        return transcrever_audio_com_tempos(str(arquivo))
    if extensao == ".pdf":
        return extrair_paginas_pdf(str(arquivo))
    if extensao == ".docx":
        texto = extrair_texto_word(str(arquivo))
        return [("documento", texto)] if texto else []
    raise ValueError("Formato não suportado.")


def extrair_conteudo(arquivo: Path) -> str:
    """Escolhe o extrator conforme o formato do arquivo."""
    segmentos = extrair_segmentos(arquivo)
    return "\n\n".join(texto for _, texto in segmentos)


# 4 - GERAR OS EMBEDDINGS


def gerar_embeddings(
    blocos: list[str], modelo: Embedder | None = None
) -> list[list[float]]:
    """Transforma os blocos em vetores de 384 dimensões."""
    if not blocos:
        return []

    if modelo is None:
        from sentence_transformers import SentenceTransformer

        embedder_ativo: Any = SentenceTransformer(MODELO_NOME)
    else:
        embedder_ativo = modelo

    vetores = embedder_ativo.encode(blocos)
    if hasattr(vetores, "tolist"):
        return vetores.tolist()
    return [list(v) for v in vetores]


# 5 - IDENTIFICAR O TIPO DO DOCUMENTO


def identificar_tipo(arquivo: Path) -> str:
    """Identifica se o arquivo é imagem, áudio ou texto."""
    extensao = arquivo.suffix.lower()

    if extensao in [".png", ".jpg", ".jpeg"]:
        return "ocr"
    elif extensao in [".ogg", ".mp3", ".wav"]:
        return "audio"
    else:
        return "texto"


# 6 - PIPELINE BATCH IDEMPOTENTE


def _criar_cliente_qdrant(qdrant_url: str | None = None) -> QdrantClient:
    from qdrant_client import QdrantClient

    url = qdrant_url or os.getenv("QDRANT_URL")
    if url:
        return QdrantClient(url=url, api_key=os.getenv("QDRANT_API_KEY"))
    return QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)


def _buscar_pontos_existentes(
    cliente: QdrantClient,
    collection_name: str,
    source_key: str,
    user_id: str | None = None,
) -> list[Any]:
    from qdrant_client import models

    pontos: list[Any] = []
    offset: Any = None
    conditions: list[Any] = [
        models.FieldCondition(key="source", match=models.MatchValue(value=source_key))
    ]
    if user_id is not None:
        conditions.append(
            models.FieldCondition(key="user_id", match=models.MatchValue(value=user_id))
        )
    filtro = models.Filter(must=conditions)
    while True:
        batch, next_offset = cliente.scroll(
            collection_name=collection_name,
            scroll_filter=filtro,
            limit=256,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        pontos.extend(batch)
        if next_offset is None:
            break
        offset = next_offset
    return pontos


def _coletar_arquivos(
    arquivos: Sequence[Path] | None = None,
    pasta_documentos: Path | str = PASTA_DOCUMENTOS,
) -> list[Path]:
    if arquivos is not None:
        return [Path(a) for a in arquivos]

    pasta = Path(pasta_documentos)
    if not pasta.is_dir():
        return []

    encontrados = [
        arquivo
        for arquivo in pasta.iterdir()
        if arquivo.is_file() and arquivo.suffix.lower() in FORMATOS_ACEITOS
    ]
    encontrados.sort()
    return encontrados


def ingest_files(
    arquivos: Sequence[Path] | None = None,
    *,
    pasta_documentos: Path | str = PASTA_DOCUMENTOS,
    collection_name: str = NOME_COLECAO,
    user_id: str = USUARIO,
    corpus_scope: str = CORPUS_SCOPE_INSTITUTIONAL,
    target_collection_scope: str = CORPUS_SCOPE_INSTITUTIONAL,
    recreate: bool = False,
    chunk_size: int = DEFAULT_STRUCTURAL_CHARS,
    chunk_overlap: int = 160,
    qdrant_url: str | None = None,
    client: QdrantClient | None = None,
    embedder: Embedder | None = None,
    segment_extractor: Callable[[Path], list[tuple[str, str]]] | None = None,
) -> IngestionSummary:
    """Executa ingestão batch idempotente com metadados de citação e sanitização PII."""
    from qdrant_client import models

    validate_corpus_segregation(
        corpus_scope=corpus_scope,
        target_collection_scope=target_collection_scope,
    )

    summary = IngestionSummary(collection=collection_name)
    lista_bruta = _coletar_arquivos(arquivos, pasta_documentos=pasta_documentos)

    if not lista_bruta:
        return summary

    # Deduplicação por caminho canônico no mesmo lote.
    lista_arquivos: list[Path] = []
    caminhos_vistos: set[str] = set()
    for arq in lista_bruta:
        chave_caminho = normalize_source_key(arq)
        if chave_caminho in caminhos_vistos:
            summary.deduplicated_files += 1
            continue
        caminhos_vistos.add(chave_caminho)
        lista_arquivos.append(arq)

    # Validação de segregação por caminho antes de tocar na coleção.
    for arq in lista_arquivos:
        validate_corpus_segregation(
            corpus_scope=corpus_scope,
            target_collection_scope=target_collection_scope,
            source_path=arq,
        )

    owns_client = client is None
    cliente = client if client is not None else _criar_cliente_qdrant(qdrant_url)
    extrator = segment_extractor or extrair_segmentos
    modelo: Any = embedder
    hashes_lote: set[str] = set()

    try:
        if recreate and cliente.collection_exists(collection_name):
            cliente.delete_collection(collection_name)

        if not cliente.collection_exists(collection_name):
            cliente.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=VECTOR_SIZE, distance=models.Distance.COSINE
                ),
            )

        for arquivo in lista_arquivos:
            if not arquivo.is_file():
                summary.failed_files += 1
                summary.errors.append(f"Arquivo não encontrado: {arquivo.as_posix()}")
                continue
            if arquivo.suffix.lower() not in FORMATOS_ACEITOS:
                summary.failed_files += 1
                summary.errors.append(f"Formato não suportado: {arquivo.as_posix()}")
                continue

            try:
                segmentos_brutos = extrator(arquivo)
                segmentos_sanitizados: list[tuple[str, str]] = []
                for localizador, texto_seg in segmentos_brutos:
                    resultado_pii = mask_pii(texto_seg)
                    for tipo_pii, qtd in resultado_pii.redactions.items():
                        summary.pii_redactions[tipo_pii] = (
                            summary.pii_redactions.get(tipo_pii, 0) + qtd
                        )
                    if resultado_pii.text.strip():
                        segmentos_sanitizados.append((localizador, resultado_pii.text))

                texto_total = "\n\n".join(t for _, t in segmentos_sanitizados).strip()
                if not texto_total:
                    summary.failed_files += 1
                    aviso = f"Extração vazia ou ilegível: {arquivo.name}"
                    summary.quality_warnings.append(aviso)
                    summary.errors.append(aviso)
                    continue

                quality_warning: str | None = None
                if len(texto_total) < MIN_QUALITY_CHARS:
                    quality_warning = (
                        f"Baixa densidade textual ({len(texto_total)} caracteres): "
                        f"revisar qualidade de OCR/STT de {arquivo.name}"
                    )
                    summary.quality_warnings.append(quality_warning)

                file_hash = compute_sha256(texto_total)
                if file_hash in hashes_lote:
                    summary.deduplicated_files += 1
                    continue
                hashes_lote.add(file_hash)

                if modelo is None:
                    from sentence_transformers import SentenceTransformer

                    modelo = SentenceTransformer(MODELO_NOME)
                tokenizer = getattr(modelo, "tokenizer", None)
                if tokenizer is None:
                    # A test embedder can expose only encode(); production
                    # SentenceTransformer must supply the actual tokenizer.
                    if embedder is None:
                        raise RuntimeError("Tokenizador MiniLM indisponível.")
                task_type = identificar_tipo(arquivo)
                chunks = dividir_segmentos(
                    segmentos_sanitizados,
                    task_type=task_type,
                    tamanho=chunk_size,
                    sobreposicao=chunk_overlap,
                    source=arquivo.name,
                    tokenizer=tokenizer,
                )
                if not chunks:
                    summary.failed_files += 1
                    summary.errors.append(f"Nenhum chunk gerado: {arquivo.name}")
                    continue

                source_key = (
                    arquivo.name
                    if corpus_scope == "private"
                    else normalize_source_key(arquivo)
                )
                source_id = build_source_id(arquivo)
                title = build_title(arquivo)

                existentes = _buscar_pontos_existentes(
                    cliente, collection_name, source_key, user_id
                )
                if (
                    len(existentes) == len(chunks)
                    and existentes
                    and all(
                        (p.payload or {}).get("file_hash") == file_hash
                        and (p.payload or {}).get("ingestion_version")
                        == INGESTION_VERSION
                        for p in existentes
                    )
                ):
                    summary.skipped_unchanged += 1
                    continue

                vetores = gerar_embeddings([c.text for c in chunks], modelo)
                now_iso = datetime.now(UTC).isoformat()
                pontos = []
                novos_ids: set[str] = set()

                for chunk, vetor in zip(chunks, vetores, strict=True):
                    ponto_id = build_chunk_id(user_id, source_key, chunk.chunk_index)
                    novos_ids.add(ponto_id)
                    pontos.append(
                        models.PointStruct(
                            id=ponto_id,
                            vector=vetor,
                            payload={
                                # 6 campos obrigatórios preservados
                                "text": chunk.text,
                                "source": source_key,
                                "task_type": task_type,
                                "user_id": user_id,
                                "created_at": now_iso,
                                "chunk_index": chunk.chunk_index,
                                # Metadados padronizados TASK-F2-02 / TASK-F2-03
                                "source_id": source_id,
                                "title": title,
                                "page_or_time": chunk.page_or_time,
                                "content_hash": chunk.content_hash,
                                "file_hash": file_hash,
                                "corpus_scope": corpus_scope,
                                "ingestion_version": INGESTION_VERSION,
                                "quality_warning": quality_warning,
                            },
                        )
                    )

                cliente.upsert(
                    collection_name=collection_name, points=pontos, wait=True
                )

                orfaos: list[int | str] = [
                    str(p.id) for p in existentes if str(p.id) not in novos_ids
                ]
                if orfaos:
                    cliente.delete(
                        collection_name=collection_name,
                        points_selector=models.PointIdsList(points=list(orfaos)),
                        wait=True,
                    )
                    summary.orphan_chunks_deleted += len(orfaos)

                summary.processed_files += 1
                summary.total_chunks_upserted += len(pontos)
            except PermissionError:
                raise
            except Exception as erro:
                summary.failed_files += 1
                summary.errors.append(
                    f"Erro ao processar {arquivo.name}: {type(erro).__name__}"
                )

        info = cliente.get_collection(collection_name)
        summary.points_in_collection = int(info.points_count or 0)
        return summary
    finally:
        if owns_client:
            cliente.close()


def executar_pipeline(argv: Sequence[str] | None = None) -> IngestionSummary:
    """CLI de ingestão batch idempotente para a base multimodal do Vezo."""
    parser = argparse.ArgumentParser(
        description="Ingestão multimodal batch idempotente no Qdrant (TASK-F2-02/03)."
    )
    parser.add_argument(
        "--files",
        nargs="+",
        type=Path,
        default=None,
        help="Lista explícita de arquivos para ingestão.",
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path(PASTA_DOCUMENTOS),
        help="Diretório de documentos quando --files não for informado.",
    )
    parser.add_argument(
        "--collection",
        default=os.getenv("QDRANT_COLLECTION", NOME_COLECAO),
        help="Nome da coleção Qdrant.",
    )
    parser.add_argument(
        "--qdrant-url",
        default=os.getenv("QDRANT_URL"),
        help="URL HTTP do Qdrant (ex.: http://localhost:6333).",
    )
    parser.add_argument(
        "--corpus-scope",
        choices=[CORPUS_SCOPE_INSTITUTIONAL, CORPUS_SCOPE_PRIVATE],
        default=CORPUS_SCOPE_INSTITUTIONAL,
        help="Escopo do corpus (private é bloqueado na coleção institucional).",
    )
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Recria a coleção do zero antes da ingestão.",
    )
    args = parser.parse_args(argv)

    summary = ingest_files(
        arquivos=args.files,
        pasta_documentos=args.input_dir,
        collection_name=args.collection,
        corpus_scope=args.corpus_scope,
        recreate=args.recreate,
        qdrant_url=args.qdrant_url,
    )

    print("\n===== RESUMO DE INGESTÃO =====")
    print("Coleção:", summary.collection)
    print("Versão:", summary.ingestion_version)
    print("Documentos processados:", summary.processed_files)
    print("Ignorados (inalterados):", summary.skipped_unchanged)
    print("Deduplicados no lote:", summary.deduplicated_files)
    print("Falhas:", summary.failed_files)
    print("Chunks enviados:", summary.total_chunks_upserted)
    print("Chunks órfãos removidos:", summary.orphan_chunks_deleted)
    print("Pontos armazenados:", summary.points_in_collection)
    if summary.pii_redactions:
        print("Mascaramentos PII:", summary.pii_redactions)
    if summary.quality_warnings:
        print("Avisos de qualidade:", len(summary.quality_warnings))
    return summary


if __name__ == "__main__":
    executar_pipeline()
