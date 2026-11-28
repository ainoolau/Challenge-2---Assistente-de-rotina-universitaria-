# MEMORY — Memória Técnica, Decisões Arquiteturais e Lições Aprendidas

> Registro vivo de decisões consolidadas, incidentes diagnosticados e armadilhas conhecidas no projeto **Vezo**. Todo agente ou desenvolvedor deve consultar este arquivo antes de alterar retrieval, prompts, modelos, infraestrutura ou contratos.

---

## 1. Decisões de Arquitetura e Produto

### `M-01` — Migração para Embeddings Multilíngues (384d)
- **Contexto:** O modelo inicial `all-MiniLM-L6-v2` (voltado ao inglês) apresentou baixa qualidade de recuperação em consultas em português sobre grades, editais e áudios transcritos.
- **Decisão:** Padronizar `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (384 dimensões, distância `COSINE`) na ingestão, retrieval, benchmark e multiagentes.
- **Armadilha conhecida:** `.env.example` ainda referencia `all-MiniLM-L6-v2` de uma fase anterior — **não reverter** o código para o modelo antigo. Qualquer troca futura de encoder exige recriar toda a coleção `rotina_estudante_multimodal`.

### `M-02` — Limite de Tokens de Saída com `openai/gpt-oss-20b` (Groq)
- **Contexto:** Mesmo com `include_reasoning=False`, o parâmetro `reasoning_effort="low"` consome tokens internos dentro do orçamento de `max_completion_tokens`. Limites de `512` e `1024` causaram truncamento (`finish_reason="length"`) em perguntas como `GS-07`, `GS-08` e `GS-11`.
- **Decisão:** Padronizar **`max_completion_tokens=2048`** nos executores Groq (`zero_shot.py`, `guardrail_rag.py` e `src/agents/llm.py`) e rejeitar qualquer resposta cujo `finish_reason != "stop"`.

### `M-03` — Política de Retries, `User-Agent` (HTTP 403) e Pacing contra Cota (HTTP 429)
- **Incidentes diagnosticados:**
  1. Requisições `urllib.request` com `User-Agent` padrão do Python receberam **HTTP 403** na Groq. Adicionar `User-Agent` explícito (`vezo-benchmark/1.0` e `vezo-multiagents/1.0`) resolveu o problema.
  2. Execuções multiagentes sequenciais dispararam **HTTP 429** por taxa de requisições na Groq.
- **Decisão:** Manter `User-Agent` explícito; **não fazer retries ocultos** que mascarem falhas; aplicar pacing configurável (`--min-call-interval 15` no modo `live`) separando no trace `rate_limit_wait_ms` da latência HTTP real (`latency_ms`).

### `M-04` — Fine-Tuning de Embeddings (Triplet Loss) Pausado
- **Evidência:** Testes preliminares de fine-tuning com Triplet Loss sobre os 162 chunks atuais degradaram o retrieval em comparação ao modelo pré-treinado original, pois os fragmentos de 500 caracteres continham informação incompleta/descontextualizada.
- **Decisão:** **Não** investir em novos experimentos de fine-tuning antes de implementar **Chunking Estrutural + Contextual Retrieval** e reavaliar a base.

### `M-05` — Causa Raiz das Lacunas de Retrieval (`GS-01`, `GS-05`, `GS-06`, `GS-08`, `GS-10`)
- **Diagnóstico:** O fatiamento fixo de `500` caracteres (`overlap=50`) separa linhas de tabelas/calendários, quebra cláusulas de editais e descola o identificador do estudante de sua rotina em `perfis_rotina_forms.txt` (gerando mistura de perfis em `GS-10` e abstenções por falta de contexto em `GS-01/05/06/08`). Além disso, o `paraphrase-multilingual-MiniLM-L12-v2` no SentenceTransformers possui `max_seq_length = 128` tokens reais (truncando silenciosamente o fim de chunks maiores).
- **Resolução (`#80` / `INGESTION_VERSION = "3.0.2"`):** Implementado chunking estrutural por documento (isolamento estrito de perfis/campos em `perfis_rotina_forms.txt`, preservação de linhas de tabelas/calendários e quebra por seções/parágrafos com janela `900`/`160`), cabeçalho contextual compacto (`[Documento: ... | Perfil/Seção/Localização: ...]`, com proteção contra títulos/cláusulas longas) e controle pelo tokenizador real (`MAX_EMBEDDING_TOKENS = 128`).
- **Evidência Antes vs. Depois (25 docs reais):** `Hit@1` subiu de `54,5%` para `63,6%` (+9,1 pp), `MRR` subiu de `0,7197` para `0,7424`, `Hit@3` manteve `90,9%` e `GS-12` (fora de domínio) permaneceu seguro em `0,430` (`< 0,50`). **Ponto de atenção:** `Hit@5` passou de `100%` para `90,9%` (1 query caiu fora do Top-5 com o maior número de chunks granulares <= 128 tokens) — a ser endereçado na próxima etapa de **Reranking Top-10 → Top-3 (`#84`)**.

