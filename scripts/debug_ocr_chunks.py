from pathlib import Path

from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

client = QdrantClient(host="localhost", port=6333)
model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

target_files = ["grade_aluno_06.jpg", "comunicado_monitoria_05.jpg"]

print("--- 1. CHUNKS DESSES ARQUIVOS NO QDRANT ---")
records, _ = client.scroll(
    collection_name="rotina_estudante_multimodal", limit=200, with_payload=True
)

for tf in target_files:
    chunks = [
        (r.payload.get("chunk_id"), r.payload.get("text"))
        for r in records
        if tf in Path(r.payload.get("source", "")).name
    ]
    print(f"\nArquivo: {tf} | Total de Chunks: {len(chunks)}")
    for cid, txt in chunks:
        preview = txt.replace("\n", " ")[:140]
        print(f'  Chunk #{cid}: "{preview}..."')

print("\n--- 2. EM QUAL POSIÇÃO ELES APARECEM (TOP-20)? ---")
queries = [
    (
        "Atividades de orientação exigem dedicação em período integral?",
        "grade_aluno_06.jpg",
    ),
    (
        "Quais são os comunicados e orientações sobre monitoria e pesquisa?",
        "comunicado_monitoria_05.jpg",
    ),
]

for q, expected in queries:
    print(f"\nQuery: '{q}'")
    vec = model.encode(q).tolist()
    points = client.query_points(
        collection_name="rotina_estudante_multimodal",
        query=vec,
        limit=20,
        with_payload=True,
    ).points

    found = False
    for idx, p in enumerate(points, start=1):
        src = Path(p.payload.get("source", "")).name
        if expected in src:
            print(
                f"  -> Rank #{idx} | Score: {p.score:.4f} | Chunk #{p.payload.get('chunk_id')}"
            )
            found = True
            break
    if not found:
        print("  -> Não apareceu nem no Top-20")
