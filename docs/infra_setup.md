# Infraestrutura Local com Docker Compose (Vezo)

A infraestrutura do **Vezo** (`Qdrant`, `MLflow` e `API FastAPI`) é orquestrada via Docker Compose em `infra/docker-compose.yml`, com rede dedicada (`routine_network`), volumes persistentes e healthchecks.

## Pré-requisitos

- Docker Engine (`>= 24.0`) instalado e ativo
- Docker Compose v2 (`docker compose version`)
- Arquivo `.env` criado a partir de `.env.example` na raiz do projeto (nunca versionado)

## 1. Subir a stack completa (Qdrant + MLflow + API FastAPI)

Execute a partir da raiz do projeto:

```bash
cp .env.example .env
docker compose --env-file .env -f infra/docker-compose.yml up -d --build
```

Para subir apenas os serviços de dados/observabilidade (rodando a API via `uvicorn` local):

```bash
docker compose -f infra/docker-compose.yml up -d qdrant mlflow
```

## 2. Portas, Volumes e Healthchecks

| Serviço | Porta Host | Volume Persistente | Healthcheck |
| :--- | :--- | :--- | :--- |
| `qdrant` (`v1.12.1`) | `127.0.0.1:6333` / `6334` | `routine_qdrant_storage` (`/qdrant/storage`) | TCP `localhost:6333` |
| `mlflow` (`v2.19.0`) | `127.0.0.1:5000` | `routine_mlflow_data` (`/mlflow`) | HTTP `http://localhost:5000/health` |
| `api` (Python `3.11`) | `127.0.0.1:8000` (`API_PORT`) | `routine_api_data` (`/data/vezo.db`) + `routine_hf_cache` | HTTP `http://127.0.0.1:8000/health` |

## 3. Validação da Configuração e Smoke Test

Validar sintaxe do Compose (mesmo check executado no CI):

```bash
docker compose -f infra/docker-compose.yml config --quiet
```

Rodar smoke test ponta a ponta contra a stack ativa (sem expor chaves/tokens):

```bash
python scripts/smoke_e2e.py
```

## 4. Segurança e LGPD

- Todas as portas são vinculadas a `127.0.0.1` no ambiente local.
- `GROQ_API_KEY` e `QDRANT_API_KEY` só entram via `.env` local ou variáveis de ambiente — jamais em `.env.example` ou no `Dockerfile` (`.dockerignore` bloqueia `.env`).
- O container da API executa sob usuário não-root (`vezo`).
