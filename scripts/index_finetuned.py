"""Indexação dos chunks em coleção Qdrant com suporte a parâmetros CLI."""

import argparse
from datetime import UTC, datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from qdrant_client import QdrantClient, models
from sentence_transformers import SentenceTransformer

from src.data_pipeline.ingestion import (
    FORMATOS_ACEITOS,
    PASTA_DOCUMENTOS,
    QDRANT_HOST,
    QDRANT_PORT,
    USUARIO,
    dividir_texto,
    extrair_conteudo,
    identificar_tipo,
)

DEFAULT_MODEL_PATH = "models/MiniLM-L12-rotina-v2"
DEFAULT_COLLECTION = "rotina_estudante_finetuned"
VECTOR_DIMENSION = 384


def indexar_colecao(
    model_path: str = DEFAULT_MODEL_PATH,
    collection_name: str = DEFAULT_COLLECTION,
) -> None:
    pasta = Path(PASTA_DOCUMENTOS)
    if not pasta.is_dir():
        print(f"[!] Diretório de documentos '{PASTA_DOCUMENTOS}' não encontrado.")
        return

    arquivos = sorted(
        [
            arq
            for arq in pasta.iterdir()
            if arq.is_file() and arq.suffix.lower() in FORMATOS_ACEITOS
        ]
    )

    if not arquivos:
        print("[!] Nenhum arquivo suportado encontrado para indexação.")
        return

    print(f"[*] Carregando modelo: '{model_path}'...")
    modelo = SentenceTransformer(model_path)

    print(f"[*] Conectando ao Qdrant em {QDRANT_HOST}:{QDRANT_PORT}...")
    cliente = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

    try:
        if cliente.collection_exists(collection_name):
            print(f"[*] Recriando coleção '{collection_name}'...")
            cliente.delete_collection(collection_name)

        cliente.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(
                size=VECTOR_DIMENSION,
                distance=models.Distance.COSINE,
            ),
        )
        print(f"[✓] Coleção '{collection_name}' provisionada com sucesso.")

        total_chunks = 0
        documentos_processados = 0

        for arquivo in arquivos:
            try:
                texto = extrair_conteudo(arquivo)
                blocos = dividir_texto(texto)

                if not blocos:
                    continue

                vetores = modelo.encode(blocos).tolist()
                pontos = []

                for i, bloco in enumerate(blocos):
                    identificador = str(
                        uuid5(
                            NAMESPACE_URL,
                            f"{USUARIO}:{arquivo.as_posix()}:{i}",
                        )
                    )

                    ponto = models.PointStruct(
                        id=identificador,
                        vector=vetores[i],
                        payload={
                            "text": bloco,
                            "source": arquivo.as_posix(),
                            "task_type": identificar_tipo(arquivo),
                            "user_id": USUARIO,
                            "created_at": datetime.now(UTC).isoformat(),
                            "chunk_index": i,
                        },
                    )
                    pontos.append(ponto)

                cliente.upsert(
                    collection_name=collection_name, points=pontos, wait=True
                )
                documentos_processados += 1
                total_chunks += len(pontos)
                print(f"  [+] {arquivo.name}: {len(pontos)} chunks indexados.")

            except Exception as exc:
                print(f"  [-] Erro ao processar '{arquivo.name}': {exc}")

        info = cliente.get_collection(collection_name)
        print("\n" + "=" * 55)
        print(f"   INDEXAÇÃO CONCLUÍDA: {collection_name}")
        print("=" * 55)
        print(f"Documentos processados: {documentos_processados}")
        print(f"Total de pontos na coleção: {info.points_count} (esperado: 162)")
        print("Coleção original 'rotina_estudante_multimodal' mantida intacta.")
    finally:
        cliente.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Indexação de chunks no Qdrant com modelo especificado"
    )
    parser.add_argument(
        "--model-path",
        default=DEFAULT_MODEL_PATH,
        help="Caminho do modelo local ou HuggingFace",
    )
    parser.add_argument(
        "--collection",
        default=DEFAULT_COLLECTION,
        help="Nome da coleção de destino no Qdrant",
    )
    args = parser.parse_args()

    indexar_colecao(model_path=args.model_path, collection_name=args.collection)
