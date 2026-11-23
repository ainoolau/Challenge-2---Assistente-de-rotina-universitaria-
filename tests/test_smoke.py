"""Smoke tests leves e contratos de bootstrap/infraestrutura (CI sem rede)."""

from __future__ import annotations

from pathlib import Path

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
