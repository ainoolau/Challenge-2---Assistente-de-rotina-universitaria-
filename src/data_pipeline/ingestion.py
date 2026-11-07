
# TASK-03 - PIPELINE DE INGESTÃO MULTIMODAL
#
# Este programa:
# 1. Lê arquivos de diferentes formatos
# 2. Extrai o texto dos arquivos
# 3. Divide os textos em blocos menores
# 4. Transforma os blocos em vetores
# 5. Salva os vetores no Qdrant


# BIBLIOTECAS

from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid5, NAMESPACE_URL

from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient, models

from .extractors import (
    extrair_texto_imagem,
    transcrever_audio,
    extrair_texto_pdf,
    extrair_texto_word,
)


# CONFIGURAÇÕES DO PROJETO

PASTA_DOCUMENTOS = "data/samples"
PASTA_QDRANT = "data/qdrant"

# Coleção separada para nossos testes
NOME_COLECAO = "rotina_estudante_multimodal"

USUARIO = "usuario_teste"

FORMATOS_ACEITOS = [
    ".png", ".jpg", ".jpeg",
    ".ogg", ".mp3", ".wav",
    ".pdf", ".docx", ".txt"
]


# 1 - DIVIDIR O TEXTO EM BLOCOS

def dividir_texto(texto, tamanho=500, sobreposicao=50):
    """Divide o texto em blocos de até 500 caracteres."""

    if tamanho <= 0:
        raise ValueError("O tamanho deve ser positivo.")

    if sobreposicao < 0 or sobreposicao >= tamanho:
        raise ValueError("Sobreposição inválida.")

    if not texto.strip():
        return []

    blocos = []

    # Cada novo bloco começa 450 caracteres depois
    passo = tamanho - sobreposicao

    for inicio in range(0, len(texto), passo):

        fim = inicio + tamanho
        bloco = texto[inicio:fim]

        blocos.append(bloco)

        # Para quando chegar ao final do texto
        if fim >= len(texto):
            break

    return blocos


# 2 - IDENTIFICAR O FORMATO E EXTRAIR O TEXTO

def extrair_conteudo(arquivo):
    """Escolhe o extrator conforme o formato do arquivo."""

    extensao = arquivo.suffix.lower()

    # Imagens
    if extensao in [".png", ".jpg", ".jpeg"]:
        return extrair_texto_imagem(str(arquivo))

    # Áudios
    elif extensao in [".ogg", ".mp3", ".wav"]:
        return transcrever_audio(str(arquivo))

    # PDF
    elif extensao == ".pdf":
        return extrair_texto_pdf(str(arquivo))

    # Word
    elif extensao == ".docx":
        return extrair_texto_word(str(arquivo))

    # Texto simples
    elif extensao == ".txt":
        return arquivo.read_text(encoding="utf-8-sig")

    else:
        raise ValueError("Formato não suportado.")


# 3 - GERAR OS EMBEDDINGS

def gerar_embeddings(blocos, modelo=None):
    """Transforma os blocos em vetores de 384 dimensões."""

    if not blocos:
        return []

    # Carrega o modelo caso ainda não tenha sido passado
    if modelo is None:
        modelo = SentenceTransformer(
            "all-MiniLM-L6-v2",
            local_files_only=True
        )

    vetores = modelo.encode(blocos)

    return vetores.tolist()


# 4 - IDENTIFICAR O TIPO DO DOCUMENTO

def identificar_tipo(arquivo):
    """Identifica se o arquivo é imagem, áudio ou texto."""

    extensao = arquivo.suffix.lower()

    if extensao in [".png", ".jpg", ".jpeg"]:
        return "ocr"

    elif extensao in [".ogg", ".mp3", ".wav"]:
        return "audio"

    else:
        return "texto"


# 5 - EXECUTAR O PIPELINE

def executar_pipeline():
    """Processa os arquivos e envia os vetores ao Qdrant."""

    # Localizar a pasta dos documentos
    pasta = Path(PASTA_DOCUMENTOS)

    if not pasta.is_dir():
        print("Pasta de documentos não encontrada.")
        return

    # Encontrar os arquivos compatíveis
    arquivos = []

    for arquivo in pasta.iterdir():

        if arquivo.is_file():
            if arquivo.suffix.lower() in FORMATOS_ACEITOS:
                arquivos.append(arquivo)

    arquivos.sort()

    print("Arquivos encontrados:", len(arquivos))

    if len(arquivos) == 0:
        print("Nenhum arquivo encontrado.")
        return

    # Carregar o modelo apenas uma vez
    modelo = SentenceTransformer(
        "all-MiniLM-L6-v2",
        local_files_only=True
    )

    # Preparar a pasta do banco local
    Path(PASTA_QDRANT).mkdir(
        parents=True,
        exist_ok=True
    )

    # Conectar ao Qdrant
    cliente = QdrantClient(path=PASTA_QDRANT)

    try:

        # Criar a coleção caso ainda não exista
        if not cliente.collection_exists(NOME_COLECAO):

            cliente.create_collection(
                collection_name=NOME_COLECAO,
                vectors_config=models.VectorParams(
                    size=384,
                    distance=models.Distance.COSINE
                )
            )

            print("Coleção criada no Qdrant!")

        # Contadores
        documentos_processados = 0
        falhas = 0
        total_vetores = 0

        # Processar os arquivos, um por vez
        for arquivo in arquivos:

            print("\nProcessando:", arquivo.name)

            try:

                # Extrair o texto
                texto = extrair_conteudo(arquivo)

                # Dividir em blocos
                blocos = dividir_texto(texto)

                if len(blocos) == 0:
                    print("Documento sem texto.")
                    falhas += 1
                    continue

                # Gerar os vetores
                vetores = gerar_embeddings(blocos, modelo)

                pontos = []

                # Criar um ponto para cada bloco
                for i in range(len(blocos)):

                    # Identificador fixo para cada arquivo e bloco
                    identificador = str(
                        uuid5(
                            NAMESPACE_URL,
                            f"{USUARIO}:{arquivo.as_posix()}:{i}"
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
                            "created_at": datetime.now(
                                timezone.utc
                            ).isoformat(),
                            "chunk_index": i
                        }
                    )

                    pontos.append(ponto)

                # Salvar os vetores no Qdrant
                cliente.upsert(
                    collection_name=NOME_COLECAO,
                    points=pontos,
                    wait=True
                )

                documentos_processados += 1
                total_vetores += len(pontos)

                print("Documento processado com sucesso!")

            except Exception as erro:
                falhas += 1
                print("Erro ao processar:", erro)

        # Consultar a quantidade de pontos no banco
        informacoes = cliente.get_collection(NOME_COLECAO)

        # Mostrar o resultado final
        print("\n===== RESUMO =====")
        print("Documentos processados:", documentos_processados)
        print("Falhas:", falhas)
        print("Vetores enviados:", total_vetores)
        print("Pontos armazenados:", informacoes.points_count)

    finally:
        # Fechar a conexão com o Qdrant
        cliente.close()


# 6 - INICIAR O PROGRAMA

if __name__ == "__main__":
    executar_pipeline()
