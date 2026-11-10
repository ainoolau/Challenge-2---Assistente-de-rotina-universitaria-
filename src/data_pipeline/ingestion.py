# TASK-03 - PIPELINE DE INGESTÃO MULTIMODAL
#
# 1. Lê arquivos de diferentes formatos
# 2. Extrai o texto dos arquivos
# 3. Divide os textos em blocos menores
# 4. Transforma os blocos em vetores (Modelo Multilíngue PT-BR)
# 5. Salva os vetores no Qdrant via Docker (HTTP)

from datetime import UTC, datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from qdrant_client import QdrantClient, models
from sentence_transformers import SentenceTransformer

from .extractors import (
    extrair_texto_imagem,
    extrair_texto_pdf,
    extrair_texto_word,
    transcrever_audio,
)

# CONFIGURAÇÕES DO PROJETO

PASTA_DOCUMENTOS = "data/samples"
QDRANT_HOST = "localhost"
QDRANT_PORT = 6333

# Nome da coleção utilizada pelo pipeline
NOME_COLECAO = "rotina_estudante_multimodal"

# MODELO MULTILÍNGUE (Suporte nativo a Português, 384 dimensões)
MODELO_NOME = "paraphrase-multilingual-MiniLM-L12-v2"

USUARIO = "usuario_teste"

FORMATOS_ACEITOS = [
    ".png",
    ".jpg",
    ".jpeg",
    ".ogg",
    ".mp3",
    ".wav",
    ".pdf",
    ".docx",
    ".txt",
]


# 1 - DIVIDIR O TEXTO EM BLOCOS


def dividir_texto(texto: str, tamanho: int = 500, sobreposicao: int = 50) -> list[str]:
    """Divide o texto em blocos de até 500 caracteres."""
    if tamanho <= 0:
        raise ValueError("O tamanho deve ser positivo.")

    if sobreposicao < 0 or sobreposicao >= tamanho:
        raise ValueError("Sobreposição inválida.")

    if not texto.strip():
        return []

    blocos = []
    passo = tamanho - sobreposicao

    for inicio in range(0, len(texto), passo):
        fim = inicio + tamanho
        bloco = texto[inicio:fim]
        blocos.append(bloco)

        if fim >= len(texto):
            break

    return blocos


# 2 - IDENTIFICAR O FORMATO E EXTRAIR O TEXTO


def extrair_conteudo(arquivo: Path) -> str:
    """Escolhe o extrator conforme o formato do arquivo."""
    extensao = arquivo.suffix.lower()

    if extensao in [".png", ".jpg", ".jpeg"]:
        return extrair_texto_imagem(str(arquivo))
    elif extensao in [".ogg", ".mp3", ".wav"]:
        return transcrever_audio(str(arquivo))
    elif extensao == ".pdf":
        return extrair_texto_pdf(str(arquivo))
    elif extensao == ".docx":
        return extrair_texto_word(str(arquivo))
    elif extensao == ".txt":
        return arquivo.read_text(encoding="utf-8-sig")
    else:
        raise ValueError("Formato não suportado.")


# 3 - GERAR OS EMBEDDINGS


def gerar_embeddings(
    blocos: list[str], modelo: SentenceTransformer | None = None
) -> list[list[float]]:
    """Transforma os blocos em vetores de 384 dimensões."""
    if not blocos:
        return []

    if modelo is None:
        modelo = SentenceTransformer(MODELO_NOME)

    vetores = modelo.encode(blocos)
    return vetores.tolist()


# 4 - IDENTIFICAR O TIPO DO DOCUMENTO


def identificar_tipo(arquivo: Path) -> str:
    """Identifica se o arquivo é imagem, áudio ou texto."""
    extensao = arquivo.suffix.lower()

    if extensao in [".png", ".jpg", ".jpeg"]:
        return "ocr"
    elif extensao in [".ogg", ".mp3", ".wav"]:
        return "audio"
    else:
        return "texto"


# 5 - EXECUTAR O PIPELINE


def executar_pipeline() -> None:
    """Processa os arquivos e envia os vetores ao Qdrant via Docker."""
    pasta = Path(PASTA_DOCUMENTOS)

    if not pasta.is_dir():
        print("Pasta de documentos não encontrada.")
        return

    arquivos = []
    for arquivo in pasta.iterdir():
        if arquivo.is_file() and arquivo.suffix.lower() in FORMATOS_ACEITOS:
            arquivos.append(arquivo)

    arquivos.sort()
    print("Arquivos encontrados:", len(arquivos))

    if len(arquivos) == 0:
        print("Nenhum arquivo encontrado.")
        return

    print(f"Carregando modelo multilíngue: {MODELO_NOME}...")
    modelo = SentenceTransformer(MODELO_NOME)

    print(f"Conectando ao Qdrant via Docker em {QDRANT_HOST}:{QDRANT_PORT}...")
    cliente = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

    try:
        # Recria a coleção para garantir compatibilidade vetorial
        if cliente.collection_exists(NOME_COLECAO):
            print(f"Recriando coleção '{NOME_COLECAO}' com os novos embeddings...")
            cliente.delete_collection(NOME_COLECAO)

        cliente.create_collection(
            collection_name=NOME_COLECAO,
            vectors_config=models.VectorParams(size=384, distance=models.Distance.COSINE),
        )
        print("Coleção multilíngue criada com sucesso!")

        documentos_processados = 0
        falhas = 0
        total_vetores = 0

        for arquivo in arquivos:
            print("\nProcessando:", arquivo.name)

            try:
                texto = extrair_conteudo(arquivo)
                blocos = dividir_texto(texto)

                if len(blocos) == 0:
                    print("Documento sem texto.")
                    falhas += 1
                    continue

                vetores = gerar_embeddings(blocos, modelo)
                pontos = []

                for i in range(len(blocos)):
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
                            "text": blocos[i],
                            "source": arquivo.as_posix(),
                            "task_type": identificar_tipo(arquivo),
                            "user_id": USUARIO,
                            "created_at": datetime.now(UTC).isoformat(),
                            "chunk_index": i,
                        },
                    )
                    pontos.append(ponto)

                cliente.upsert(collection_name=NOME_COLECAO, points=pontos, wait=True)

                documentos_processados += 1
                total_vetores += len(pontos)
                print("Documento processado com sucesso!")

            except Exception as erro:
                falhas += 1
                print("Erro ao processar:", erro)

        informacoes = cliente.get_collection(NOME_COLECAO)

        print("\n===== RESUMO =====")
        print("Documentos processados:", documentos_processados)
        print("Falhas:", falhas)
        print("Vetores enviados:", total_vetores)
        print("Pontos armazenados:", informacoes.points_count)

    finally:
        cliente.close()


if __name__ == "__main__":
    executar_pipeline()
