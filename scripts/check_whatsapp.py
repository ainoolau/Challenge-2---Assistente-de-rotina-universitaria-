from pathlib import Path

from qdrant_client import QdrantClient

client = QdrantClient(host="localhost", port=6333)
records, _ = client.scroll(
    collection_name="rotina_estudante_multimodal", limit=200, with_payload=True
)

print("--- TEXTO COMPLETO DO PRINT DO WHATSAPP ---")
for r in records:
    if "comunicado_monitoria_05.jpg" in Path(r.payload.get("source", "")).name:
        print(f"\n[ID: {r.id}] Payload Keys: {list(r.payload.keys())}")
        print(r.payload.get("text"))
