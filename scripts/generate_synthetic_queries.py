from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from groq import Groq, RateLimitError
from pydantic import BaseModel, Field
from qdrant_client import QdrantClient

# Configurações do Qdrant e Groq
COLLECTION_NAME = "rotina_estudante_multimodal"
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))

# Modelo padrão estável na Groq com fallback configurável via variável de ambiente
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

OUTPUT_DIR = Path("data/finetuning")
OUTPUT_FILE = OUTPUT_DIR / "train_pairs.json"
SCROLL_BATCH_SIZE = 64


class QueryPair(BaseModel):
    formal_query: str = Field(
        description="Pergunta técnica, formal ou acadêmica respondida estritamente pelo texto."
    )
    colloquial_query: str = Field(
        description="Pergunta natural, coloquial ou em tom de dúvida de estudante respondida pelo texto."
    )


def extract_queries_with_groq(
    client: Groq, text: str, max_retries: int = 3
) -> QueryPair | None:
    system_prompt = (
        "Você é um especialista em geração de dados sintéticos para fine-tuning de embeddings de busca vetorial.\n"
        "Com base unicamente no trecho de texto fornecido, gere duas perguntas em português brasileiro que possam ser "
        "respondidas por esse fragmento:\n"
        "1. formal_query: Pergunta precisa, formal e técnica (estilo busca acadêmica/edital/documentação).\n"
        "2. colloquial_query: Pergunta natural, espontânea, como um estudante com dúvida perguntaria no dia a dia.\n"
        "Responda estritamente no esquema JSON solicitado."
    )

    prompt = f'Trecho:\n"""\n{text}\n"""'

    for attempt in range(max_retries):
        try:
            completion = client.chat.completions.create(
                model=GROQ_MODEL,
                temperature=0.3,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
            )
            raw_response = completion.choices[0].message.content
            if not raw_response:
                return None

            data = json.loads(raw_response)
            return QueryPair(**data)

        except RateLimitError:
            wait_time = 2 ** (attempt + 1)
            time.sleep(wait_time)
        except Exception as err:
            print(
                f"[WARN] Erro ao chamar LLM com modelo {GROQ_MODEL} (tentativa {attempt + 1}): {err}",
                file=sys.stderr,
            )
            time.sleep(1)

    return None


def fetch_all_chunks(qdrant: QdrantClient) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    offset = None

    while True:
        records, next_offset = qdrant.scroll(
            collection_name=COLLECTION_NAME,
            limit=SCROLL_BATCH_SIZE,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )

        for record in records:
            payload = record.payload or {}
            text = payload.get("text")
            if text and isinstance(text, str) and len(text.strip()) > 40:
                points.append(
                    {
                        "point_id": str(record.id),
                        "text": text.strip(),
                        "source": payload.get("source"),
                        "task_type": payload.get("task_type"),
                        "chunk_index": payload.get("chunk_index"),
                        "user_id": payload.get("user_id"),
                    }
                )

        if next_offset is None:
            break
        offset = next_offset

    return points


def main() -> None:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print(
            "[ERROR] A variável de ambiente GROQ_API_KEY não foi definida.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Conectando ao Qdrant em {QDRANT_HOST}:{QDRANT_PORT}...")
    # check_compatibility=False suprime o aviso de incompatibilidade de versão do cliente/servidor
    qdrant = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT, check_compatibility=False)

    if not qdrant.collection_exists(COLLECTION_NAME):
        print(
            f"[ERROR] Coleção '{COLLECTION_NAME}' não encontrada no Qdrant.",
            file=sys.stderr,
        )
        sys.exit(1)

    groq_client = Groq(api_key=api_key)

    print(f"Buscando pontos da coleção '{COLLECTION_NAME}'...")
    chunks = fetch_all_chunks(qdrant)
    print(f"Total de chunks válidos recuperados: {len(chunks)}")
    print(f"Utilizando modelo da Groq: {GROQ_MODEL}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    dataset: list[dict[str, Any]] = []

    for idx, item in enumerate(chunks, start=1):
        generated = extract_queries_with_groq(groq_client, item["text"])
        if not generated:
            continue

        # Pergunta Formal / Acadêmica
        dataset.append(
            {
                "query": generated.formal_query,
                "positive": item["text"],
                "query_style": "formal",
                "source": item["source"],
                "task_type": item["task_type"],
                "chunk_index": item["chunk_index"],
                "point_id": item["point_id"],
            }
        )

        # Pergunta Coloquial / Estudantil
        dataset.append(
            {
                "query": generated.colloquial_query,
                "positive": item["text"],
                "query_style": "colloquial",
                "source": item["source"],
                "task_type": item["task_type"],
                "chunk_index": item["chunk_index"],
                "point_id": item["point_id"],
            }
        )

        if idx % 10 == 0 or idx == len(chunks):
            print(
                f"Processados {idx}/{len(chunks)} chunks... ({len(dataset)} pares gerados)"
            )

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(dataset, f, ensure_ascii=False, indent=2)

    print(
        f"\nConcluído com sucesso! {len(dataset)} pares exportados para: {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()
