---
name: rag-pipeline
description: >-
  Use this skill whenever modifying multimodal extraction, chunking, embeddings,
  Qdrant ingestion/retrieval, guardrail thresholds, reranking, or RAG evaluation
  and MLflow tracking in the Vezo repository.
---

# Skill: `rag-pipeline` — Engenharia, Qualidade e Avaliação do Pipeline RAG do Vezo

## 1. Quando Usar

Ative esta skill em qualquer tarefa que envolva:
- `src/data_pipeline/extractors.py`, `ingestion.py` ou `retrieval.py`;
- `src/agents/research_agent.py` (gate pré-LLM, decomposição composta, refinamento);
- `scripts/evaluate_rag.py` ou `scripts/scenarios/` (`naive_rag.py`, `guardrail_rag.py`);
- Instrumentação MLflow de retrieval/RAG (`src/mlops/`);
- Experimentos de chunking estrutural, Contextual Retrieval ou reranking.

## 2. Regras Rígidas do Contrato Vetorial

1. **Modelo e Dimensão Padronizados:**
   - Usar exclusivamente `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (**384 dimensões**, distância **COSINE**).
   - **Ignorar** a referência legada `all-MiniLM-L6-v2` presente em `.env.example`.
   - Toda troca de modelo de embedding exige recriação completa da coleção `rotina_estudante_multimodal` e reexecução dos testes de retrieval.
2. **API Qdrant e Contrato de Payload:**
   - Usar sempre `client.query_points(...)` — **nunca** o método obsoleto `client.search(...)`.
   - Preservar os 6 campos obrigatórios de payload em cada ponto: `text`, `source`, `task_type` (`"texto" | "ocr" | "audio"`), `user_id`, `created_at` (ISO 8601 UTC) e `chunk_index` (`int >= 0`), com ID determinístico via `uuid5`.
3. **Qdrant Docker vs. Disco Local:**
   - Ao consultar a coleção populada pelo Docker (`localhost:6333`), **sempre** definir `QDRANT_URL=http://localhost:6333`.
   - No modo local em disco (`data/qdrant`), nunca rodar ingestão e leitura simultaneamente (lock exclusivo por processo).

## 3. Diretrizes de Evolução do RAG (Chunking, Contexto e Reranking)

1. **Chunking Estrutural (Prioridade P0 — resolve `GS-01`, `GS-05`, `GS-06`, `GS-08`, `GS-10`):**
   - **Formulários (`perfis_rotina_forms.txt`):** separar estritamente por delimitador de perfil/estudante — nunca misturar dois alunos no mesmo chunk.
   - **Calendários e Tabelas:** preservar linhas completas mantendo atividade e data juntas.
   - **Editais e Documentos Longos:** quebrar por títulos, cláusulas e parágrafos completos antes de recorrer a janelas fixas (`800–1000` chars com `15–20%` de sobreposição).
2. **Contextual Retrieval & Limite do Tokenizador:**
   - Prefixar cada chunk com metadado legível de origem e seção/perfil, por exemplo:
     `[Documento: edital_residencia_02.pdf | Seção: Frequência e Sanções]`
   - **Verificação de truncamento:** o MiniLM trunca entradas acima de **256 wordpieces** por padrão; ao alterar chunkers, medir a contagem de tokens com o tokenizador do modelo para garantir que informação crítica no final do chunk não seja silenciosamente descartada.
3. **Guardrail Pré-LLM & Reranking em Duas Etapas:**
   - Preservar bloqueio pré-LLM (`top_score < threshold`) com **0 chamadas ao LLM** e mensagem oficial de abstenção.
   - Ao introduzir **Cross-Encoder Reranker** (Qdrant Top-10 → Reranker Top-3), **recalibrar explicitamente o limiar** sobre `GS-01`–`GS-12` (scores de Cross-Encoder têm escala diferente da similaridade de cosseno).
4. **Proibição de Fine-Tuning Prematuro (`docs/MEMORY.md#M-04`):**
   - **Não** executar novos treinos de fine-tuning (Triplet Loss) antes de validar os ganhos do chunking estrutural + Contextual Retrieval.
5. **Anti-Leakage de Gabarito:**
   - Nunca usar `expected_answer`, `key_facts` ou `evidence` de `tests/benchmark_llm_rag_queries.json` durante a ingestão, otimização de chunking ou construção de prompts.

## 4. Protocolo Obrigatório de Validação (Antes/Depois)

Sempre execute esta sequência ao alterar qualquer componente do pipeline RAG:

1. **Subir Qdrant e reindexar (se ingestão/chunking mudou):**
   ```bash
   docker compose -f infra/docker-compose.yml up -d qdrant
   python -m src.data_pipeline.ingestion
   ```
2. **Medir métricas de retrieval (comparando antes vs. depois):**
   ```bash
   python scripts/evaluate_rag.py
   ```
   Registre: `Hit@1`, `Hit@3`, `Hit@5`, `keyword_match_rate_at_3`, `MRR`, `top_score` de `GS-12` (caso negativo) e `avg_latency_ms`.
3. **Registrar no MLflow (quando `src/mlops/` estiver disponível):**
   - Logar parâmetros (`embedding_model`, `chunk_strategy`, `chunk_size`, `overlap`, `top_k`, `reranker`, `threshold`) e métricas acima em `http://localhost:5000`.
4. **Rodar testes automatizados e linters:**
   ```bash
   pytest tests/test_retrieval.py tests/test_benchmark_golden_set.py tests/test_multiagents.py -v
   ruff check .
   ruff format --check .
   mypy src --ignore-missing-imports --no-warn-return-any
   ```
5. **Registrar aprendizados:** atualizar `docs/MEMORY.md` e `docs/TASKS.md` se houver mudança de limiar, estratégia de chunking ou decisão arquitetural.
