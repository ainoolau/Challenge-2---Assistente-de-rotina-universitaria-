"""Smoke tests leves e contratos de bootstrap/infraestrutura (CI sem rede)."""

from __future__ import annotations

import email.message
import io
import json
import urllib.request
from pathlib import Path
from typing import Any

import pytest

from scripts.smoke_e2e import (
    _has_httponly_cookie,
    _resolve_default_api_url,
    run_smoke,
)

ROOT = Path(__file__).resolve().parents[1]


def test_smoke() -> None:
    assert True


def test_docker_bootstrap_contracts() -> None:
    compose = (ROOT / "infra" / "docker-compose.yml").read_text(encoding="utf-8")
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")

    # Serviços integrados, healthchecks e volumes persistentes no Compose
    for required in (
        "qdrant:",
        "mlflow:",
        "api:",
        "VEZO_DB_PATH: /data/vezo.db",
        "QDRANT_URL: http://qdrant:6333",
        "MLFLOW_TRACKING_URI: http://mlflow:5000",
        "VEZO_CORS_ORIGINS:",
        "api_data:",
        "healthcheck:",
    ):
        assert required in compose, f"Esperado '{required}' em infra/docker-compose.yml"

    # Dockerfile usa Python 3.11, usuário não-root e expõe FastAPI
    assert "FROM python:3.11-slim" in dockerfile
    assert "uvicorn src.api.main:app" in dockerfile
    assert "USER vezo" in dockerfile

    # .dockerignore protege segredos e bancos locais
    assert ".env" in dockerignore
    assert "*.db" in dockerignore

    # .env.example usa modelo multilíngue (M-01), configura CORS/PWA e não expõe chaves
    assert "paraphrase-multilingual-MiniLM-L12-v2" in env_example
    assert "all-MiniLM-L6-v2" not in env_example
    assert "VEZO_CORS_ORIGINS=" in env_example
    assert "NEXT_PUBLIC_API_URL=" in env_example
    assert "gsk_" not in env_example


def test_smoke_e2e_httponly_cookie_validation() -> None:
    assert _has_httponly_cookie(["vezo_session=abc123; HttpOnly; Path=/; SameSite=lax"])
    assert _has_httponly_cookie(["vezo_session=abc123; httponly; Path=/"])
    assert not _has_httponly_cookie(["vezo_session=abc123; Path=/; SameSite=lax"])
    assert not _has_httponly_cookie(["other_cookie=abc123; HttpOnly; Path=/"])
    assert not _has_httponly_cookie([])


