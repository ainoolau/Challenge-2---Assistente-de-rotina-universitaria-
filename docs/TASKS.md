# TASKS — Roadmap, Backlog Priorizado e Status do Projeto Vezo

> **Marco Final de Entrega:** `11/12/2026`
> **Branch de Integração:** `develop`
> **Foco Estratégico:** Observabilidade + Evidências Sólidas de RAG/Multiagentes + PWA Polido Fim-a-Fim

---

## 1. Entregas Concluídas (Baseline na `develop`)

### Sprint 2 — Base de Conhecimento, Infra e Retrieval
- [x] `TASK-01`: Curadoria e anonimização LGPD de 25 documentos multimodais em `data/samples/` (`DOC-01`–`DOC-25`).
- [x] `TASK-02`: Infraestrutura local via Docker Compose (`infra/docker-compose.yml`: Qdrant `v1.12.1` + MLflow `v2.19.0`).
- [x] `TASK-03`: Pipeline de extração multimodal (`extractors.py`) e ingestão vetorial (`ingestion.py`, modelo multilíngue 384d).
- [x] `TASK-04`: Documentação inicial da arquitetura do pipeline (`docs/pipeline_arquitetura.md`).
- [x] `TASK-05`: Script executável de retrieval (`scripts/demo_retrieval.py`) e módulo reutilizável (`src/data_pipeline/retrieval.py`).
- [x] Benchmark formal de retrieval (`scripts/evaluate_rag.py` → `Hit@3: 90.9%`, `Hit@5: 100%`, `MRR: 0.7197`, latência média `49.68 ms`).

### Sprint 3 — Benchmark Comparativo LLM vs. RAG
- [x] `TASK-S3-01`: Golden Set oficial (`tests/benchmark_llm_rag_queries.json`, v1.0.0) e contrato JSON Schema (`tests/benchmark_result_schema.json`).
- [x] `TASK-S3-02`: Cenário 1 Zero-Shot (`scripts/scenarios/zero_shot.py`) + execução integral Groq `openai/gpt-oss-20b` (`2048` tokens).
- [x] `TASK-S3-03`: Cenário 3 Naive RAG (`scripts/scenarios/naive_rag.py`) + relatório técnico (`reports/evidencias_cenario3_naive_rag.md`).
- [x] `TASK-S3-04`: Cenário 4 Guardrail RAG (`scripts/scenarios/guardrail_rag.py`, `threshold=0.50`) + relatório técnico (`reports/evidencias_cenario4_guardrail.md`).

### Sistema Multiagentes v1
- [x] `TASK-F3-09`: Contratos Pydantic v2 (`src/agents/schemas.py`).
- [x] `TASK-F3-10`: `ResearchAgent` com gate pré-LLM, decomposição composta, verificação literal de citações e refinamento limitado (`src/agents/research_agent.py`).
- [x] `TASK-F3-11`: `AnalysisPlanningAgent` + motor determinístico de agenda com sono/fuso/DST (`src/agents/planning.py`).
- [x] `TASK-F3-12` / `TASK-F3-13`: `ValidationAgent` (2 níveis) e `MultiAgentOrchestrator` com 1 rodada de correção (`src/agents/validation_agent.py`, `orchestrator.py`).
- [x] `TASK-F3-14`: CLI demonstrável (`scripts/demo_multiagents.py`), documentação (`docs/multiagent_*.md`) e 32 testes automatizados (`tests/test_multiagents.py`).

---

## 2. Prioridades Imediatas (P0 / P1 — Sprint Atual)

Todas as 5 trilhas abaixo estão priorizadas para execução imediata rumo à entrega de `11/12/2026`:

### Trilha A — Governança de Agentes & CI Modular (`chore/agent-setup-and-ci`)
- [x] `A-01` (`P0`): Consolidar documentação base (`docs/PRD.md`, `ARCHITECTURE.md`, `DESIGN.md`, `TASKS.md`, `MEMORY.md`) e atualizar `.agents/rules/AGENTS.md`.
- [ ] `A-02` (`P0`): Criar subagentes especializados em `.agents/agents/` (`orquestrador`, `frontend`, `produto`, `producao`).
- [ ] `A-03` (`P0`): Criar Agent Skills em `.agents/skills/` (`pr-review`, `rag-pipeline`).
- [ ] `A-04` (`P0`): Evoluir `.github/workflows/ci.yml` para esteira modular com matrizes, gate jobs e `$GITHUB_STEP_SUMMARY`.

