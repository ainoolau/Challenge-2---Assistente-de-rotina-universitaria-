# Assistente de Rotina e Gestão de Tempo

Assistente inteligente para universitários em multijornada (faculdade, trabalho, projetos e estudo autônomo).

## Stack Principal

- **Linguagem & Runtime:** Python 3.11
- **Backend & APIs:** FastAPI
- **Banco Vetorial & MLOps:** Qdrant (Docker) & MLflow
- **Processamento Multimodal:** Sentence-Transformers (`all-MiniLM-L6-v2`), Whisper local (`tiny`) e Tesseract OCR (`--psm 6`)
- **Qualidade & Testes:** Pytest & Ruff

---

## Como Configurar o Ambiente Local (Primeira Vez)

### 1. Pré-requisitos

- **Python 3.11.x** (Obrigatório: versões >=3.12 apresentam incompatibilidade com dependências de IA).
  - **Windows:** instale via PowerShell:
    ```powershell
    winget install Python.Python.3.11
    ```
- **Docker e Docker Compose** (para execução isolada do Qdrant e MLflow).
- **Tesseract OCR** (para ingestão de fotos e grades de horários):
  - **Windows:**
    ```powershell
    winget install UB-Mannheim.TesseractOCR
    ```
  - **Linux (Ubuntu/Debian):**
    ```bash
    sudo apt install tesseract-ocr tesseract-ocr-por
    ```
  - **macOS:**
    ```bash
    brew install tesseract tesseract-lang
    ```
- **FFmpeg** (necessário para o processamento de áudio com Whisper):
  - **Windows:** `winget install Gyan.FFmpeg`
  - **Linux:** `sudo apt install ffmpeg`
  - **macOS:** `brew install ffmpeg`

### 2. Instalação e Ambiente Virtual

1. **Clone o repositório e acesse a branch de trabalho:**

   ```bash
   git clone [https://github.com/ainoolau/Challenge-2---Assistente-de-rotina-universitaria-.git](https://github.com/ainoolau/Challenge-2---Assistente-de-rotina-universitaria-.git)
   cd Challenge-2---Assistente-de-rotina-universitaria-
   git checkout develop