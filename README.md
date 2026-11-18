# Assistente de Rotina e Gestão de Tempo

Assistente inteligente para universitários em multijornada (faculdade, trabalho, projetos e estudo autônomo).

## Stack Principal

- **Linguagem & Runtime:** Python 3.11
- **Backend & APIs:** FastAPI
- **Banco Vetorial & MLOps:** Qdrant (Docker) & MLflow
- **Processamento Multimodal:** Sentence-Transformers (`paraphrase-multilingual-MiniLM-L12-v2`), Whisper local (`tiny`) e Tesseract OCR (`--psm 6`)
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
   git clone https://github.com/ainoolau/Challenge-2---Assistente-de-rotina-universitaria-.git
   cd Challenge-2---Assistente-de-rotina-universitaria-
   git checkout develop
   ```

2. **Crie e ative o ambiente virtual:**

   ```bash
   python3.11 -m venv .venv
   source .venv/bin/activate
   ```

   No Windows (PowerShell), use `py -3.11 -m venv .venv` e
   `.\.venv\Scripts\Activate.ps1`.

3. **Instale as dependências:**

   ```bash
   python -m pip install -r requirements.txt
   ```

4. **Suba o Qdrant pelo Docker Compose:**

   ```bash
   docker compose -f infra/docker-compose.yml up -d qdrant
   ```

   Qdrant fica disponível em `http://localhost:6333`. Para iniciar também
   o MLflow, execute `docker compose -f infra/docker-compose.yml up -d`.

### Benchmark zero-shot (Cenário 1)

O executor independente `scripts/scenarios/zero_shot.py` usa Groq ou Ollama sem recuperação
documental. Consulte [configuração, contrato oficial e execução](docs/zero_shot.md).

### Sistema multiagentes

`python scripts/demo_multiagents.py` executa quatro cenários simulados de pesquisa,
síntese, validação e planejamento. Para Groq/Qdrant reais, consulte
[execução e validação](docs/multiagent_execution.md) e
[arquitetura e contratos](docs/multiagent_architecture.md).
