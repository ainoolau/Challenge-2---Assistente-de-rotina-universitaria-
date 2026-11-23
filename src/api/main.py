"""Aplicação FastAPI do Vezo: sessões persistentes, CRUD /schedule, planejamento e chat."""

from __future__ import annotations

import os
import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any, cast

from fastapi import (
    FastAPI,
    File,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from src.agents.schemas import AgentRequest
from src.core.planning import (
    audit_plan,
    audit_rebalance,
    detect_input_conflicts,
    expand_sleep_slots,
    free_windows,
    overlaps,
    plan,
    rebalance,
)
from src.core.schemas import (
    Interval,
    PlanningProposal,
    PlanningRequest,
    ProposedBlock,
    RebalanceProposal,
    RebalanceRequest,
    ScheduleSlot,
)

from .dependencies import (
    SESSION_COOKIE_NAME,
    DefaultOrchestratorManager,
    OrchestratorProvider,
    ServiceUnavailableError,
    SessionDep,
    StoreDep,
)
from .schemas import (
    ChatHistoryMessage,
    ChatQueryRequest,
    ChatQueryResponse,
    CitationItem,
    HealthResponse,
    OptimizeScheduleRequest,
    PreferencesUpdateRequest,
    ProposalActionResponse,
    ReallocateScheduleRequest,
    ScheduleItemCreate,
    ScheduleItemResponse,
    ScheduleItemUpdate,
    ScheduleListResponse,
    ScheduleProposalResponse,
    SessionCreateRequest,
    SessionPreferences,
    SessionResponse,
)
from .storage import (
    ProposalStateError,
    VersionConflictError,
    VezoStore,
)


def _overlaps_protected_sleep(interval: Interval, prefs: SessionPreferences) -> bool:
    sleep_slots = expand_sleep_slots(
        horizon=interval,
        timezone=prefs.timezone,
        sleep_start=prefs.sleep_start,
        sleep_end=prefs.sleep_end,
    )
    return any(overlaps(interval, sleep) for sleep in sleep_slots)


def _items_to_fixed_slots(items: list[ScheduleItemResponse]) -> list[ScheduleSlot]:
    slots: list[ScheduleSlot] = []
    for item in items:
        if not item.fixed:
            continue
        slot_kind = item.kind if item.kind != "study" else "other"
        slots.append(
            ScheduleSlot(
                slot_id=item.item_id,
                start=item.start,
                end=item.end,
                label=item.label,
                kind=cast(Any, slot_kind),
                fixed=True,
                buffer_before_minutes=item.buffer_before_minutes,
                buffer_after_minutes=item.buffer_after_minutes,
            )
        )
    return slots


def _items_to_all_busy_slots(items: list[ScheduleItemResponse]) -> list[ScheduleSlot]:
    """Converte todos os itens persistidos em slots ocupados para evitar sobreposição."""
    slots: list[ScheduleSlot] = []
    for item in items:
        slot_kind = item.kind if item.kind != "study" else "other"
        slots.append(
            ScheduleSlot(
                slot_id=item.item_id,
                start=item.start,
                end=item.end,
                label=item.label,
                kind=cast(Any, slot_kind),
                fixed=item.fixed,
                buffer_before_minutes=item.buffer_before_minutes,
                buffer_after_minutes=item.buffer_after_minutes,
            )
        )
    return slots


def _items_to_flexible_blocks(
    items: list[ScheduleItemResponse], horizon: Interval
) -> list[ProposedBlock]:
    h_start = horizon.start.timestamp()
    h_end = horizon.end.timestamp()
    blocks: list[ProposedBlock] = []
    for item in items:
        if item.fixed or item.kind != "study":
            continue
        if item.start.timestamp() < h_end and item.end.timestamp() > h_start:
            blocks.append(
                ProposedBlock(
                    goal_id=item.goal_id or item.item_id,
                    title=item.label,
                    start=item.start,
                    end=item.end,
                )
            )
    return blocks


def create_app(
    *,
    db_path: str | Path | None = None,
    orchestrator_provider: OrchestratorProvider | None = None,
    cors_origins: list[str] | None = None,
) -> FastAPI:
    """Cria instância configurável da aplicação FastAPI do Vezo."""
    resolved_db: str | Path = (
        db_path if db_path is not None else os.getenv("VEZO_DB_PATH", "data/vezo.db")
    )
    store = VezoStore(resolved_db)
    default_manager = DefaultOrchestratorManager()
    provider = orchestrator_provider or default_manager.get

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            default_manager.close()

    app = FastAPI(
        title="Vezo API — Assistente de Rotina Universitária",
        version="0.1.0",
        description=(
            "API FastAPI do MVP Vezo: sessões persistentes, CRUD de agenda com "
            "proteção de sono e eventos fixos, motor determinístico compartilhado "
            "(otimização e rebalanceamento com confirmação explícita) e chat RAG/multiagentes."
        ),
        lifespan=lifespan,
    )
    app.state.store = store
    app.state.orchestrator_provider = provider

    origins = cors_origins
    if origins is None:
        raw_origins = os.getenv(
            "VEZO_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
        )
        origins = [o.strip() for o in raw_origins.split(",") if o.strip()]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # =========================================================================
    # 1. HEALTH & SESSÕES (TASK-F4-02 #66)
    # =========================================================================

    @app.get("/health", response_model=HealthResponse, tags=["health"])
    def health(store_dep: StoreDep) -> HealthResponse:
        return HealthResponse(
            status="ok",
            db_ok=store_dep.ping(),
            qdrant_configured=bool(
                os.getenv("QDRANT_URL") or Path("data/qdrant").is_dir()
            ),
            llm_configured=bool(os.getenv("GROQ_API_KEY")),
        )

    @app.post(
        "/sessions",
        response_model=SessionResponse,
        status_code=status.HTTP_201_CREATED,
        tags=["sessions"],
    )
    def create_session(
        response: Response,
        store_dep: StoreDep,
        payload: SessionCreateRequest | None = None,
    ) -> SessionResponse:
        session, raw_token = store_dep.create_session(payload)
        cookie_secure = os.getenv("VEZO_COOKIE_SECURE", "false").lower() == "true"
        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=raw_token,
            httponly=True,
            samesite="lax",
            secure=cookie_secure,
            path="/",
        )
        return SessionResponse(
            session_id=session.session_id,
            session_token=raw_token,
            schedule_version=session.schedule_version,
            preferences=session.preferences,
            created_at=session.created_at,
        )

    @app.get("/sessions/me", response_model=SessionResponse, tags=["sessions"])
    def get_current_session(session: SessionDep) -> SessionResponse:
        return SessionResponse(
            session_id=session.session_id,
            session_token=None,
            schedule_version=session.schedule_version,
            preferences=session.preferences,
            created_at=session.created_at,
        )

    @app.get("/preferences", response_model=SessionPreferences, tags=["preferences"])
    def get_preferences(session: SessionDep) -> SessionPreferences:
        return session.preferences

    @app.put("/preferences", response_model=SessionPreferences, tags=["preferences"])
    @app.patch("/preferences", response_model=SessionPreferences, tags=["preferences"])
    def update_preferences(
        payload: PreferencesUpdateRequest,
        session: SessionDep,
        store_dep: StoreDep,
    ) -> SessionPreferences:
        merged_data = session.preferences.model_dump()
        updates = payload.model_dump(exclude_none=True)
        merged_data.update(updates)
        try:
            validated = SessionPreferences.model_validate(merged_data)
        except ValidationError as exc:
            raise HTTPException(
                status_code=422,
                detail=exc.errors(),
            ) from exc

        updated = store_dep.update_preferences(
            session.session_id, validated, bump_version=True
        )
        return updated.preferences

    # =========================================================================
    # 2. CRUD /schedule & PROTEÇÃO DE FIXOS/SONO (TASK-F4-03 #67)
    # =========================================================================

    @app.get("/schedule", response_model=ScheduleListResponse, tags=["schedule"])
    def list_schedule(
        session: SessionDep,
        store_dep: StoreDep,
        horizon_start: Annotated[datetime | None, Query()] = None,
        horizon_end: Annotated[datetime | None, Query()] = None,
    ) -> ScheduleListResponse:
        items = store_dep.list_schedule_items(session.session_id)
        fixed_slots = _items_to_fixed_slots(items)
        conflicts = detect_input_conflicts(fixed_slots)

        windows: list[Interval] = []
        if horizon_start is not None or horizon_end is not None:
            if horizon_start is None or horizon_end is None:
                raise HTTPException(
                    status_code=422,
                    detail="Informe horizon_start e horizon_end juntos.",
                )
            try:
                horizon = Interval(start=horizon_start, end=horizon_end)
                plan_req = PlanningRequest(
                    timezone=session.preferences.timezone,
                    horizon=horizon,
                    schedule_slots=_items_to_all_busy_slots(items),
                    sleep_start=session.preferences.sleep_start,
                    sleep_end=session.preferences.sleep_end,
                    buffer_minutes=session.preferences.buffer_minutes,
                    max_block_minutes=session.preferences.max_block_minutes,
                    min_block_minutes=session.preferences.min_block_minutes,
                )
            except ValidationError as exc:
                raise HTTPException(
                    status_code=422,
                    detail=exc.errors(),
                ) from exc
            windows = free_windows(plan_req)

        return ScheduleListResponse(
            schedule_version=session.schedule_version,
            preferences=session.preferences,
            items=items,
            input_conflicts=conflicts,
            free_windows=windows,
        )

    @app.post(
        "/schedule",
        response_model=ScheduleItemResponse,
        status_code=status.HTTP_201_CREATED,
        tags=["schedule"],
    )
    def create_schedule_item(
        payload: ScheduleItemCreate,
        session: SessionDep,
        store_dep: StoreDep,
    ) -> ScheduleItemResponse:
        if payload.kind == "sleep":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Períodos de sono protegido não podem ser criados como itens "
                    "avulsos; configure em PUT /preferences."
                ),
            )
        if _overlaps_protected_sleep(payload, session.preferences):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Intervalo invade a janela de sono protegido da sessão "
                    f"({session.preferences.sleep_start.strftime('%H:%M')}-"
                    f"{session.preferences.sleep_end.strftime('%H:%M')} "
                    f"{session.preferences.timezone})."
                ),
            )
        return store_dep.create_schedule_item(session.session_id, payload)

    @app.patch(
        "/schedule/{item_id}",
        response_model=ScheduleItemResponse,
        tags=["schedule"],
    )
    def update_schedule_item(
        item_id: str,
        payload: ScheduleItemUpdate,
        session: SessionDep,
        store_dep: StoreDep,
        force_fixed: Annotated[
            bool,
            Query(
                description="Exige autorização explícita para alterar compromissos fixos."
            ),
        ] = False,
    ) -> ScheduleItemResponse:
        existing = store_dep.get_schedule_item(session.session_id, item_id)
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Item da agenda não encontrado nesta sessão.",
            )
        if existing.kind == "sleep" or (existing.fixed and not force_fixed):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Compromisso fixo ou período protegido bloqueado contra edição "
                    "direta."
                ),
            )

        merged_data = {
            "start": payload.start if payload.start is not None else existing.start,
            "end": payload.end if payload.end is not None else existing.end,
            "label": payload.label if payload.label is not None else existing.label,
            "kind": payload.kind if payload.kind is not None else existing.kind,
            "fixed": payload.fixed if payload.fixed is not None else existing.fixed,
            "goal_id": (
                payload.goal_id if payload.goal_id is not None else existing.goal_id
            ),
            "buffer_before_minutes": (
                payload.buffer_before_minutes
                if payload.buffer_before_minutes is not None
                else existing.buffer_before_minutes
            ),
            "buffer_after_minutes": (
                payload.buffer_after_minutes
                if payload.buffer_after_minutes is not None
                else existing.buffer_after_minutes
            ),
        }
        try:
            validated = ScheduleItemCreate.model_validate(merged_data)
        except ValidationError as exc:
            raise HTTPException(
                status_code=422,
                detail=exc.errors(),
            ) from exc

        if validated.kind == "sleep" or _overlaps_protected_sleep(
            validated, session.preferences
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Atualização bloqueada: intervalo invade sono protegido.",
            )

        updated = store_dep.update_schedule_item(session.session_id, item_id, validated)
        assert updated is not None
        return updated

    @app.delete(
        "/schedule/{item_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        tags=["schedule"],
    )
    def delete_schedule_item(
        item_id: str,
        session: SessionDep,
        store_dep: StoreDep,
        force_fixed: Annotated[
            bool,
            Query(
                description="Exige autorização explícita para remover compromissos fixos."
            ),
        ] = False,
    ) -> Response:
        existing = store_dep.get_schedule_item(session.session_id, item_id)
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Item da agenda não encontrado nesta sessão.",
            )
        if existing.kind == "sleep" or (existing.fixed and not force_fixed):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Compromisso fixo ou período protegido bloqueado contra remoção "
                    "direta."
                ),
            )
        store_dep.delete_schedule_item(session.session_id, item_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    # =========================================================================
    # 3. OTIMIZAÇÃO, REALOCAÇÃO & CONFIRMAÇÃO TRANSACIONAL (TASK-F4-05 #69)
    # =========================================================================

    @app.post(
        "/schedule/optimize",
        response_model=ScheduleProposalResponse,
        tags=["planning"],
    )
    def optimize_schedule(
        payload: OptimizeScheduleRequest,
        session: SessionDep,
        store_dep: StoreDep,
    ) -> ScheduleProposalResponse:
        items = store_dep.list_schedule_items(session.session_id)
        prefs = session.preferences
        try:
            plan_req = PlanningRequest(
                timezone=prefs.timezone,
                horizon=payload.horizon,
                schedule_slots=_items_to_all_busy_slots(items),
                study_goals=payload.study_goals,
                sleep_start=prefs.sleep_start,
                sleep_end=prefs.sleep_end,
                buffer_minutes=(
                    payload.buffer_minutes
                    if payload.buffer_minutes is not None
                    else prefs.buffer_minutes
                ),
                max_block_minutes=(
                    payload.max_block_minutes
                    if payload.max_block_minutes is not None
                    else prefs.max_block_minutes
                ),
                min_block_minutes=(
                    payload.min_block_minutes
                    if payload.min_block_minutes is not None
                    else prefs.min_block_minutes
                ),
            )
        except ValidationError as exc:
            raise HTTPException(
                status_code=422,
                detail=exc.errors(),
            ) from exc

        proposal = plan(plan_req)
        assert proposal is not None
        violations = audit_plan(plan_req, proposal)
        if violations:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Falha na auditoria determinística do plano proposto.",
            )

        conflicts = detect_input_conflicts(_items_to_fixed_slots(items))
        record = store_dep.create_proposal(
            session_id=session.session_id,
            proposal_type="optimize",
            base_version=session.schedule_version,
            payload={
                "planning_request": plan_req.model_dump(mode="json"),
                "planning": proposal.model_dump(mode="json"),
            },
        )
        return ScheduleProposalResponse(
            proposal_id=record.proposal_id,
            proposal_type="optimize",
            status="pending",
            base_version=record.base_version,
            planning=proposal,
            input_conflicts=conflicts,
            created_at=record.created_at,
        )

    @app.post(
        "/schedule/reallocate",
        response_model=ScheduleProposalResponse,
        tags=["planning"],
    )
    def reallocate_schedule(
        payload: ReallocateScheduleRequest,
        session: SessionDep,
        store_dep: StoreDep,
    ) -> ScheduleProposalResponse:
        items = store_dep.list_schedule_items(session.session_id)
        prefs = session.preferences
        fixed_slots = _items_to_fixed_slots(items)
        existing_blocks = _items_to_flexible_blocks(items, payload.horizon)

        try:
            reb_req = RebalanceRequest(
                timezone=prefs.timezone,
                horizon=payload.horizon,
                schedule_slots=fixed_slots,
                disruptions=payload.disruptions,
                existing_blocks=existing_blocks,
                study_goals=payload.study_goals,
                sleep_start=prefs.sleep_start,
                sleep_end=prefs.sleep_end,
                buffer_minutes=(
                    payload.buffer_minutes
                    if payload.buffer_minutes is not None
                    else prefs.buffer_minutes
                ),
                max_block_minutes=(
                    payload.max_block_minutes
                    if payload.max_block_minutes is not None
                    else prefs.max_block_minutes
                ),
                min_block_minutes=(
                    payload.min_block_minutes
                    if payload.min_block_minutes is not None
                    else prefs.min_block_minutes
                ),
                disruption_note=payload.disruption_note,
            )
        except ValidationError as exc:
            raise HTTPException(
                status_code=422,
                detail=exc.errors(),
            ) from exc

        proposal = rebalance(reb_req)
        violations = audit_rebalance(reb_req, proposal)
        if violations:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Falha na auditoria determinística do rebalanceamento.",
            )

        record = store_dep.create_proposal(
            session_id=session.session_id,
            proposal_type="reallocate",
            base_version=session.schedule_version,
            payload={
                "rebalance_request": reb_req.model_dump(mode="json"),
                "rebalance": proposal.model_dump(mode="json"),
            },
        )
        return ScheduleProposalResponse(
            proposal_id=record.proposal_id,
            proposal_type="reallocate",
            status="pending",
            base_version=record.base_version,
            rebalance=proposal,
            input_conflicts=proposal.input_conflicts,
            created_at=record.created_at,
        )

    @app.post(
        "/schedule/proposals/{proposal_id}/confirm",
        response_model=ProposalActionResponse,
        tags=["planning"],
    )
    def confirm_proposal(
        proposal_id: str,
        session: SessionDep,
        store_dep: StoreDep,
    ) -> ProposalActionResponse:
        record = store_dep.get_proposal(session.session_id, proposal_id)
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Proposta não encontrada nesta sessão.",
            )

        blocks_to_apply: list[ProposedBlock]
        replace_bounds: tuple[float, float] | None = None

        if record.proposal_type == "reallocate":
            reb_req = RebalanceRequest.model_validate(
                record.payload["rebalance_request"]
            )
            reb_prop = RebalanceProposal.model_validate(record.payload["rebalance"])
            if audit_rebalance(reb_req, reb_prop):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Proposta reprovada na reauditoria de invariantes.",
                )
            blocks_to_apply = reb_prop.proposed_blocks
            replace_bounds = (
                reb_req.horizon.start.timestamp(),
                reb_req.horizon.end.timestamp(),
            )
        else:
            plan_req = PlanningRequest.model_validate(
                record.payload["planning_request"]
            )
            plan_prop = PlanningProposal.model_validate(record.payload["planning"])
            if audit_plan(plan_req, plan_prop):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Proposta reprovada na reauditoria de invariantes.",
                )
            blocks_to_apply = plan_prop.proposed_blocks

        try:
            new_version, total_items = store_dep.confirm_proposal(
                session_id=session.session_id,
                proposal_id=proposal_id,
                blocks=blocks_to_apply,
                replace_flexible_in_horizon=replace_bounds,
            )
        except (ProposalStateError, VersionConflictError) as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=str(exc)
            ) from exc

        return ProposalActionResponse(
            proposal_id=proposal_id,
            status="confirmed",
            schedule_version=new_version,
            applied_blocks=blocks_to_apply,
            items_count=total_items,
            message=(
                f"Proposta confirmada e aplicada ({len(blocks_to_apply)} blocos "
                "flexíveis gravados; sono e fixos preservados)."
            ),
        )

    @app.post(
        "/schedule/proposals/{proposal_id}/reject",
        response_model=ProposalActionResponse,
        tags=["planning"],
    )
    def reject_proposal(
        proposal_id: str,
        session: SessionDep,
        store_dep: StoreDep,
    ) -> ProposalActionResponse:
        record = store_dep.get_proposal(session.session_id, proposal_id)
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Proposta não encontrada nesta sessão.",
            )
        try:
            version, total_items = store_dep.reject_proposal(
                session_id=session.session_id,
                proposal_id=proposal_id,
            )
        except ProposalStateError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=str(exc)
            ) from exc

        return ProposalActionResponse(
            proposal_id=proposal_id,
            status="rejected",
            schedule_version=version,
            applied_blocks=[],
            items_count=total_items,
            message="Proposta rejeitada; agenda mantida sem alterações.",
        )

    # =========================================================================
    # 4. CHAT MULTIAGENTES & HISTÓRICO (TASK-F4-04 #68)
    # =========================================================================

    @app.post("/documents/upload", tags=["documents"], status_code=201)
    async def upload_document(
        session: SessionDep, file: Annotated[UploadFile, File()]
    ) -> dict[str, Any]:
        from src.data_pipeline.ingestion import ingest_files
        from src.data_pipeline.retrieval import get_client

        filename = Path((file.filename or "").replace("\\", "/")).name
        if not filename or Path(filename).suffix.lower() not in {
            ".pdf",
            ".txt",
            ".docx",
            ".png",
            ".jpg",
            ".jpeg",
        }:
            raise HTTPException(status_code=400, detail="Extensão de arquivo inválida.")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / filename
            size = 0
            with path.open("wb") as output:
                while chunk := await file.read(1024 * 1024):
                    size += len(chunk)
                    if size > 10 * 1024 * 1024:
                        raise HTTPException(
                            status_code=413, detail="Arquivo excede 10 MB."
                        )
                    output.write(chunk)
            if not size:
                raise HTTPException(status_code=400, detail="Arquivo vazio.")
            try:
                client = get_client()
                try:
                    summary = await run_in_threadpool(
                        ingest_files,
                        [path],
                        collection_name="vezo_user_private",
                        user_id=session.session_id,
                        corpus_scope="private",
                        target_collection_scope="private",
                        client=client,
                    )
                finally:
                    client.close()
            except Exception as exc:
                raise HTTPException(
                    status_code=503, detail="Serviço de ingestão indisponível."
                ) from exc
            if summary.failed_files or not (
                summary.processed_files or summary.skipped_unchanged
            ):
                raise HTTPException(
                    status_code=422, detail="Não foi possível extrair texto do arquivo."
                )
            return {
                "filename": filename,
                "chunks": summary.total_chunks_upserted,
                "unchanged": bool(summary.skipped_unchanged),
            }

    @app.get("/documents", tags=["documents"])
    def list_documents(session: SessionDep) -> list[dict[str, Any]]:
        from qdrant_client import models

        from src.data_pipeline.retrieval import get_client

        try:
            client = get_client()
            try:
                if not client.collection_exists("vezo_user_private"):
                    return []
                offset = None
                documents: dict[str, dict[str, Any]] = {}
                while True:
                    points, offset = client.scroll(
                        collection_name="vezo_user_private",
                        scroll_filter=models.Filter(
                            must=[
                                models.FieldCondition(
                                    key="user_id",
                                    match=models.MatchValue(value=session.session_id),
                                ),
                                models.FieldCondition(
                                    key="corpus_scope",
                                    match=models.MatchValue(value="private"),
                                ),
                            ]
                        ),
                        limit=256,
                        offset=offset,
                        with_payload=True,
                        with_vectors=False,
                    )
                    for point in points:
                        payload = point.payload or {}
                        source = str(payload.get("source", ""))
                        documents[source] = {
                            "filename": source,
                            "created_at": payload.get("created_at"),
                        }
                    if offset is None:
                        break
                return list(documents.values())
            finally:
                client.close()
        except Exception as exc:
            raise HTTPException(
                status_code=503, detail="Base de documentos indisponível."
            ) from exc

    @app.post("/chat/query", response_model=ChatQueryResponse, tags=["chat"])
    async def chat_query(
        request: Request,
        payload: ChatQueryRequest,
        session: SessionDep,
        store_dep: StoreDep,
    ) -> ChatQueryResponse:
        items = (
            store_dep.list_schedule_items(session.session_id)
            if payload.include_session_schedule
            else []
        )
        prefs = session.preferences
        busy_slots = _items_to_all_busy_slots(items)
        fixed_conflicts = detect_input_conflicts(_items_to_fixed_slots(items))

        try:
            agent_req = AgentRequest(
                question=payload.question,
                timezone=prefs.timezone,
                schedule_slots=busy_slots,
                study_goals=payload.study_goals,
                horizon=payload.horizon,
                sleep_start=prefs.sleep_start,
                sleep_end=prefs.sleep_end,
                buffer_minutes=prefs.buffer_minutes,
                max_block_minutes=prefs.max_block_minutes,
                min_block_minutes=prefs.min_block_minutes,
            )
        except ValidationError as exc:
            raise HTTPException(
                status_code=422,
                detail=exc.errors(),
            ) from exc

        orch_provider: OrchestratorProvider = request.app.state.orchestrator_provider
        try:
            if orchestrator_provider is None:
                orchestrator = await run_in_threadpool(
                    default_manager.get, payload.scope, session.session_id
                )
            elif payload.scope == "demo":
                orchestrator = await run_in_threadpool(orch_provider)
            else:
                raise ServiceUnavailableError("Provedor privado não configurado.")
            try:
                result = await run_in_threadpool(orchestrator.run, agent_req)
            finally:
                if orchestrator_provider is None and payload.scope == "private":
                    orchestrator.research.retriever.close()
        except ServiceUnavailableError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Serviço de consulta indisponível no momento; "
                    "nenhuma resposta foi inventada e nenhuma agenda foi alterada."
                ),
            ) from exc

        if result.status == "error":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    result.error.get("message")
                    if result.error
                    else "Falha temporária no fluxo multiagente; nenhuma agenda foi alterada."
                ),
            )

        citations: list[CitationItem] = []
        if result.retrieval is not None:
            cited_ids = set(result.retrieval.citations)
            selected_chunks = [
                c
                for c in result.retrieval.chunks
                if not cited_ids or c.source_id in cited_ids
            ]
            if result.status == "completed":
                citations = [
                    CitationItem(
                        source_id=c.source_id,
                        source=c.source,
                        title=c.title,
                        page_or_time=c.page_or_time,
                        text=c.text,
                        score=c.score,
                        task_type=c.task_type,
                    )
                    for c in selected_chunks
                ]

        planning_proposal: PlanningProposal | None = None
        proposal_id: str | None = None
        if (
            result.status == "completed"
            and result.proposal is not None
            and result.proposal.planning is not None
        ):
            planning_proposal = result.proposal.planning
            plan_req = PlanningRequest(
                timezone=agent_req.timezone,
                schedule_slots=agent_req.schedule_slots,
                study_goals=agent_req.study_goals,
                horizon=agent_req.horizon,
                sleep_start=agent_req.sleep_start,
                sleep_end=agent_req.sleep_end,
                buffer_minutes=agent_req.buffer_minutes,
                max_block_minutes=agent_req.max_block_minutes,
                min_block_minutes=agent_req.min_block_minutes,
            )
            prop_record = store_dep.create_proposal(
                session_id=session.session_id,
                proposal_type="chat",
                base_version=session.schedule_version,
                payload={
                    "planning_request": plan_req.model_dump(mode="json"),
                    "planning": planning_proposal.model_dump(mode="json"),
                },
            )
            proposal_id = prop_record.proposal_id

        abstained = result.status == "abstained"
        limitations = (
            list(result.proposal.limitations) if result.proposal is not None else []
        )
        gaps = list(result.retrieval.gaps) if result.retrieval is not None else []

        store_dep.append_chat_message(
            session_id=session.session_id,
            role="user",
            content=payload.question,
            metadata={"run_id": result.run_id},
        )
        store_dep.append_chat_message(
            session_id=session.session_id,
            role="assistant",
            content=result.final_answer,
            metadata={
                "run_id": result.run_id,
                "status": result.status,
                "abstained": abstained,
                "proposal_id": proposal_id,
                "citations": [c.model_dump(mode="json") for c in citations],
            },
        )

        return ChatQueryResponse(
            run_id=result.run_id,
            status=result.status,
            abstained=abstained,
            answer=result.final_answer,
            citations=citations,
            limitations=limitations,
            gaps=gaps,
            input_conflicts=fixed_conflicts,
            planning=planning_proposal,
            proposal_id=proposal_id,
            llm_calls=result.metrics.llm_calls,
            total_latency_ms=result.metrics.total_latency_ms,
        )

    @app.get(
        "/chat/history",
        response_model=list[ChatHistoryMessage],
        tags=["chat"],
    )
    def get_chat_history(
        session: SessionDep,
        store_dep: StoreDep,
    ) -> list[ChatHistoryMessage]:
        return store_dep.list_chat_history(session.session_id)

    return app


app = create_app()
