"""Dependências de sessão segura e provedor de orquestrador multiagentes da API."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any

from fastapi import Cookie, Depends, Header, HTTPException, Request, status

from src.agents.analysis_planning_agent import AnalysisPlanningAgent
from src.agents.llm import GroqLLM, LLMConfig, load_api_key
from src.agents.orchestrator import MultiAgentOrchestrator
from src.agents.research_agent import QdrantRetriever, ResearchAgent
from src.agents.validation_agent import ValidationAgent

from .storage import SessionRecord, VezoStore

SESSION_COOKIE_NAME = "vezo_session"


class ServiceUnavailableError(RuntimeError):
    """Indisponibilidade temporária do Qdrant ou provedor LLM (sem inventar resposta)."""


OrchestratorProvider = Callable[[], MultiAgentOrchestrator]


def get_store(request: Request) -> VezoStore:
    store: VezoStore = request.app.state.store
    return store


def require_session(
    request: Request,
    vezo_session: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
    x_session_token: Annotated[str | None, Header(alias="X-Session-Token")] = None,
) -> SessionRecord:
    """Autentica a sessão por cookie HttpOnly ou fallback opcional X-Session-Token."""
    raw_token = vezo_session or x_session_token
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão ausente. Crie uma sessão em POST /sessions.",
        )
    store = get_store(request)
    session = store.get_session_by_token(raw_token)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de sessão inválido ou expirado.",
        )
    return session


StoreDep = Annotated[VezoStore, Depends(get_store)]
SessionDep = Annotated[SessionRecord, Depends(require_session)]


class DefaultOrchestratorManager:
    """Inicialização tardia e segura de QdrantRetriever + GroqLLM para /chat/query."""

    def __init__(self) -> None:
        self._retriever: Any = None
        self._orchestrator: MultiAgentOrchestrator | None = None

    def get(self) -> MultiAgentOrchestrator:
        if self._orchestrator is not None:
            return self._orchestrator

        env_path = Path(".env")
        if not os.getenv("GROQ_API_KEY") and env_path.is_file():
            load_api_key(env_path)

        if not os.getenv("GROQ_API_KEY"):
            raise ServiceUnavailableError(
                "Provedor LLM indisponível (GROQ_API_KEY não configurada). "
                "Nenhuma resposta foi inventada."
            )

        try:
            retriever = QdrantRetriever()
        except Exception as exc:
            raise ServiceUnavailableError(
                "Base vetorial Qdrant indisponível no momento. "
                "Nenhuma resposta foi inventada."
            ) from exc

        min_interval = float(os.getenv("VEZO_LLM_MIN_CALL_INTERVAL", "0"))
        llm = GroqLLM(LLMConfig(min_call_interval=min_interval))
        self._retriever = retriever
        self._orchestrator = MultiAgentOrchestrator(
            ResearchAgent(retriever, llm),
            AnalysisPlanningAgent(llm),
            ValidationAgent(llm),
            llm,
            mode="live",
            config={"source": "fastapi"},
        )
        return self._orchestrator

    def close(self) -> None:
        if self._retriever is not None:
            self._retriever.close()
            self._retriever = None
        self._orchestrator = None
