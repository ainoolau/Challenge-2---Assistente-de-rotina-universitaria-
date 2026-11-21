"""Sanitização mínima de PII e segregação de corpus para ingestão RAG (TASK-F2-03)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

CORPUS_SCOPE_INSTITUTIONAL = "institutional"
CORPUS_SCOPE_PRIVATE = "private"
VALID_CORPUS_SCOPES = frozenset({CORPUS_SCOPE_INSTITUTIONAL, CORPUS_SCOPE_PRIVATE})

PRIVATE_PATH_MARKERS = frozenset(
    {"private", "privado", "privados", "personal", "pessoal", "user_private"}
)

# CPF formatado (000.000.000-00) ou precedido explicitamente pelo rótulo CPF.
_CPF_FORMATTED_RE = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b")
_CPF_LABELED_RE = re.compile(r"(?i)\b(cpf\s*[:#-]?\s*)(\d{11})\b")

# E-mail padrão.
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")

# Telefones brasileiros (com +55, DDD ou formato 9XXXX-XXXX / XXXX-XXXX com contexto).
_PHONE_BR_RE = re.compile(
    r"(?<!\d)(?:\+55\s?)?(?:\(\d{2}\)\s?|\b\d{2}\s)(?:9\s?)?\d{4}[-\s]?\d{4}\b"
)
_PHONE_LABELED_RE = re.compile(
    r"(?i)\b((?:telefone|celular|whatsapp|fone|tel\.?)\s*[:#-]?\s*)"
    r"((?:\+?\d[\d\s().-]{7,16}\d))"
)

# Nome acompanhado de matrícula / RA / RGA na mesma linha ou na linha seguinte.
_LABELED_NAME_BEFORE_ID_RE = re.compile(
    r"(?im)^(\s*(?:nome(?:\s+completo)?|estudante|aluno(?:a)?|discente)\s*[:#-]\s*)"
    r"([^\r\n|;()]{3,80}?)"
    r"(?=\s*(?:[-–—|,(]|\r?\n)\s*(?:matr[íi]cula|ra|rga|cpf)\b)"
)

_INLINE_NAME_WITH_ID_RE = re.compile(
    r"(?m)(?<![A-Za-zÀ-ÖØ-öø-ÿ])"
    r"([A-ZÀ-Ý][a-zà-ÿ]{1,25}(?:\s+(?:da|de|do|das|dos|e|[A-ZÀ-Ý][a-zà-ÿ]{1,25})){1,5})"
    r"(\s*[-–—|,(]\s*(?i:matr[íi]cula|ra|rga)\s*[:#-]?\s*)"
    r"([A-Za-z0-9][A-Za-z0-9./-]{3,20})"
)

# Matrícula / RA / RGA precedido por rótulo.
_MATRICULA_RE = re.compile(
    r"(?i)\b(matr[íi]cula|ra|rga)(\s*[:#-]?\s*)(\d[\d./-]{3,20})\b"
)


@dataclass(frozen=True)
class SanitizationResult:
    """Resultado determinístico da sanitização de PII em um texto."""

    text: str
    redactions: dict[str, int] = field(default_factory=dict)

    @property
    def had_pii(self) -> bool:
        return sum(self.redactions.values()) > 0


def mask_pii(text: str) -> SanitizationResult:
    """Mascara identificadores pessoais comuns preservando conteúdo acadêmico."""
    if not text:
        return SanitizationResult(text=text, redactions={})

    redactions: dict[str, int] = {}
    sanitized = text

    def _sub(
        pattern: re.Pattern[str],
        repl: str,
        key: str,
        current: str,
    ) -> str:
        updated, count = pattern.subn(repl, current)
        if count:
            redactions[key] = redactions.get(key, 0) + count
        return updated

    # 1. Nome acompanhado de matrícula/RA/RGA (antes de mascarar matrícula/CPF).
    sanitized = _sub(
        _LABELED_NAME_BEFORE_ID_RE,
        r"\1[NOME_REMOVIDO]",
        "nome_com_identificador",
        sanitized,
    )
    sanitized = _sub(
        _INLINE_NAME_WITH_ID_RE,
        r"[NOME_REMOVIDO]\2[MATRICULA_REMOVIDA]",
        "nome_com_matricula",
        sanitized,
    )

    # 2. Matrícula / RA / RGA.
    sanitized = _sub(
        _MATRICULA_RE,
        r"\1\2[MATRICULA_REMOVIDA]",
        "matricula",
        sanitized,
    )

    # 3. CPF.
    sanitized = _sub(_CPF_FORMATTED_RE, "[CPF_REMOVIDO]", "cpf", sanitized)
    sanitized = _sub(_CPF_LABELED_RE, r"\1[CPF_REMOVIDO]", "cpf", sanitized)

    # 4. E-mail.
    sanitized = _sub(_EMAIL_RE, "[EMAIL_REMOVIDO]", "email", sanitized)

    # 5. Telefone.
    sanitized = _sub(
        _PHONE_LABELED_RE,
        r"\1[TELEFONE_REMOVIDO]",
        "telefone",
        sanitized,
    )
    sanitized = _sub(_PHONE_BR_RE, "[TELEFONE_REMOVIDO]", "telefone", sanitized)

    return SanitizationResult(text=sanitized, redactions=redactions)


def is_private_path(path: Path) -> bool:
    """Detecta se o caminho aponta explicitamente para um diretório privado."""
    parts = {part.lower() for part in path.parts}
    return bool(parts & PRIVATE_PATH_MARKERS)


def validate_corpus_segregation(
    *,
    corpus_scope: str,
    target_collection_scope: str = CORPUS_SCOPE_INSTITUTIONAL,
    source_path: Path | None = None,
) -> None:
    """Impede indexação de dados privados no índice institucional compartilhado."""
    if corpus_scope not in VALID_CORPUS_SCOPES:
        raise ValueError(
            f"Escopo de corpus inválido: {corpus_scope!r}. "
            f"Use um de: {sorted(VALID_CORPUS_SCOPES)}."
        )
    if target_collection_scope not in VALID_CORPUS_SCOPES:
        raise ValueError(
            f"Escopo alvo de coleção inválido: {target_collection_scope!r}. "
            f"Use um de: {sorted(VALID_CORPUS_SCOPES)}."
        )
    if (
        corpus_scope == CORPUS_SCOPE_PRIVATE
        and target_collection_scope == CORPUS_SCOPE_INSTITUTIONAL
    ):
        raise PermissionError(
            "Segregação LGPD: dados privados não podem ser indexados no índice "
            "institucional compartilhado."
        )
    if (
        source_path is not None
        and target_collection_scope == CORPUS_SCOPE_INSTITUTIONAL
        and is_private_path(source_path)
    ):
        raise PermissionError(
            f"Segregação LGPD: caminho privado bloqueado para índice institucional: "
            f"{source_path.as_posix()}"
        )
