import uuid

import pytest

qdrant_client_lib = pytest.importorskip(
    "qdrant_client", reason="qdrant-client não instalado no ambiente"
)
from qdrant_client import QdrantClient  # noqa: E402
from qdrant_client.http import models  # noqa: E402


@pytest.fixture(scope="module")
def qdrant_client():
    client = QdrantClient(host="localhost", port=6333, timeout=2.0)
    try:
        client.get_collections()
    except Exception:  # noqa: BLE001
        pytest.skip("Serviço Qdrant não está rodando em localhost:6333 (ambiente CI/sem Docker).")
    yield client
    client.close()


def test_qdrant_smoke_lifecycle(qdrant_client: QdrantClient):
    collection_name = f"test_smoke_{uuid.uuid4().hex[:8]}"
    vector_dim = 384
    dummy_vector = [0.1] * vector_dim
    point_id = 1

    try:
        # 1. Cria coleção temporária no Qdrant
        created = qdrant_client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(
                size=vector_dim,
                distance=models.Distance.COSINE,
            ),
        )
        assert created is True

        # 2. Insere 1 ponto/vetor de teste
        upsert_result = qdrant_client.upsert(
            collection_name=collection_name,
            points=[
                models.PointStruct(
                    id=point_id,
                    vector=dummy_vector,
                    payload={"status": "smoke_test_ok"},
                )
            ],
            wait=True,
        )
        assert upsert_result.status == models.UpdateStatus.COMPLETED

        # 3. Recupera o ponto inserido
        retrieved_points = qdrant_client.retrieve(
            collection_name=collection_name,
            ids=[point_id],
            with_vectors=True,
            with_payload=True,
        )
        assert len(retrieved_points) == 1
        assert retrieved_points[0].payload["status"] == "smoke_test_ok"

    finally:
        # 4. Remove a coleção de teste
        qdrant_client.delete_collection(collection_name=collection_name)
