"""Testes de integração da API FastAPI + SQLite do Vezo (TASK-F4-02 a F4-05)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.agents.analysis_planning_agent import AnalysisPlanningAgent
from src.agents.demo import SimulatedLLM, SimulatedRetriever
from src.agents.orchestrator import MultiAgentOrchestrator
from src.agents.research_agent import ResearchAgent
from src.agents.validation_agent import ValidationAgent
from src.api.dependencies import SESSION_COOKIE_NAME, ServiceUnavailableError
from src.api.main import create_app


def _make_simulated_orchestrator() -> MultiAgentOrchestrator:
    llm = SimulatedLLM()
    return MultiAgentOrchestrator(
        ResearchAgent(SimulatedRetriever(), llm),
        AnalysisPlanningAgent(llm),
        ValidationAgent(llm),
        llm,
        mode="simulated",
    )


@pytest.fixture
def api_client(tmp_path: Path):
    db_file = tmp_path / "vezo_test.db"
    app = create_app(
        db_path=db_file,
        orchestrator_provider=_make_simulated_orchestrator,
    )
    with TestClient(app) as client:
        yield client, db_file


def _create_session(client: TestClient, **body) -> dict:
    resp = client.post("/sessions", json=body or None)
    assert resp.status_code == 201
    return resp.json()


def test_health_and_openapi_contract(api_client):
    client, _ = api_client
    health = client.get("/health")
    assert health.status_code == 200
    data = health.json()
    assert data["status"] == "ok"
    assert data["db_ok"] is True
    assert "qdrant_ok" in data

    spec = client.get("/openapi.json")
    assert spec.status_code == 200
    paths = spec.json()["paths"]
    for expected in (
        "/health",
        "/sessions",
        "/preferences",
        "/schedule",
        "/schedule/{item_id}",
        "/schedule/optimize",
        "/schedule/reallocate",
        "/schedule/proposals/{proposal_id}/confirm",
        "/schedule/proposals/{proposal_id}/reject",
        "/chat/query",
        "/chat/history",
    ):
        assert expected in paths


def test_health_probes_qdrant_connectivity(api_client, monkeypatch):
    import urllib.error
    from contextlib import contextmanager

    class FakeResp:
        status = 200

    seen_headers: list[dict[str, str]] = []

    @contextmanager
    def ok_urlopen(req, timeout=2.0):
        assert req.full_url == "http://qdrant.internal:6333/collections"
        seen_headers.append({k.lower(): v for k, v in req.header_items()})
        yield FakeResp()

    def unauthorized_urlopen(req, timeout=2.0):
        raise urllib.error.HTTPError(
            req.full_url, 401, "Unauthorized", hdrs=None, fp=None
        )

    def forbidden_urlopen(req, timeout=2.0):
        raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", hdrs=None, fp=None)

    def failing_urlopen(_req, timeout=2.0):
        raise OSError("connection refused")

    client, _ = api_client
    monkeypatch.setenv("QDRANT_URL", "http://qdrant.internal:6333")
    monkeypatch.setenv("QDRANT_API_KEY", "valid-test-key")

    monkeypatch.setattr("src.api.main.urllib.request.urlopen", ok_urlopen)
    ok_data = client.get("/health").json()
    assert ok_data["qdrant_configured"] is True
    assert ok_data["qdrant_ok"] is True
    assert seen_headers[-1].get("api-key") == "valid-test-key"

    # Chave inválida (401) -> qdrant_ok=False
    monkeypatch.setattr("src.api.main.urllib.request.urlopen", unauthorized_urlopen)
    unauth_data = client.get("/health").json()
    assert unauth_data["qdrant_configured"] is True
    assert unauth_data["qdrant_ok"] is False

    # Sem permissão (403) -> qdrant_ok=False
    monkeypatch.setattr("src.api.main.urllib.request.urlopen", forbidden_urlopen)
    forbid_data = client.get("/health").json()
    assert forbid_data["qdrant_configured"] is True
    assert forbid_data["qdrant_ok"] is False

    # Indisponibilidade de rede -> qdrant_ok=False
    monkeypatch.setattr("src.api.main.urllib.request.urlopen", failing_urlopen)
    down_data = client.get("/health").json()
    assert down_data["qdrant_configured"] is True
    assert down_data["qdrant_ok"] is False


def test_session_cookie_header_isolation_and_persistence(tmp_path: Path):
    db_file = tmp_path / "persist.db"
    app1 = create_app(
        db_path=db_file,
        orchestrator_provider=_make_simulated_orchestrator,
    )

    with TestClient(app1) as client_a, TestClient(app1) as client_b:
        # Sem sessão -> 401
        assert client_a.get("/schedule").status_code == 401
        assert (
            client_a.get(
                "/schedule", headers={"X-Session-Token": "token-invalido"}
            ).status_code
            == 401
        )

        # Cria sessão A (cookie HttpOnly emitido)
        resp_a = client_a.post(
            "/sessions",
            json={"timezone": "America/Sao_Paulo", "consent_accepted": True},
        )
        assert resp_a.status_code == 201
        set_cookie = resp_a.headers.get("set-cookie", "").lower()
        assert f"{SESSION_COOKIE_NAME}=" in set_cookie
        assert "httponly" in set_cookie
        assert "samesite=lax" in set_cookie
        token_a = resp_a.json()["session_token"]
        assert token_a

        # Token bruto NÃO pode estar persistido no banco SQLite (somente hash).
        conn = sqlite3.connect(db_file)
        try:
            stored_hashes = [
                row[0] for row in conn.execute("SELECT token_hash FROM sessions")
            ]
        finally:
            conn.close()
        assert token_a not in stored_hashes

        # Cria item na sessão A via cookie.
        item_resp = client_a.post(
            "/schedule",
            json={
                "start": "2026-11-17T08:00:00-03:00",
                "end": "2026-11-17T10:00:00-03:00",
                "label": "Aula de Econometria",
                "kind": "class",
                "fixed": True,
            },
        )
        assert item_resp.status_code == 201
        item_id = item_resp.json()["item_id"]

        # Sessão B não pode ver nem alterar itens da sessão A.
        _create_session(client_b)
        assert client_b.get("/schedule").json()["items"] == []
        assert (
            client_b.patch(f"/schedule/{item_id}", json={"label": "Hack"}).status_code
            == 404
        )
        assert client_b.delete(f"/schedule/{item_id}").status_code == 404

    # Reinício da aplicação sobre o mesmo SQLite preserva dados (acesso via X-Session-Token).
    app2 = create_app(
        db_path=db_file,
        orchestrator_provider=_make_simulated_orchestrator,
    )
    with TestClient(app2) as restarted:
        sched = restarted.get("/schedule", headers={"X-Session-Token": token_a})
        assert sched.status_code == 200
        assert len(sched.json()["items"]) == 1
        assert sched.json()["items"][0]["label"] == "Aula de Econometria"
        assert sched.json()["preferences"]["consent_accepted"] is True


def test_schedule_crud_timezone_and_protected_sleep_fixed_guards(api_client):
    client, _ = api_client
    _create_session(client, timezone="America/Sao_Paulo", buffer_minutes=15)

    # Preferência com fuso inválido -> 422.
    bad_tz = client.put("/preferences", json={"timezone": "Invalid/Timezone"})
    assert bad_tz.status_code == 422

    # Preferência válida atualiza buffer e sono.
    ok_pref = client.put(
        "/preferences",
        json={"buffer_minutes": 10, "sleep_start": "22:30:00", "sleep_end": "06:30:00"},
    )
    assert ok_pref.status_code == 200
    assert ok_pref.json()["buffer_minutes"] == 10

    # Data sem fuso explícito -> 422.
    naive = client.post(
        "/schedule",
        json={
            "start": "2026-11-17T08:00:00",
            "end": "2026-11-17T10:00:00",
            "label": "Sem fuso",
            "kind": "class",
        },
    )
    assert naive.status_code == 422

    # Bloqueio de criação dentro do sono protegido (22:30-06:30) -> 409.
    in_sleep = client.post(
        "/schedule",
        json={
            "start": "2026-11-17T23:00:00-03:00",
            "end": "2026-11-18T00:00:00-03:00",
            "label": "Estudo na madrugada",
            "kind": "study",
            "fixed": False,
        },
    )
    assert in_sleep.status_code == 409

    # Bloqueio de criação direta de item kind="sleep" -> 409.
    raw_sleep = client.post(
        "/schedule",
        json={
            "start": "2026-11-17T13:00:00-03:00",
            "end": "2026-11-17T14:00:00-03:00",
            "label": "Soneca",
            "kind": "sleep",
        },
    )
    assert raw_sleep.status_code == 409

    # Cria compromisso fixo e item flexível.
    fixed_item = client.post(
        "/schedule",
        json={
            "start": "2026-11-17T08:00:00-03:00",
            "end": "2026-11-17T12:00:00-03:00",
            "label": "Residência IA",
            "kind": "work",
            "fixed": True,
        },
    ).json()
    flex_item = client.post(
        "/schedule",
        json={
            "start": "2026-11-17T14:00:00-03:00",
            "end": "2026-11-17T15:00:00-03:00",
            "label": "Leitura",
            "kind": "study",
            "fixed": False,
            "goal_id": "leitura-1",
        },
    ).json()

    # Compromisso fixo bloqueado contra edição/remoção direta -> 409.
    assert (
        client.patch(
            f"/schedule/{fixed_item['item_id']}", json={"label": "Alterado"}
        ).status_code
        == 409
    )
    assert client.delete(f"/schedule/{fixed_item['item_id']}").status_code == 409

    # Item flexível permite edição (desde que não invada sono) e remoção.
    assert (
        client.patch(
            f"/schedule/{flex_item['item_id']}",
            json={
                "start": "2026-11-17T23:00:00-03:00",
                "end": "2026-11-17T23:45:00-03:00",
            },
        ).status_code
        == 409
    )
    patched = client.patch(
        f"/schedule/{flex_item['item_id']}", json={"label": "Leitura revisada"}
    )
    assert patched.status_code == 200
    assert patched.json()["label"] == "Leitura revisada"

    # GET /schedule com horizonte retorna janelas livres reais.
    listed = client.get(
        "/schedule",
        params={
            "horizon_start": "2026-11-17T06:30:00-03:00",
            "horizon_end": "2026-11-17T22:30:00-03:00",
        },
    )
    assert listed.status_code == 200
    assert len(listed.json()["free_windows"]) >= 2

    assert client.delete(f"/schedule/{flex_item['item_id']}").status_code == 204


def test_optimize_reallocate_confirm_reject_and_version_conflict(api_client):
    client, _ = api_client
    _create_session(client, timezone="America/Sao_Paulo", buffer_minutes=15)

    # Cadastra compromisso fixo de trabalho.
    fixed = client.post(
        "/schedule",
        json={
            "start": "2026-11-17T08:00:00-03:00",
            "end": "2026-11-17T12:00:00-03:00",
            "label": "CLT",
            "kind": "work",
            "fixed": True,
        },
    ).json()

    # 1. Otimização cria proposta pendente SEM alterar agenda.
    opt_resp = client.post(
        "/schedule/optimize",
        json={
            "horizon": {
                "start": "2026-11-17T06:00:00-03:00",
                "end": "2026-11-18T22:00:00-03:00",
            },
            "study_goals": [
                {
                    "goal_id": "econ",
                    "title": "Estudo de Econometria",
                    "duration_minutes": 120,
                    "deadline": "2026-11-18T20:00:00-03:00",
                    "priority": 5,
                }
            ],
        },
    )
    assert opt_resp.status_code == 200
    opt_data = opt_resp.json()
    assert opt_data["status"] == "pending"
    assert opt_data["requires_confirmation"] is True
    assert len(opt_data["planning"]["proposed_blocks"]) >= 2
    assert len(client.get("/schedule").json()["items"]) == 1  # ainda só o fixo!

    # 2. Rejeição preserva agenda intacta e bloqueia reconfirmação.
    rej = client.post(f"/schedule/proposals/{opt_data['proposal_id']}/reject")
    assert rej.status_code == 200
    assert rej.json()["status"] == "rejected"
    assert len(client.get("/schedule").json()["items"]) == 1
    assert (
        client.post(
            f"/schedule/proposals/{opt_data['proposal_id']}/confirm"
        ).status_code
        == 409
    )

    # 3. Gera duas propostas na mesma versão: confirma uma e valida conflito de versão na outra.
    p1 = client.post(
        "/schedule/optimize",
        json={
            "horizon": {
                "start": "2026-11-17T06:00:00-03:00",
                "end": "2026-11-18T22:00:00-03:00",
            },
            "study_goals": [
                {
                    "goal_id": "econ",
                    "title": "Estudo de Econometria",
                    "duration_minutes": 120,
                    "deadline": "2026-11-18T20:00:00-03:00",
                    "priority": 5,
                }
            ],
        },
    ).json()
    p2 = client.post(
        "/schedule/optimize",
        json={
            "horizon": {
                "start": "2026-11-17T06:00:00-03:00",
                "end": "2026-11-18T22:00:00-03:00",
            },
            "study_goals": [
                {
                    "goal_id": "calc",
                    "title": "Lista de Cálculo",
                    "duration_minutes": 60,
                    "deadline": "2026-11-18T20:00:00-03:00",
                    "priority": 3,
                }
            ],
        },
    ).json()

    conf1 = client.post(f"/schedule/proposals/{p1['proposal_id']}/confirm")
    assert conf1.status_code == 200
    assert conf1.json()["status"] == "confirmed"

    # p2 ficou defasada (base_version != schedule_version atual) -> 409 Conflict!
    conf2 = client.post(f"/schedule/proposals/{p2['proposal_id']}/confirm")
    assert conf2.status_code == 409
    assert "versão" in conf2.json()["detail"].lower()

    # 4. Realocação diante de imprevisto atingindo o primeiro bloco flexível confirmado.
    current_items = client.get("/schedule").json()["items"]
    study_items = [i for i in current_items if not i["fixed"]]
    assert len(study_items) >= 2
    first_study = study_items[0]

    realloc = client.post(
        "/schedule/reallocate",
        json={
            "horizon": {
                "start": "2026-11-17T06:00:00-03:00",
                "end": "2026-11-18T22:00:00-03:00",
            },
            "disruptions": [
                {
                    "start": first_study["start"],
                    "end": first_study["end"],
                    "label": "Reunião inesperada",
                    "kind": "work",
                }
            ],
            "disruption_note": "Reunião emergencial da residência",
        },
    )
    assert realloc.status_code == 200
    rdata = realloc.json()
    assert rdata["requires_confirmation"] is True
    assert rdata["rebalance"]["diff"]["moved"]
    assert rdata["rebalance"]["diff"]["kept"]

    # Antes de confirmar, blocos originais permanecem intactos.
    assert client.get("/schedule").json()["items"] == current_items

    # Após confirmar, compromisso fixo continua intacto e blocos flexíveis são atualizados.
    conf_realloc = client.post(f"/schedule/proposals/{rdata['proposal_id']}/confirm")
    assert conf_realloc.status_code == 200
    after_items = client.get("/schedule").json()["items"]
    fixed_after = [i for i in after_items if i["item_id"] == fixed["item_id"]]
    assert len(fixed_after) == 1
    assert fixed_after[0]["start"] == fixed["start"]
    assert fixed_after[0]["end"] == fixed["end"]


def test_chat_query_documental_abstention_planning_and_unavailable(tmp_path: Path):
    db_file = tmp_path / "chat.db"
    app = create_app(
        db_path=db_file,
        orchestrator_provider=_make_simulated_orchestrator,
    )
    with TestClient(app) as client:
        _create_session(client)

        # 1. Consulta documental fundamentada com citações tipadas.
        doc = client.post(
            "/chat/query",
            json={"question": "Qual é a frequência mínima exigida na residência?"},
        )
        assert doc.status_code == 200
        doc_json = doc.json()
        assert doc_json["status"] == "completed"
        assert doc_json["abstained"] is False
        assert doc_json["citations"]
        assert doc_json["citations"][0]["source_id"] == "C1"
        assert doc_json["proposal_id"] is None

        # 2. Fora de domínio -> abstenção segura sem LLM.
        ood = client.post(
            "/chat/query",
            json={
                "question": "Qual é a nota de corte do vestibular de Medicina da UnB?"
            },
        )
        assert ood.status_code == 200
        ood_json = ood.json()
        assert ood_json["status"] == "abstained"
        assert ood_json["abstained"] is True
        assert ood_json["llm_calls"] == 0
        assert ood_json["citations"] == []

        # 3. Chat com planejamento cria proposta pendente (não altera agenda sem confirmar).
        plan_chat = client.post(
            "/chat/query",
            json={
                "question": "Quando é a aula de Econometria e como encaixar estudos?",
                "horizon": {
                    "start": "2026-11-17T06:00:00-03:00",
                    "end": "2026-11-18T22:00:00-03:00",
                },
                "study_goals": [
                    {
                        "goal_id": "econ-chat",
                        "title": "Estudo de Econometria",
                        "duration_minutes": 60,
                        "deadline": "2026-11-18T20:00:00-03:00",
                        "priority": 4,
                    }
                ],
            },
        )
        assert plan_chat.status_code == 200
        pc = plan_chat.json()
        assert pc["requires_confirmation"] is True
        assert pc["planning"] is not None
        assert pc["proposal_id"] is not None
        assert client.get("/schedule").json()["items"] == []

        # Confirma proposta gerada no chat -> grava na agenda!
        confirm_chat = client.post(f"/schedule/proposals/{pc['proposal_id']}/confirm")
        assert confirm_chat.status_code == 200
        assert len(client.get("/schedule").json()["items"]) == 1

        # Histórico de chat persistido na sessão.
        history = client.get("/chat/history")
        assert history.status_code == 200
        assert len(history.json()) == 6  # 3 perguntas + 3 respostas

    # 4. Indisponibilidade de Groq/Qdrant -> 503 sem inventar resposta.
    def _unavailable_provider():
        raise ServiceUnavailableError(
            "Provedor LLM indisponível. Nenhuma resposta foi inventada."
        )

    app_down = create_app(
        db_path=tmp_path / "chat_down.db",
        orchestrator_provider=_unavailable_provider,
    )
    with TestClient(app_down) as client_down:
        _create_session(client_down)
        down = client_down.post(
            "/chat/query",
            json={"question": "Qual é a frequência mínima exigida na residência?"},
        )
        assert down.status_code == 503
        assert "indisponível" in down.json()["detail"].lower()


def test_private_ingestion_isolates_same_filename(tmp_path):
    from qdrant_client import QdrantClient

    from src.data_pipeline.ingestion import ingest_files
    from src.data_pipeline.retrieval import search

    class Embedder:
        def encode(self, sentences, **kwargs):
            return [[1.0] + [0.0] * 383 for _ in sentences]

    client = QdrantClient(":memory:")
    model = Embedder()
    document = tmp_path / "a.txt"
    for session, content in [
        ("A", "Documento secreto da primeira sessão."),
        ("B", "Documento secreto da segunda sessão."),
    ]:
        document.write_text(content, encoding="utf-8")
        summary = ingest_files(
            [document],
            collection_name="vezo_user_private",
            user_id=session,
            corpus_scope="private",
            target_collection_scope="private",
            client=client,
            embedder=model,
        )
        assert summary.processed_files == 1
    hits_a = search(
        client, model, "documento", collection="vezo_user_private", user_id="A"
    )
    hits_b = search(
        client, model, "documento", collection="vezo_user_private", user_id="B"
    )
    assert len(hits_a) == len(hits_b) == 1
    assert "primeira" in hits_a[0].text
    assert "segunda" in hits_b[0].text
    client.close()


def test_document_upload_rejects_invalid_and_oversized(api_client):
    client, _ = api_client
    _create_session(client)
    assert (
        client.post(
            "/documents/upload", files={"file": ("bad.exe", b"data")}
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/documents/upload",
            files={"file": ("big.txt", b"x" * (10 * 1024 * 1024 + 1))},
        ).status_code
        == 413
    )
    assert (
        client.post("/documents/upload", files={"file": ("empty.txt", b"")}).status_code
        == 400
    )


def test_upload_chat_isolation_and_demo_end_to_end(tmp_path, monkeypatch):
    from qdrant_client import QdrantClient, models

    from src.data_pipeline import retrieval

    class Embedder:
        def encode(self, sentences, **kwargs):
            return [[1.0] + [0.0] * 383 for _ in sentences]

    class SharedClient:
        def __init__(self, client):
            self.client = client

        def __getattr__(self, key):
            return getattr(self.client, key)

        def close(self):
            pass

    db = QdrantClient(":memory:")
    db.create_collection(
        "rotina_estudante_multimodal",
        vectors_config=models.VectorParams(size=384, distance=models.Distance.COSINE),
    )
    db.upsert(
        "rotina_estudante_multimodal",
        [
            models.PointStruct(
                id=1,
                vector=[1.0] + [0.0] * 383,
                payload={
                    "source": "demo.txt",
                    "text": "Documento institucional da residência.",
                    "user_id": "demo",
                    "task_type": "texto",
                    "chunk_index": 0,
                },
            )
        ],
    )
    monkeypatch.setenv("GROQ_API_KEY", "test-only")
    monkeypatch.setattr(
        retrieval, "get_client", lambda *args, **kwargs: SharedClient(db)
    )
    monkeypatch.setattr(retrieval, "load_embedder", lambda: Embedder())
    llms = []

    def make_llm(*args):
        llm = SimulatedLLM()
        llms.append(llm)
        return llm

    monkeypatch.setattr("src.api.dependencies.GroqLLM", make_llm)
    app = create_app(db_path=tmp_path / "test.db")
    with TestClient(app) as a, TestClient(app) as b:
        _create_session(a)
        _create_session(b)
        empty = a.post(
            "/chat/query", json={"question": "Qual é o prazo?", "scope": "private"}
        )
        assert empty.status_code == 200 and empty.json()["abstained"]
        assert empty.json()["llm_calls"] == 0 and llms[-1].calls == []
        for client, text in [
            (
                a,
                "O prazo exclusivo da sessão A é segunda-feira. CPF 123.456.789-09 email teste@example.com telefone (11) 99999-8888.",
            ),
            (b, "O prazo exclusivo da sessão B é sexta-feira."),
        ]:
            response = client.post(
                "/documents/upload",
                files={"file": ("prazo.txt", text.encode(), "text/plain")},
            )
            assert response.status_code == 201, response.text
            if client is a:
                empty_b = b.post(
                    "/chat/query",
                    json={"question": "Qual é o prazo?", "scope": "private"},
                )
                assert empty_b.status_code == 200 and empty_b.json()["abstained"]
                assert empty_b.json()["llm_calls"] == 0 and llms[-1].calls == []
                assert b.get("/documents").json() == []
                points, _ = db.scroll("vezo_user_private", with_payload=True)
                payload_text = str(points[0].payload["text"])
                for secret in (
                    "123.456.789-09",
                    "teste@example.com",
                    "(11) 99999-8888",
                ):
                    assert secret not in payload_text
                assert (
                    "[CPF_REMOVIDO]" in payload_text
                    and "[EMAIL_REMOVIDO]" in payload_text
                    and "[TELEFONE_REMOVIDO]" in payload_text
                )
        assert [x["filename"] for x in a.get("/documents").json()] == ["prazo.txt"]
        for client, expected, forbidden in [
            (a, "segunda-feira", "sexta-feira"),
            (b, "sexta-feira", "segunda-feira"),
        ]:
            response = client.post(
                "/chat/query", json={"question": "Qual é o prazo?", "scope": "private"}
            )
            assert response.status_code == 200, response.text
            result = response.json()
            assert expected in result["answer"] and forbidden not in result["answer"]
            assert "[C1: prazo.txt]" in result["answer"]
        demo = a.post(
            "/chat/query", json={"question": "Qual é a informação?", "scope": "demo"}
        )
        assert demo.status_code == 200, demo.text
        assert "[C1: demo.txt]" in demo.json()["answer"]
        assert "institucional" in demo.json()["answer"]
    db.close()


def test_qdrant_local_does_not_create_directory_on_read(tmp_path):
    from src.data_pipeline.retrieval import get_client

    path = tmp_path / "new-qdrant"
    with pytest.raises(FileNotFoundError):
        get_client(path)
    assert not path.exists()
    client = get_client(path, create_if_missing=True)
    client.close()
    assert path.is_dir()
