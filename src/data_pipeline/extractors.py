# Bibliotecas padrão do Python
import os
from functools import lru_cache
from io import BytesIO
from pathlib import Path

# Bibliotecas externas
import pymupdf
import pytesseract
import whisper
from docx import Document
from dotenv import load_dotenv
from PIL import Image

# Carrega as configurações do arquivo .env
RAIZ = Path(__file__).resolve().parents[2]
load_dotenv(RAIZ / ".env")

# Configura o caminho do Tesseract
caminho_tesseract = os.getenv("TESSERACT_CMD")

if caminho_tesseract:
    pytesseract.pytesseract.tesseract_cmd = caminho_tesseract


def extrair_texto_imagem(caminho_imagem: str) -> str:
    """
    Extrai o texto de uma imagem usando Tesseract OCR
    configurado para português e PSM 6.
    """
    caminho = Path(caminho_imagem)

    if not caminho.is_file():
        raise FileNotFoundError(f"Imagem não encontrada: {caminho}")

    with Image.open(caminho) as imagem:
        texto = pytesseract.image_to_string(imagem, lang="por", config="--psm 6")

    return texto.strip()


# TRANSCRIÇÃO DE ÁUDIOS


@lru_cache(maxsize=1)  # permite reutilizar o modelo Whisper já carregado
def carregar_modelo_whisper():
    """Carrega o modelo Whisper tiny uma única vez."""
    return whisper.load_model("tiny")


def _formatar_tempo(segundos: float) -> str:
    """Formata segundos em MM:SS para metadados de localização de áudio."""
    total = max(0, int(segundos))
    minutos, resto = divmod(total, 60)
    return f"{minutos:02d}:{resto:02d}"


def transcrever_audio_com_tempos(caminho_audio: str) -> list[tuple[str, str]]:
    """Transcreve áudio preservando faixas de tempo (MM:SS-MM:SS) por segmento."""
    caminho = Path(caminho_audio)

    if not caminho.is_file():
        raise FileNotFoundError(f"Áudio não encontrado: {caminho}")

    formatos_permitidos = {".ogg", ".mp3", ".wav"}

    if caminho.suffix.lower() not in formatos_permitidos:
        raise ValueError(f"Formato não suportado: {caminho.suffix}")

    modelo = carregar_modelo_whisper()
    resultado = modelo.transcribe(str(caminho), language="pt", fp16=False)

    segmentos = resultado.get("segments") or []
    saida: list[tuple[str, str]] = []
    for seg in segmentos:
        texto = str(seg.get("text", "")).strip()
        if not texto:
            continue
        inicio = _formatar_tempo(float(seg.get("start", 0.0)))
        fim = _formatar_tempo(float(seg.get("end", 0.0)))
        saida.append((f"{inicio}-{fim}", texto))

    if saida:
        return saida

    texto_completo = str(resultado.get("text", "")).strip()
    return [("00:00", texto_completo)] if texto_completo else []


def transcrever_audio(caminho_audio: str) -> str:
    """Transcreve arquivos OGG, MP3 e WAV em português."""
    segmentos = transcrever_audio_com_tempos(caminho_audio)
    return " ".join(texto for _, texto in segmentos).strip()


# EXTRAÇÃO DE TEXTO DE PDF


def extrair_paginas_pdf(caminho_pdf: str) -> list[tuple[str, str]]:
    """Extrai texto de PDFs digitais ou digitalizados preservando o número da página."""

    caminho = Path(caminho_pdf)

    if not caminho.is_file():
        raise FileNotFoundError(f"PDF não encontrado: {caminho}")

    paginas: list[tuple[str, str]] = []

    with pymupdf.open(caminho) as documento:
        for numero, pagina in enumerate(documento, start=1):
            texto = pagina.get_text("text").strip()

            # Se não há texto digital, usamos OCR na página.
            if not texto:
                pixmap = pagina.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)

                imagem = Image.open(BytesIO(pixmap.tobytes("png")))

                texto = pytesseract.image_to_string(
                    imagem, lang="por", config="--psm 6"
                ).strip()

            if texto:
                paginas.append((f"p. {numero}", texto))

    return paginas


def extrair_texto_pdf(caminho_pdf: str) -> str:
    """Extrai texto de PDFs digitais ou digitalizados."""
    return "\n\n".join(texto for _, texto in extrair_paginas_pdf(caminho_pdf))


# EXTRAÇÃO DE TEXTO DE WORD


def extrair_texto_word(caminho_word: str) -> str:
    """Extrai texto de arquivos Word .docx."""

    caminho = Path(caminho_word)

    if not caminho.is_file():
        raise FileNotFoundError(f"Word não encontrado: {caminho}")

    documento = Document(str(caminho))

    textos = []

    # Extrai parágrafos
    for paragrafo in documento.paragraphs:
        if paragrafo.text.strip():
            textos.append(paragrafo.text.strip())

    # Extrai conteúdo das tabelas
    for tabela in documento.tables:
        for linha in tabela.rows:
            celulas = [celula.text.strip() for celula in linha.cells]

            if any(celulas):
                textos.append(" | ".join(celulas))

    return "\n".join(textos)
