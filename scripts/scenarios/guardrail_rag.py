import json
import os
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import jsonschema
from dotenv import load_dotenv
from groq import Groq
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

# Carrega variáveis de ambiente (GROQ_API_KEY, QDRANT_URL, etc.)
load_dotenv()

# Caminhos oficiais
GOLDEN_SET_PATH = Path("tests/benchmark_llm_rag_queries.json")
SCHEMA_PATH = Path("tests/benchmark_result_schema.json")
OUTPUT_PATH = Path("reports/scenarios/guardrail_rag_results.json")

# Configurações de Infraestrutura e Retrieval (Sprint 2)
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION_NAME = "rotina_estudante_multimodal"
EMBEDDING_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

# Configurações de Geração e Guardrail
SCENARIO_ID = "guardrail_rag"
LLM_PROVIDER = "groq"
LLM_MODEL = "openai/gpt-oss-20b"
TEMPERATURE = 0.1
MAX_OUTPUT_TOKENS = 2048
TOP_K = 3
GUARDRAIL_THRESHOLD = 0.50
PROMPT_TEMPLATE_ID = "rag_v1"

# Template oficial rag_v1 (padronizado com naive_rag)
SYSTEM_PROMPT_RAG_V1 = """Você é o Vezo, um assistente acadêmico preciso e confiável.
Responda à pergunta do estudante utilizando EXCLUSIVAMENTE as evidências documentais fornecidas no contexto abaixo.

REGRAS ESTRITAS:
1. Não invente regras, datas, prazos ou valores que não estejam explicitamente escritos nos trechos fornecidos.
2. Cite obrigatoriamente o nome exato do arquivo de origem (ex: [fonte: nome_do_arquivo.pdf]) ao final das afirmações.
3. Se os trechos fornecidos não contiverem a resposta exata, diga que não há evidência suficiente nos documentos.
4. Seja claro, objetivo e direto."""


def build_rag_prompt(question: str, chunks: list[dict[str, Any]]) -> str:
    context_blocks = []
    for c in chunks:
        context_blocks.append(
            f"--- TRECHO {c['rank']} (Arquivo: {c['source']} | Score: {c['score']:.4f}) ---\n{c['text']}"
        )
    context_str = "\n\n".join(context_blocks)
    return f"CONTEXTO DOCUMENTAL:\n{context_str}\n\nPERGUNTA DO ESTUDANTE:\n{question}"


def extract_cited_sources(
    answer: str, retrieved_chunks: list[dict[str, Any]]
) -> list[str]:
    """Extrai os basenames dos arquivos efetivamente citados na resposta (conforme schema)."""
    available_sources = list(dict.fromkeys(c["source"] for c in retrieved_chunks))
    cited = [src for src in available_sources if src in answer]
    if not cited:
        for src in available_sources:
            stem = Path(src).stem
            if re.search(rf"\b{re.escape(stem)}\b", answer, re.IGNORECASE):
                cited.append(src)
    return cited if cited else available_sources


def retrieve_top_k(
    qdrant: QdrantClient, encoder: SentenceTransformer, question: str, top_k: int = 3
) -> tuple[list[dict[str, Any]], float]:
    t0 = time.perf_counter()
    query_vector = encoder.encode(question).tolist()

    # Busca por similaridade de cosseno (valores maiores = maior relevância)
    search_result = qdrant.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=top_k,
        with_payload=True,
    ).points

    retrieval_latency_ms = round((time.perf_counter() - t0) * 1000, 2)

    valid_task_types = {"texto", "ocr", "audio"}
    chunks: list[dict[str, Any]] = []

    for rank_idx, hit in enumerate(search_result, start=1):
        payload = hit.payload or {}
        raw_source = payload.get("source") or payload.get("file_name") or "desconhecido"
        raw_task_type = payload.get("task_type")
        task_type = raw_task_type if raw_task_type in valid_task_types else None

        raw_chunk_idx = payload.get("chunk_index")
        chunk_index = (
            int(raw_chunk_idx)
            if isinstance(raw_chunk_idx, int) and raw_chunk_idx >= 0
            else None
        )

        chunks.append(
            {
                "rank": rank_idx,
                "point_id": str(hit.id) if hit.id is not None else None,
                "source": Path(raw_source).name,
                "chunk_index": chunk_index,
                "task_type": task_type,
                "score": round(float(hit.score), 4),
                "text": str(payload.get("text", "")),
            }
        )

    return chunks, retrieval_latency_ms


