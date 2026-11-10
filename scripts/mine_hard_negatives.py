"""Script para minerar Hard Negatives a partir do dataset de pares e da base Qdrant."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

# Configurações do projeto
TRAIN_PAIRS_PATH = Path("data/finetuning/train_pairs.json")
OUTPUT_TRIPLETS_PATH = Path("data/finetuning/triplets_train.json")

QDRANT_HOST = "localhost"
QDRANT_PORT = 6333
COLLECTION_NAME = "rotina_estudante_multimodal"
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
TOP_K = 5


def mine_hard_negatives() -> None:
    """Gera o dataset de trios (anchor, positive, negative) minerando negativos no Qdrant."""
    if not TRAIN_PAIRS_PATH.exists():
        print(f"Erro: Arquivo não encontrado em {TRAIN_PAIRS_PATH}")
        sys.exit(1)

    with TRAIN_PAIRS_PATH.open(encoding="utf-8") as file:
        train_pairs = json.load(file)

    print(f"Total de pares carregados: {len(train_pairs)}")

    print(f"Carregando modelo {MODEL_NAME}...")
    model = SentenceTransformer(MODEL_NAME)

    print(f"Conectando ao Qdrant em {QDRANT_HOST}:{QDRANT_PORT}...")
    client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

    triplets = []
    skipped_count = 0

    try:
        for idx, item in enumerate(train_pairs, start=1):
            query = item["query"]
            positive_text = item["positive"]
            origin_point_id = item.get("point_id")

            # Encodar a query atual
            query_vector = model.encode(query).tolist()

            # Buscar Top-5 chunks mais similares
            search_response = client.query_points(
                collection_name=COLLECTION_NAME,
                query=query_vector,
                limit=TOP_K,
                with_payload=True,
            )

            # Selecionar o candidato de maior score que não seja o chunk de origem
            hard_negative_text = None
            for point in search_response.points:
                point_id = str(point.id)
                candidate_text = point.payload.get("text", "").strip()

                if point_id != str(origin_point_id) and candidate_text != positive_text.strip():
                    hard_negative_text = candidate_text
                    break

            if hard_negative_text:
                triplets.append({
                    "anchor": query,
                    "positive": positive_text,
                    "negative": hard_negative_text,
                })
            else:
                skipped_count += 1
                print(f"Aviso [{idx}]: Nenhum hard negative encontrado para point_id={origin_point_id}")

    finally:
        client.close()

    OUTPUT_TRIPLETS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_TRIPLETS_PATH.open("w", encoding="utf-8") as file:
        json.dump(triplets, file, ensure_ascii=False, indent=2)

    print("Mineração finalizada com sucesso!")
    print(f"- Total de trios gerados: {len(triplets)}")
    print(f"- Itens ignorados/sem negativo: {skipped_count}")
    print(f"- Arquivo salvo em: {OUTPUT_TRIPLETS_PATH.resolve()}")


if __name__ == "__main__":
    mine_hard_negatives()