### `M-06` — Motor de Agenda 100% Determinístico e Sem Escrita Automática
- **Decisão:** Cálculos de intervalo, proteção de sono (padrão `22h–06h` no fuso IANA, incluindo virada de meia-noite e transição de horário de verão/DST), detecção de conflitos pré-existentes (`input_conflicts`) e auditoria (`audit_plan`) pertencem exclusivamente a `src/agents/planning.py`.
- **Regra inegociável:** O LLM **nunca** calcula horários em prosa, **nunca** altera a agenda diretamente (`requires_confirmation=True`) e **nunca** pode anular uma reprovação determinística do `ValidationAgent`.

### `M-07` — Direção Oficial de Produto e Frontend (Alinhada em `19/11/2026`)
- **Decisão:**
  - **Entrega final:** `11/12/2026`.
  - **Backend:** FastAPI (`src/api/`) expondo RAG, multiagentes e **sessões persistentes**.
  - **Frontend:** **PWA responsivo** instalável no celular em **Next.js / React + Tailwind CSS + shadcn/ui** (`frontend/`), com Dashboard (Hoje/Semana/Mês), visualizador de cenário/prioridades/conflitos e chat integrado.
  - **Estética:** limpa e autoral — **proibido** visual genérico de *vibe coding* (gradientes roxo-para-azul, excesso de ícones em bolhas super-arredondadas).
  - **Paleta:** ainda em discussão pela equipe (candidata externa fora do repositório); usar **tokens semânticos CSS** desacoplados para troca trivial posterior.
  - **Integrações externas (`.ics`, Google Calendar):** escopo plus / pós-MVP se sobrar tempo.

---

## 2. Armadilhas Operacionais e Contratos Críticos

| Área | Armadilha / Regra | Como Proceder |
| :--- | :--- | :--- |
| **Python** | Versões `>=3.12` quebram dependências de IA do projeto. | Usar estritamente **Python 3.11.x** (`requires-python = ">=3.11,<3.12"`). |
| **Qdrant: Docker vs. Disco** | `ingestion.py` grava no Qdrant HTTP (`localhost:6333`), mas `retrieval.py` cai para `data/qdrant` se `QDRANT_URL` não estiver definida (e modo local aceita só 1 processo por vez). | Definir `QDRANT_URL=http://localhost:6333` ao usar o container Docker. Nunca rodar ingestão e leitura simultâneas sobre `data/qdrant`. |
| **API do `qdrant-client`** | `client.search(...)` foi removido/depreciado em versões recentes. | Usar sempre `client.query_points(...)`. |
| **Dependência `groq` SDK** | `naive_rag.py` e `guardrail_rag.py` importam o pacote `groq`, que não está listado em `pyproject.toml` nem `requirements.txt`. | Instalar `groq` separadamente para rodar Cenários 3/4. `zero_shot.py` e `src/agents/llm.py` usam apenas `urllib.request`. |
| **Separação de Contratos** | O sistema multiagentes (`src/agents/schemas.py`) e o benchmark (`tests/benchmark_result_schema.json`) têm finalidades distintas. | Não alterar o contrato `1.0.0` do benchmark ao evoluir multiagentes/API; não comparar métricas multiagente (até 5 chunks/refinamento) diretamente com Top-3 simples da Sprint 3. |
| **Guardrails CI / LGPD** | CI bloqueia pesos de modelos (`.bin`, `.pt`, `.pth`, `.gguf`, `.safetensors`, `.onnx`) em todo o repo, e mídias/PDFs/`>10 MB` fora de `data/samples/`. | Nunca versionar pesos, `.env`, `reports/multiagents/` ou arquivos de mídia fora de `data/samples/`. |
| **Gabarito do Golden Set** | `tests/benchmark_llm_rag_queries.json` contém `expected_answer`, `key_facts` e `evidence`. | Scripts de inferência devem ler **somente** `query_id` e `question`. |
| **Tesseract / FFmpeg no Windows** | Instalador do Tesseract traz apenas `eng`; `winget` do FFmpeg pode falhar. | Configurar `TESSERACT_CMD` e `TESSDATA_PREFIX` (com `por.traineddata`) e usar `imageio-ffmpeg` se necessário. |