### Trilha B — Qualidade do RAG & Consolidação do Benchmark (`src/data_pipeline/`, `scripts/scenarios/`)
- [x] `B-01` (`P0`): Implementar **Chunking Estrutural** na ingestão (`#80`, `INGESTION_VERSION = "3.0.2"`):
  - Separar `perfis_rotina_forms.txt` por delimitador de perfil/estudante (eliminando mistura de perfis como em `GS-10`);
  - Preservar linhas completas de tabelas/calendários e cláusulas de editais (atacando lacunas em `GS-01`, `GS-05`, `GS-06`, `GS-08`);
  - Ajustar janela estrutural (`900` chars / `160` overlap) com controle real de tokens (`MAX_EMBEDDING_TOKENS = 128` do MiniLM).
- [x] `B-02` (`P0`): Implementar **Contextual Retrieval** adicionando cabeçalho estruturado (`[Documento: ... | Perfil/Seção/Localização: ...]`) em cada chunk antes de vetorizar (`#80`).
- [ ] `B-03` (`P1`): Implementar **busca em duas etapas com Reranking** (Qdrant Top-10 → Cross-Encoder Reranker → Top-3) e recalibrar o limiar do guardrail.
- [ ] `B-04` (`P1`): Consolidar **`TASK-S3-05`** — reexecutar Cenário 2 (`retrieval_only`) sobre o Golden Set v1.0.0 e gerar relatório comparativo final dos 4 cenários (incluindo impacto antes/depois do chunking estrutural).

### Trilha C — Observabilidade MLOps (`src/mlops/`)
- [ ] `C-01` (`P0`): Criar módulo de rastreamento **MLflow** (`src/mlops/tracker.py`) conectando a `MLFLOW_TRACKING_URI` (`http://localhost:5000`).
- [ ] `C-02` (`P0`): Instrumentar pipeline de ingestão/avaliação (`Hit@1/3/5`, `MRR`, `chunk_count`, parâmetros de chunking e reranking).
- [ ] `C-03` (`P0`): Instrumentar `MultiAgentOrchestrator` registrando por execução: latência total, latência HTTP, `rate_limit_wait_ms`, tokens entrada/saída, número de chamadas LLM, abstenções, correções e status de validação (sem vazar dados sensíveis ou chaves).

### Trilha D — Backend API FastAPI & Sessões Persistentes (`src/api/`)
- [ ] `D-01` (`P0`): Estruturar app FastAPI (`src/api/main.py`) com healthcheck (`/health`), CORS configurável para o PWA e injeção reutilizável de `QdrantRetriever` + `MultiAgentOrchestrator`.
- [ ] `D-02` (`P0`): Implementar persistência leve (SQLite) para **sessões**, histórico de conversas e agenda estruturada do estudante (`schedule_slots`, `study_goals`, `sleep_start`/`sleep_end`, `timezone`).
- [ ] `D-03` (`P0`): Criar endpoints REST:
  - CRUD de sessões e agenda (`/api/v1/sessions`, `/api/v1/sessions/{id}/schedule`);
  - Execução de chat/planejamento (`/api/v1/sessions/{id}/chat`);
  - Confirmação explícita de proposta (`/api/v1/sessions/{id}/schedule/confirm`) revalidando invariantes com `audit_plan`.
- [ ] `D-04` (`P1`): Criar testes automatizados de API (`tests/test_api.py` usando `httpx`/`TestClient` com doubles offline para rodar no CI) e endpoint de ingestão incremental.

### Trilha E — Frontend PWA (`frontend/` — Next.js/React + Tailwind + shadcn/ui)
- [ ] `E-01` (`P0`): Inicializar projeto `frontend/` (Next.js App Router, TypeScript, Tailwind CSS, `shadcn/ui`, `manifest.webmanifest` PWA) com design tokens semânticos desacoplados e estética limpa (sem clichês de *vibe coding*).
- [ ] `E-02` (`P0`): Construir **Dashboard de Rotina (Hoje / Semana / Mês)** + visualizador de cenário do estudante com prioridades da semana e destaque visual para conflitos (`input_conflicts`) e sono protegido.
- [ ] `E-03` (`P0`): Integrar **Chat Assistente** ao dashboard: citações clicáveis exibindo trecho literal/fonte, seção de lacunas/limitações, visual de abstenção segura e card de proposta de agenda com botões **Confirmar** / **Descartar**.
- [ ] `E-04` (`P0`): Conectar seletor de **sessões persistentes** à API FastAPI.
- [ ] `E-05` (`P1`): Aplicar a **paleta oficial do Vezo** nos tokens CSS assim que a equipe consolidar o guia visual definitivo.

---

## 3. Backlog Plus / Pós-MVP (Se sobrar tempo antes de `11/12/2026` ou Fase 2)

- [ ] `P2-01`: Exportação e importação de agenda em formato `.ics`.
- [ ] `P2-02`: Integração com Google Calendar (OAuth + sincronização somente após confirmação).
- [ ] `P2-03`: Novos testes de fine-tuning de embeddings (exclusivamente após validação do chunking estrutural e contextual retrieval).
- [ ] `P2-04`: Importação assistida de grades horárias direto do SIGAA / upload mobile via câmera.
