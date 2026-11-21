"""Persistência leve e transacional em SQLite para sessões, agenda, propostas e chat."""

from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, time
from pathlib import Path
from typing import Any
from uuid import uuid4

from src.core.schemas import ProposedBlock

from .schemas import (
    ChatHistoryMessage,
    CitationItem,
    ScheduleItemCreate,
    ScheduleItemResponse,
    SessionCreateRequest,
    SessionPreferences,
)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def hash_session_token(raw_token: str) -> str:
    """Deriva hash SHA-256 do token opaco de sessão (nunca persiste o token bruto)."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SessionRecord:
    session_id: str
    schedule_version: int
    preferences: SessionPreferences
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class ProposalRecord:
    proposal_id: str
    session_id: str
    proposal_type: str
    base_version: int
    status: str
    payload: dict[str, Any]
    created_at: str
    resolved_at: str | None


class VersionConflictError(RuntimeError):
    """Levantada quando a agenda mudou entre a geração e a confirmação da proposta."""


class ProposalStateError(RuntimeError):
    """Levantada quando a proposta já foi confirmada ou rejeitada."""


class VezoStore:
    """Repositório SQLite para o MVP do Vezo (TASK-F4-02 / TASK-F4-05)."""

    def __init__(self, db_path: str | Path = "data/vezo.db") -> None:
        self.db_path = Path(db_path)
        self._schema_initialized = False

    @contextmanager
    def _connect(self, *, ensure_schema: bool = True) -> Iterator[sqlite3.Connection]:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        try:
            if ensure_schema and not self._schema_initialized:
                self._init_schema_on_conn(conn)
                self._schema_initialized = True
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema_on_conn(self, conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    token_hash TEXT UNIQUE NOT NULL,
                    schedule_version INTEGER NOT NULL DEFAULT 1,
                    timezone TEXT NOT NULL DEFAULT 'America/Sao_Paulo',
                    sleep_start TEXT NOT NULL DEFAULT '22:00:00',
                    sleep_end TEXT NOT NULL DEFAULT '06:00:00',
                    buffer_minutes INTEGER NOT NULL DEFAULT 0,
                    max_block_minutes INTEGER NOT NULL DEFAULT 60,
                    min_block_minutes INTEGER NOT NULL DEFAULT 1,
                    consent_accepted INTEGER NOT NULL DEFAULT 0,
                    consent_timestamp TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS schedule_items (
                    item_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
                    start_iso TEXT NOT NULL,
                    end_iso TEXT NOT NULL,
                    label TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    fixed INTEGER NOT NULL DEFAULT 1,
                    goal_id TEXT,
                    buffer_before_minutes INTEGER NOT NULL DEFAULT 0,
                    buffer_after_minutes INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_schedule_items_session
                    ON schedule_items(session_id, start_iso);

                CREATE TABLE IF NOT EXISTS proposals (
                    proposal_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
                    proposal_type TEXT NOT NULL,
                    base_version INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    resolved_at TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_proposals_session
                    ON proposals(session_id, created_at);

                CREATE TABLE IF NOT EXISTS chat_messages (
                    message_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_chat_messages_session
                    ON chat_messages(session_id, created_at);
                """
        )

    def ping(self) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT 1 AS ok").fetchone()
            return bool(row and row["ok"] == 1)

    @staticmethod
    def _row_to_session(row: sqlite3.Row) -> SessionRecord:
        prefs = SessionPreferences(
            timezone=row["timezone"],
            sleep_start=time.fromisoformat(row["sleep_start"]),
            sleep_end=time.fromisoformat(row["sleep_end"]),
            buffer_minutes=int(row["buffer_minutes"]),
            max_block_minutes=int(row["max_block_minutes"]),
            min_block_minutes=int(row["min_block_minutes"]),
            consent_accepted=bool(row["consent_accepted"]),
            consent_timestamp=row["consent_timestamp"],
        )
        return SessionRecord(
            session_id=row["session_id"],
            schedule_version=int(row["schedule_version"]),
            preferences=prefs,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _row_to_item(row: sqlite3.Row) -> ScheduleItemResponse:
        return ScheduleItemResponse(
            item_id=row["item_id"],
            start=datetime.fromisoformat(row["start_iso"]),
            end=datetime.fromisoformat(row["end_iso"]),
            label=row["label"],
            kind=row["kind"],
            fixed=bool(row["fixed"]),
            goal_id=row["goal_id"],
            buffer_before_minutes=int(row["buffer_before_minutes"]),
            buffer_after_minutes=int(row["buffer_after_minutes"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _row_to_proposal(row: sqlite3.Row) -> ProposalRecord:
        return ProposalRecord(
            proposal_id=row["proposal_id"],
            session_id=row["session_id"],
            proposal_type=row["proposal_type"],
            base_version=int(row["base_version"]),
            status=row["status"],
            payload=json.loads(row["payload_json"]),
            created_at=row["created_at"],
            resolved_at=row["resolved_at"],
        )

    # --- SESSÕES & PREFERÊNCIAS ---

    def create_session(
        self, payload: SessionCreateRequest | None = None
    ) -> tuple[SessionRecord, str]:
        req = payload or SessionCreateRequest()
        session_id = f"sess-{uuid4().hex}"
        raw_token = secrets.token_urlsafe(32)
        token_hash = hash_session_token(raw_token)
        now = _now_iso()
        consent_ts = now if req.consent_accepted else None

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sessions (
                    session_id, token_hash, schedule_version, timezone,
                    sleep_start, sleep_end, buffer_minutes, max_block_minutes,
                    min_block_minutes, consent_accepted, consent_timestamp,
                    created_at, updated_at
                ) VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    token_hash,
                    req.timezone,
                    req.sleep_start.isoformat(),
                    req.sleep_end.isoformat(),
                    req.buffer_minutes,
                    req.max_block_minutes,
                    req.min_block_minutes,
                    int(req.consent_accepted),
                    consent_ts,
                    now,
                    now,
                ),
            )
            row = conn.execute(
                "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
        assert row is not None
        return self._row_to_session(row), raw_token

    def get_session_by_token(self, raw_token: str) -> SessionRecord | None:
        if not raw_token:
            return None
        token_hash = hash_session_token(raw_token)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE token_hash = ?", (token_hash,)
            ).fetchone()
        return self._row_to_session(row) if row else None

    def get_session_by_id(self, session_id: str) -> SessionRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
        return self._row_to_session(row) if row else None

    def update_preferences(
        self, session_id: str, prefs: SessionPreferences, *, bump_version: bool = True
    ) -> SessionRecord:
        now = _now_iso()
        consent_ts = prefs.consent_timestamp or (
            now if prefs.consent_accepted else None
        )
        version_expr = "schedule_version + 1" if bump_version else "schedule_version"
        with self._connect() as conn:
            conn.execute(
                f"""
                UPDATE sessions
                SET timezone = ?, sleep_start = ?, sleep_end = ?,
                    buffer_minutes = ?, max_block_minutes = ?, min_block_minutes = ?,
                    consent_accepted = ?, consent_timestamp = ?,
                    schedule_version = {version_expr}, updated_at = ?
                WHERE session_id = ?
                """,
                (
                    prefs.timezone,
                    prefs.sleep_start.isoformat(),
                    prefs.sleep_end.isoformat(),
                    prefs.buffer_minutes,
                    prefs.max_block_minutes,
                    prefs.min_block_minutes,
                    int(prefs.consent_accepted),
                    consent_ts,
                    now,
                    session_id,
                ),
            )
            row = conn.execute(
                "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
        assert row is not None
        return self._row_to_session(row)

    # --- CRUD DE AGENDA ---

    def list_schedule_items(self, session_id: str) -> list[ScheduleItemResponse]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM schedule_items
                WHERE session_id = ?
                ORDER BY start_iso ASC, end_iso ASC, item_id ASC
                """,
                (session_id,),
            ).fetchall()
        items = [self._row_to_item(r) for r in rows]
        items.sort(key=lambda i: (i.start.timestamp(), i.end.timestamp(), i.item_id))
        return items

    def get_schedule_item(
        self, session_id: str, item_id: str
    ) -> ScheduleItemResponse | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM schedule_items WHERE session_id = ? AND item_id = ?",
                (session_id, item_id),
            ).fetchone()
        return self._row_to_item(row) if row else None

    def create_schedule_item(
        self, session_id: str, payload: ScheduleItemCreate
    ) -> ScheduleItemResponse:
        item_id = f"itm-{uuid4().hex[:12]}"
        now = _now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO schedule_items (
                    item_id, session_id, start_iso, end_iso, label, kind,
                    fixed, goal_id, buffer_before_minutes, buffer_after_minutes,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item_id,
                    session_id,
                    payload.start.isoformat(),
                    payload.end.isoformat(),
                    payload.label,
                    payload.kind,
                    int(payload.fixed),
                    payload.goal_id,
                    payload.buffer_before_minutes,
                    payload.buffer_after_minutes,
                    now,
                    now,
                ),
            )
            conn.execute(
                "UPDATE sessions SET schedule_version = schedule_version + 1, updated_at = ? WHERE session_id = ?",
                (now, session_id),
            )
            row = conn.execute(
                "SELECT * FROM schedule_items WHERE item_id = ?", (item_id,)
            ).fetchone()
        assert row is not None
        return self._row_to_item(row)

    def update_schedule_item(
        self,
        session_id: str,
        item_id: str,
        updated: ScheduleItemCreate,
    ) -> ScheduleItemResponse | None:
        now = _now_iso()
        with self._connect() as conn:
            cur = conn.execute(
                """
                UPDATE schedule_items
                SET start_iso = ?, end_iso = ?, label = ?, kind = ?, fixed = ?,
                    goal_id = ?, buffer_before_minutes = ?, buffer_after_minutes = ?,
                    updated_at = ?
                WHERE session_id = ? AND item_id = ?
                """,
                (
                    updated.start.isoformat(),
                    updated.end.isoformat(),
                    updated.label,
                    updated.kind,
                    int(updated.fixed),
                    updated.goal_id,
                    updated.buffer_before_minutes,
                    updated.buffer_after_minutes,
                    now,
                    session_id,
                    item_id,
                ),
            )
            if cur.rowcount == 0:
                return None
            conn.execute(
                "UPDATE sessions SET schedule_version = schedule_version + 1, updated_at = ? WHERE session_id = ?",
                (now, session_id),
            )
            row = conn.execute(
                "SELECT * FROM schedule_items WHERE item_id = ?", (item_id,)
            ).fetchone()
        return self._row_to_item(row) if row else None

    def delete_schedule_item(self, session_id: str, item_id: str) -> bool:
        now = _now_iso()
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM schedule_items WHERE session_id = ? AND item_id = ?",
                (session_id, item_id),
            )
            if cur.rowcount == 0:
                return False
            conn.execute(
                "UPDATE sessions SET schedule_version = schedule_version + 1, updated_at = ? WHERE session_id = ?",
                (now, session_id),
            )
        return True

    # --- PROPOSTAS & CONFIRMAÇÃO TRANSACIONAL ---

    def create_proposal(
        self,
        *,
        session_id: str,
        proposal_type: str,
        base_version: int,
        payload: dict[str, Any],
    ) -> ProposalRecord:
        proposal_id = f"prop-{uuid4().hex[:12]}"
        now = _now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO proposals (
                    proposal_id, session_id, proposal_type, base_version,
                    status, payload_json, created_at, resolved_at
                ) VALUES (?, ?, ?, ?, 'pending', ?, ?, NULL)
                """,
                (
                    proposal_id,
                    session_id,
                    proposal_type,
                    base_version,
                    json.dumps(payload, ensure_ascii=False),
                    now,
                ),
            )
            row = conn.execute(
                "SELECT * FROM proposals WHERE proposal_id = ?", (proposal_id,)
            ).fetchone()
        assert row is not None
        return self._row_to_proposal(row)

    def get_proposal(self, session_id: str, proposal_id: str) -> ProposalRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM proposals WHERE session_id = ? AND proposal_id = ?",
                (session_id, proposal_id),
            ).fetchone()
        return self._row_to_proposal(row) if row else None

    def confirm_proposal(
        self,
        *,
        session_id: str,
        proposal_id: str,
        blocks: list[ProposedBlock],
        replace_flexible_in_horizon: tuple[float, float] | None = None,
    ) -> tuple[int, int]:
        """Aplica blocos confirmados atomicamente validando versão da agenda."""
        now = _now_iso()
        with self._connect() as conn:
            sess_row = conn.execute(
                "SELECT schedule_version FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            prop_row = conn.execute(
                "SELECT status, base_version FROM proposals WHERE session_id = ? AND proposal_id = ?",
                (session_id, proposal_id),
            ).fetchone()
            if sess_row is None or prop_row is None:
                raise KeyError("Proposta não encontrada")
            if prop_row["status"] != "pending":
                raise ProposalStateError(
                    f"Proposta já resolvida com status '{prop_row['status']}'."
                )
            current_version = int(sess_row["schedule_version"])
            base_version = int(prop_row["base_version"])
            if current_version != base_version:
                raise VersionConflictError(
                    "Conflito de versão: a agenda foi modificada após a geração "
                    "desta proposta. Gere uma nova proposta antes de confirmar."
                )

            if replace_flexible_in_horizon is not None:
                h_start, h_end = replace_flexible_in_horizon
                flex_rows = conn.execute(
                    """
                    SELECT item_id, start_iso, end_iso FROM schedule_items
                    WHERE session_id = ? AND fixed = 0 AND kind = 'study'
                    """,
                    (session_id,),
                ).fetchall()
                to_delete = [
                    r["item_id"]
                    for r in flex_rows
                    if datetime.fromisoformat(r["start_iso"]).timestamp() < h_end
                    and datetime.fromisoformat(r["end_iso"]).timestamp() > h_start
                ]
                for item_id in to_delete:
                    conn.execute(
                        "DELETE FROM schedule_items WHERE session_id = ? AND item_id = ?",
                        (session_id, item_id),
                    )

            for block in blocks:
                conn.execute(
                    """
                    INSERT INTO schedule_items (
                        item_id, session_id, start_iso, end_iso, label, kind,
                        fixed, goal_id, buffer_before_minutes, buffer_after_minutes,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, 'study', 0, ?, 0, 0, ?, ?)
                    """,
                    (
                        f"itm-{uuid4().hex[:12]}",
                        session_id,
                        block.start.isoformat(),
                        block.end.isoformat(),
                        block.title,
                        block.goal_id,
                        now,
                        now,
                    ),
                )

            new_version = current_version + 1
            conn.execute(
                "UPDATE proposals SET status = 'confirmed', resolved_at = ? WHERE proposal_id = ?",
                (now, proposal_id),
            )
            conn.execute(
                "UPDATE sessions SET schedule_version = ?, updated_at = ? WHERE session_id = ?",
                (new_version, now, session_id),
            )
            count_row = conn.execute(
                "SELECT COUNT(*) AS total FROM schedule_items WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            total_items = int(count_row["total"]) if count_row else 0
        return new_version, total_items

    def reject_proposal(self, *, session_id: str, proposal_id: str) -> tuple[int, int]:
        """Marca proposta como rejeitada preservando integralmente a agenda atual."""
        now = _now_iso()
        with self._connect() as conn:
            sess_row = conn.execute(
                "SELECT schedule_version FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            prop_row = conn.execute(
                "SELECT status FROM proposals WHERE session_id = ? AND proposal_id = ?",
                (session_id, proposal_id),
            ).fetchone()
            if sess_row is None or prop_row is None:
                raise KeyError("Proposta não encontrada")
            if prop_row["status"] != "pending":
                raise ProposalStateError(
                    f"Proposta já resolvida com status '{prop_row['status']}'."
                )
            conn.execute(
                "UPDATE proposals SET status = 'rejected', resolved_at = ? WHERE proposal_id = ?",
                (now, proposal_id),
            )
            count_row = conn.execute(
                "SELECT COUNT(*) AS total FROM schedule_items WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            total_items = int(count_row["total"]) if count_row else 0
            version = int(sess_row["schedule_version"])
        return version, total_items

    # --- HISTÓRICO DE CHAT ---

    def append_chat_message(
        self,
        *,
        session_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        message_id = f"msg-{uuid4().hex[:12]}"
        now = _now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO chat_messages (
                    message_id, session_id, role, content, metadata_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    message_id,
                    session_id,
                    role,
                    content,
                    json.dumps(metadata or {}, ensure_ascii=False),
                    now,
                ),
            )
        return message_id

    def list_chat_history(self, session_id: str) -> list[ChatHistoryMessage]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM chat_messages
                WHERE session_id = ?
                ORDER BY created_at ASC, rowid ASC
                """,
                (session_id,),
            ).fetchall()
        messages: list[ChatHistoryMessage] = []
        for row in rows:
            meta = json.loads(row["metadata_json"])
            raw_citations = meta.get("citations", [])
            citations = [CitationItem.model_validate(c) for c in raw_citations]
            messages.append(
                ChatHistoryMessage(
                    message_id=row["message_id"],
                    role=row["role"],
                    content=row["content"],
                    abstained=meta.get("abstained"),
                    proposal_id=meta.get("proposal_id"),
                    citations=citations,
                    created_at=row["created_at"],
                )
            )
        return messages