def test_smoke_e2e_resolves_custom_api_port(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("API_PORT=8123\nGROQ_API_KEY=ignored\n", encoding="utf-8")

    monkeypatch.delenv("API_PORT", raising=False)
    assert _resolve_default_api_url(env_file=env_file) == "http://localhost:8123"
    assert _resolve_default_api_url(env_file=tmp_path / "missing.env") == (
        "http://localhost:8000"
    )

    monkeypatch.setenv("API_PORT", "9001")
    assert _resolve_default_api_url(env_file=env_file) == "http://localhost:9001"


class _InMemoryHTTPResponse:
    """Resposta compatível com `urllib.request` e `http.cookiejar` sem abrir sockets."""

    def __init__(
        self,
        url: str,
        status: int,
        payload: dict[str, Any],
        *,
        set_cookie: str | None = None,
    ) -> None:
        self.url = url
        self.status = status
        self.code = status
        self.msg = "OK"
        self._body = io.BytesIO(json.dumps(payload).encode("utf-8"))
        self.headers = email.message.Message()
        self.headers["Content-Type"] = "application/json"
        if set_cookie:
            self.headers["Set-Cookie"] = set_cookie

    def info(self) -> email.message.Message:
        return self.headers

    def geturl(self) -> str:
        return self.url

    def read(self) -> bytes:
        return self._body.read()

    def close(self) -> None:
        self._body.close()

    def __enter__(self) -> _InMemoryHTTPResponse:
        return self

    def __exit__(self, *_args: Any) -> None:
        self.close()


def _install_fake_stack(
    monkeypatch: pytest.MonkeyPatch,
    *,
    include_httponly: bool = True,
    api_qdrant_ok: bool = True,
) -> None:
    """Substitui o transporte HTTP de `smoke_e2e` em memória preservando `CookieJar`."""

    class FakeHTTPHandler(urllib.request.BaseHandler):
        def http_open(self, req: urllib.request.Request) -> Any:
            url = req.full_url
            method = req.get_method()
            raw = req.data.decode("utf-8") if isinstance(req.data, bytes) else ""
            body = json.loads(raw) if raw else {}

            if method == "GET" and url.endswith("/readyz"):
                return _InMemoryHTTPResponse(url, 200, {"status": "ready"})
            if method == "GET" and url.endswith("/health"):
                return _InMemoryHTTPResponse(
                    url,
                    200,
                    {
                        "status": "ok",
                        "db_ok": True,
                        "qdrant_configured": True,
                        "qdrant_ok": api_qdrant_ok,
                        "llm_configured": False,
                    },
                )
            if method == "POST" and url.endswith("/sessions"):
                cookie = (
                    "vezo_session=fake-token; HttpOnly; Path=/; SameSite=lax"
                    if include_httponly
                    else "vezo_session=fake-token; Path=/; SameSite=lax"
                )
                return _InMemoryHTTPResponse(
                    url, 201, {"session_id": "sess-1"}, set_cookie=cookie
                )
            if method == "GET" and url.endswith("/sessions/me"):
                return _InMemoryHTTPResponse(url, 200, {"session_id": "sess-1"})
            if method == "POST" and url.endswith("/schedule"):
                if str(body.get("start", "")).startswith("2026-12-01T23:"):
                    return _InMemoryHTTPResponse(url, 409, {"detail": "sono protegido"})
                return _InMemoryHTTPResponse(url, 201, {"item_id": "itm-1"})
            if method == "POST" and url.endswith("/schedule/optimize"):
                return _InMemoryHTTPResponse(
                    url,
                    200,
                    {"proposal_id": "prop-1", "requires_confirmation": True},
                )
            if method == "POST" and url.endswith("/schedule/proposals/prop-1/reject"):
                return _InMemoryHTTPResponse(
                    url, 200, {"proposal_id": "prop-1", "status": "rejected"}
                )
            return _InMemoryHTTPResponse(url, 404, {"detail": "not found"})

    def fake_build_opener(*handlers: Any) -> urllib.request.OpenerDirector:
        opener = urllib.request.OpenerDirector()
        opener.add_handler(FakeHTTPHandler())
        for handler in handlers:
            opener.add_handler(handler)
        return opener

    monkeypatch.setattr(
        "scripts.smoke_e2e.urllib.request.build_opener", fake_build_opener
    )
    monkeypatch.setattr(
        "scripts.smoke_e2e._check_http_ok", lambda _url, timeout=5.0: True
    )


def test_smoke_e2e_checks_httponly_and_api_qdrant_connectivity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 1. Cenário saudável: HttpOnly presente e API conectada ao Qdrant -> PASS (0)
    _install_fake_stack(monkeypatch, include_httponly=True, api_qdrant_ok=True)
    assert (
        run_smoke(
            api_url="http://api.local:8000", qdrant_url="http://qdrant.local:6333"
        )
        == 0
    )

    # 2. Regressão de segurança: Set-Cookie sem HttpOnly -> FAIL (1)
    _install_fake_stack(monkeypatch, include_httponly=False, api_qdrant_ok=True)
    assert (
        run_smoke(
            api_url="http://api.local:8000", qdrant_url="http://qdrant.local:6333"
        )
        == 1
    )

    # 3. Qdrant /readyz acessível externamente, mas API com QDRANT_URL incorreta -> FAIL (1)
    _install_fake_stack(monkeypatch, include_httponly=True, api_qdrant_ok=False)
    assert (
        run_smoke(
            api_url="http://api.local:8000", qdrant_url="http://qdrant.local:6333"
        )
        == 1
    )