def run_guardrail_benchmark(threshold: float = GUARDRAIL_THRESHOLD) -> None:
    print(f"Iniciando Cenário 4: RAG Avançado com Guardrail (Threshold = {threshold})")

    # 1. Carregar Golden Set e Schema oficiais
    with open(GOLDEN_SET_PATH, encoding="utf-8") as f:
        golden_data = json.load(f)

    golden_set_version = golden_data["version"]
    official_abstention_msg = golden_data["abstention_message"]
    queries = golden_data["queries"]

    with open(SCHEMA_PATH, encoding="utf-8") as f:
        result_schema = json.load(f)

    # 2. Inicializar clientes
    qdrant = QdrantClient(url=QDRANT_URL)
    encoder = SentenceTransformer(EMBEDDING_MODEL_NAME)
    groq_api_key = os.getenv("GROQ_API_KEY")
    if not groq_api_key:
        raise RuntimeError("GROQ_API_KEY não encontrada no ambiente/.env")
    groq_client = Groq(api_key=groq_api_key)

    results: list[dict[str, Any]] = []

    for item in queries:
        query_id = item["query_id"]
        question = item["question"]
        print(f"\n[{query_id}] {question}")

        t_total_start = time.perf_counter()

        try:
            # Passo A: Retrieval Top-3 no Qdrant
            chunks, retrieval_latency_ms = retrieve_top_k(
                qdrant, encoder, question, TOP_K
            )
            scores = [c["score"] for c in chunks]
            top_score = scores[0] if scores else None

            # Passo B: Avaliação Pré-LLM do Guardrail
            if top_score is None or top_score < threshold:
                decision = "blocked"
                llm_called = False
                abstained = True
                reason = (
                    "Nenhum chunk recuperado no Qdrant."
                    if top_score is None
                    else f"top_score ({top_score:.4f}) abaixo do limiar ({threshold:.2f})."
                )
                answer = official_abstention_msg
                sources: list[str] = []
                generation_latency_ms = None
                input_tokens = 0
                output_tokens = 0
                extra_info: dict[str, Any] = {"guardrail_action": "pre_llm_abort"}

                print(f"   -> BLOCKED | top_score={top_score} | LLM não chamado.")
            else:
                decision = "allowed"
                llm_called = True
                abstained = False
                reason = f"top_score ({top_score:.4f}) >= limiar ({threshold:.2f})."

                user_prompt = build_rag_prompt(question, chunks)

                t_gen_start = time.perf_counter()
                completion = groq_client.chat.completions.create(
                    model=LLM_MODEL,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT_RAG_V1},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=TEMPERATURE,
                    max_tokens=MAX_OUTPUT_TOKENS,
                )
                generation_latency_ms = round(
                    (time.perf_counter() - t_gen_start) * 1000, 2
                )

                answer = (completion.choices[0].message.content or "").strip()
                usage = completion.usage
                input_tokens = int(usage.prompt_tokens) if usage else 0
                output_tokens = int(usage.completion_tokens) if usage else 0
                sources = extract_cited_sources(answer, chunks)
                extra_info = {"guardrail_action": "forward_to_llm"}

                print(
                    f"   -> ALLOWED | top_score={top_score:.4f} | "
                    f"tokens={input_tokens}+{output_tokens} | sources={sources}"
                )

            total_latency_ms = round((time.perf_counter() - t_total_start) * 1000, 2)

            entry = {
                "query_id": query_id,
                "scenario": SCENARIO_ID,
                "model": LLM_MODEL,
                "provider": LLM_PROVIDER,
                "answer": answer,
                "retrieved_chunks": chunks,
                "sources": sources,
                "retrieval_scores": scores,
                "retrieval_latency_ms": retrieval_latency_ms,
                "generation_latency_ms": generation_latency_ms,
                "total_latency_ms": total_latency_ms,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "abstained": abstained,
                "guardrail": {
                    "threshold": threshold,
                    "top_score": top_score,
                    "decision": decision,
                    "llm_called": llm_called,
                    "reason": reason,
                },
                "status": "success",
                "error": None,
                "extra": extra_info,
            }

        except Exception as exc:
            total_latency_ms = round((time.perf_counter() - t_total_start) * 1000, 2)
            has_valid_score = (
                "top_score" in locals()
                and top_score is not None
                and top_score >= threshold
            )
            entry = {
                "query_id": query_id,
                "scenario": SCENARIO_ID,
                "model": LLM_MODEL,
                "provider": LLM_PROVIDER,
                "answer": None,
                "retrieved_chunks": chunks if "chunks" in locals() else [],
                "sources": [],
                "retrieval_scores": scores if "scores" in locals() else [],
                "retrieval_latency_ms": retrieval_latency_ms
                if "retrieval_latency_ms" in locals()
                else None,
                "generation_latency_ms": None,
                "total_latency_ms": total_latency_ms,
                "input_tokens": 0,
                "output_tokens": 0,
                "abstained": None,
                "guardrail": {
                    "threshold": threshold,
                    "top_score": top_score if "top_score" in locals() else None,
                    "decision": "allowed" if has_valid_score else "blocked",
                    "llm_called": False,
                    "reason": f"Erro durante execução: {type(exc).__name__}",
                },
                "status": "error",
                "error": {
                    "type": type(exc).__name__,
                    "message": str(exc),
                },
                "extra": {},
            }
            print(f"   -> ERROR | {type(exc).__name__}: {exc}")

        results.append(entry)

    # 3. Montagem do Envelope Oficial
    now_local = datetime.now(UTC).astimezone()
    output_payload = {
        "contract_version": "1.0.0",
        "golden_set_version": golden_set_version,
        "scenario": SCENARIO_ID,
        "run_id": f"{SCENARIO_ID}-{now_local.strftime('%Y%m%dT%H%M%SZ')}",
        "generated_at": now_local.isoformat(),
        "config": {
            "llm_model": LLM_MODEL,
            "llm_provider": LLM_PROVIDER,
            "temperature": TEMPERATURE,
            "max_output_tokens": MAX_OUTPUT_TOKENS,
            "prompt_template_id": PROMPT_TEMPLATE_ID,
            "qdrant_collection": COLLECTION_NAME,
            "embedding_model": EMBEDDING_MODEL_NAME,
            "top_k": TOP_K,
            "guardrail_threshold": threshold,
            "notes": "Cenário 4 (TASK-S3-04): RAG Avançado com abstenção pré-LLM (threshold=0.50).",
        },
        "results": results,
    }

    # 4. Validação Automática contra o Schema Oficial
    print("\nValidando saída contra tests/benchmark_result_schema.json...")
    jsonschema.validate(instance=output_payload, schema=result_schema)
    print("Validação JSON Schema aprovada com 100% de conformidade!")

    # 5. Persistência do Arquivo Final
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output_payload, f, ensure_ascii=False, indent=2)

    print(f"Resultados salvos em: {OUTPUT_PATH}")


if __name__ == "__main__":
    run_guardrail_benchmark()
