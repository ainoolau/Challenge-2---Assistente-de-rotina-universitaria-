# Vezo — Assistente de Rotina e Gestão de Tempo Universitária

Assistente inteligente para universitários em multijornada (aulas, residência/trabalho, pesquisa, projetos e estudo autônomo), combinando **RAG multimodal fundamentado**, **orquestração multiagentes**, **motor determinístico de agenda** (com sono protegido e confirmação explícita) e **observabilidade MLOps**.

## Stack Principal

- **Linguagem & Runtime:** Python `3.11.x` (`>=3.11,<3.12`)
- **Backend & APIs:** FastAPI + Pydantic v2 + SQLite persistente (`src/api/`)
- **Banco Vetorial & MLOps:** Qdrant `v1.12.1` + MLflow `v2.19.0` (`infra/docker-compose.yml`)
- **Processamento Multimodal:** Sentence-Transformers (`paraphrase-multilingual-MiniLM-L12-v2`, 384d `COSINE`), Whisper local (`tiny`, `pt`), PyMuPDF e Tesseract OCR (`por`, `--psm 6`)
- **Frontend PWA (em construção):** Next.js / React + Tailwind CSS + shadcn/ui (`frontend/`)
- **Qualidade & CI:** Pytest, Ruff, MyPy e guardrails LGPD

---

## Bootstrap Rápido com Docker Compose (Stack Integrada — 1 Comando)

Este é o caminho recomendado para subir **Qdrant + MLflow + API FastAPI** juntos, com volumes persistentes e healthchecks.

### 1. Prepare o arquivo `.env` local (sem versionar chaves)

```bash
cp .env.example .env
```

*(No Windows PowerShell: `Copy-Item .env.example .env`.)*

Edite `.env` localmente apenas se quiser habilitar o chat LLM ao vivo (preenchendo `GROQ_API_KEY=...`) ou ajustar `VEZO_CORS_ORIGINS` para outra porta do frontend. **Nunca commite `.env` nem chaves reais.**

### 2. Suba toda a stack com um comando

```bash
docker compose --env-file .env -f infra/docker-compose.yml up -d --build
```

*(Se quiser testar sem `.env`, basta omitir `--env-file .env`: a API sobe normalmente com os valores padrão seguros, apenas mantendo `/chat/query` em modo protegido sem `GROQ_API_KEY`.)*

Serviços disponíveis após os healthchecks ficarem verdes (`docker compose -f infra/docker-compose.yml ps`):

| Serviço | Endereço Local | Finalidade |
| :--- | :--- | :--- |
| **API FastAPI (Vezo)** | `http://localhost:8000` (Swagger em `/docs`) | Sessões persistentes, CRUD `/schedule`, otimização/rebalanceamento e `/chat/query` |
| **Qdrant** | `http://localhost:6333` (UI em `/dashboard`) | Base vetorial multimodal (`rotina_estudante_multimodal`, 384d `COSINE`) |
| **MLflow** | `http://localhost:5000` | Rastreamento de experimentos de retrieval, benchmark e multiagentes |
| **Frontend PWA** *(quando inicializado)* | `http://localhost:3000` | Consome a API via `NEXT_PUBLIC_API_URL=http://localhost:8000` (CORS já liberado) |

### 3. Popule a base vetorial multimodal (primeira execução)

```bash
docker compose -f infra/docker-compose.yml exec api python -m src.data_pipeline.ingestion
```

*(Ou fora do container, com o ambiente virtual ativo e `QDRANT_URL=http://localhost:6333`: `python -m src.data_pipeline.ingestion`.)*

### 4. Smoke Test Ponta a Ponta (sem expor segredos)

Com os containers saudáveis, valide saúde dos 3 serviços, criação de sessão com cookie `HttpOnly`, CRUD `/schedule`, trava de sono protegido (`HTTP 409`) e proposta com confirmação explícita:

```bash
python scripts/smoke_e2e.py
```

Verificação rápida manual via `curl`:

```bash
curl -s http://localhost:8000/health
```

Para encerrar os containers preservando os volumes (`qdrant_storage`, `mlflow_data`, `api_data`, `hf_cache`):

```bash
docker compose -f infra/docker-compose.yml down
```

---

## Como Configurar o Ambiente Local Python (Desenvolvimento e Testes)

### 1. Pré-requisitos

- **Python 3.11.x** (Obrigatório: versões `>=3.12` apresentam incompatibilidade com dependências de IA).
  - **Windows:** `winget install Python.Python.3.11`
- **Docker e Docker Compose v2** (para execução isolada do Qdrant, MLflow e API).
- **Tesseract OCR** (apenas se rodar ingestão de fotos/grades fora do Docker):
  - **Windows:** `winget install UB-Mannheim.TesseractOCR`
  - **Linux (Ubuntu/Debian):** `sudo apt install tesseract-ocr tesseract-ocr-por`
  - **macOS:** `brew install tesseract tesseract-lang`
- **FFmpeg** (apenas se rodar transcrição de áudio fora do Docker):
  - **Windows:** `winget install Gyan.FFmpeg`
  - **Linux:** `sudo apt install ffmpeg`
  - **macOS:** `brew install ffmpeg`

### 2. Instalação e Ambiente Virtual

1. **Clone o repositório e acesse a branch de integração:**

   ```bash
   git clone https://github.com/ainoolau/Challenge-2---Assistente-de-rotina-universitaria-.git
   cd Challenge-2---Assistente-de-rotina-universitaria-
   git checkout develop
   ```

2. **Crie e ative o ambiente virtual:**

   ```bash
   python3.11 -m venv .venv
   source .venv/bin/activate
   ```

   No Windows (PowerShell), use `py -3.11 -m venv .venv` e `.\.venv\Scripts\Activate.ps1`.

3. **Instale as dependências:**

   ```bash
   python -m pip install -r requirements.txt
   python -m pip install "fastapi>=0.110.0" "uvicorn>=0.28.0" "pydantic>=2.6.0" "httpx>=0.27.0" ruff mypy
   ```

4. **Suba apenas os serviços de apoio (Qdrant + MLflow) para rodar a API localmente com reload:**

   ```bash
   docker compose -f infra/docker-compose.yml up -d qdrant mlflow
   uvicorn src.api.main:app --reload --port 8000
   ```

---

## Guias Complementares

- **Arquitetura e Contratos:** [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) · [docs/PRD.md](docs/PRD.md) · [docs/DESIGN.md](docs/DESIGN.md)
- **Infraestrutura Docker:** [docs/infra_setup.md](docs/infra_setup.md)
- **Benchmark Zero-Shot (Cenário 1):** `scripts/scenarios/zero_shot.py` — consulte [docs/zero_shot.md](docs/zero_shot.md)
- **Sistema Multiagentes (CLI):** `python scripts/demo_multiagents.py` — consulte [docs/multiagent_execution.md](docs/multiagent_execution.md) e [docs/multiagent_architecture.md](docs/multiagent_architecture.md)
