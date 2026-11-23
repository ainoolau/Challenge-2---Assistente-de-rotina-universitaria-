# Vezo Backend API (FastAPI + RAG Multimodal + Motor Determinístico)
# Runtime obrigatório: Python 3.11.x (conforme pyproject.toml e docs/MEMORY.md)

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/.cache/huggingface \
    VEZO_DB_PATH=/data/vezo.db \
    PORT=8000

WORKDIR /app

# Dependências de sistema para extração multimodal (Tesseract OCR PT-BR e FFmpeg para Whisper)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-por \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Instala PyTorch CPU-only antes de sentence-transformers/whisper para imagem enxuta
RUN python -m pip install --upgrade pip && \
    python -m pip install --index-url https://download.pytorch.org/whl/cpu torch

COPY requirements.txt pyproject.toml ./
RUN python -m pip install -r requirements.txt \
    "fastapi>=0.110.0" \
    "uvicorn[standard]>=0.28.0" \
    "pydantic>=2.6.0" \
    "python-multipart>=0.0.9" \
    "mlflow>=2.11.0"

COPY src ./src
COPY scripts ./scripts
COPY data/samples ./data/samples

# Usuário não-root e diretórios graváveis para SQLite (/data) e cache de modelos
RUN useradd --create-home --shell /bin/bash vezo && \
    mkdir -p /data /app/.cache/huggingface && \
    chown -R vezo:vezo /app /data

USER vezo

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=15s --retries=5 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.getenv(\"PORT\", \"8000\")}/health', timeout=3)"

CMD ["sh", "-c", "uvicorn src.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
