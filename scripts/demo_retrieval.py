"""
Script Executável de Demonstração (TASK-05) - Live Demo do RAG Multimodal Multilíngue.
"""

import sys

from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

QDRANT_HOST = "localhost"
QDRANT_PORT = 6333
COLLECTION_NAME = "rotina_estudante_multimodal"
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"


def main():
    print("\n" + "=" * 65)
    print("   ASSISTENTE DE ROTINA UNIVERSITÁRIA - DEMO MULTILÍNGUE")
    print("   TASK-05: Live Retrieval & Rastreabilidade de Fontes")
    print("=" * 65 + "\n")

    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
    else:
        query = input(
            "Digite sua dúvida sobre rotina/aulas/editais (Enter para padrão): "
        )

    if not query.strip():
        query = "Quais são as regras de frequência e bolsa da residência?"
        print(f"[*] Pergunta padrão adotada: '{query}'\n")

    print(f"[*] Pergunta: '{query}'")
    print(f"[*] Carregando modelo multilíngue ({MODEL_NAME})...")
    model = SentenceTransformer(MODEL_NAME)
    query_vector = model.encode(query).tolist()

    print(f"[*] Consultando Qdrant em {QDRANT_HOST}:{QDRANT_PORT}...")
    client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

    try:
        if hasattr(client, "query_points"):
            response = client.query_points(
                collection_name=COLLECTION_NAME,
                query=query_vector,
                limit=3,
                with_payload=True,
            )
            results = response.points
        else:
            results = client.search(
                collection_name=COLLECTION_NAME,
                query_vector=query_vector,
                limit=3,
                with_payload=True,
            )
    except Exception as e:
        print(f"\n[ERRO] Falha ao consultar coleção '{COLLECTION_NAME}': {e}")
        return
    finally:
        client.close()

    print("\n" + "-" * 65)
    print("               EVIDÊNCIAS E FONTES RECUPERADAS")
    print("-" * 65)

    if not results:
        print("[!] Nenhum documento ou trecho relevante encontrado no banco.")
        return

    for idx, hit in enumerate(results, start=1):
        score = hit.score
        payload = hit.payload or {}
        source = payload.get("source", "Origem desconhecida")
        task_type = payload.get("task_type", "texto")
        chunk_idx = payload.get("chunk_index", 0)
        text = payload.get("text", "")

        print(f"\n[Documento {idx}] • Score de Similaridade: {score:.4f}")
        print(f"  • Fonte (Arquivo): {source}")
        print(f"  • Modalidade: {str(task_type).upper()} | Chunk: #{chunk_idx}")
        print("  • Trecho Recuperado:")
        print(f'    "{str(text).strip()}"')

    print("\n" + "=" * 65)
    print("DEMONSTRAÇÃO CONCLUÍDA: Recuperação Semântica Multilíngue Validada.")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()
