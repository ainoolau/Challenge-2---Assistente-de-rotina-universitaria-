
# Assistente de Rotina e Gestão de Tempo

Assistente inteligente para universitários em multijornada (faculdade, trabalho, projetos e estudo autônomo).

## Stack Principal

- Python 3.11
- FastAPI & Streamlit
- Qdrant (Vector Database) & MLflow
- Pytest & Ruff
- Sentence-Transformers, Whisper & Tesseract OCR

---

## Como Configurar o Ambiente Local (Primeira Vez)

### 1. Pré-requisitos

- **Python 3.11.x** (Obrigatório: versões >=3.12 apresentam incompatibilidade com dependências de IA).
  - **Windows:** instale via:
    ```powershell
    winget install Python.Python.3.11
    ```

- **Docker e Docker Compose** (para Qdrant e MLflow).

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

### 2. Instalação e Ambiente Virtual

1. **Clone o repositório e acesse a branch `develop`:**

   ```bash
   git clone https://github.com/ainoolau/Challenge-2---Assistente-de-rotina-universitaria-.git
   cd Challenge-2---Assistente-de-rotina-universitaria-
   git checkout develop
   ```

2. **Crie e ative a `.venv` usando Python 3.11:**

   **Windows (PowerShell):**

   ```powershell
   py -3.11 -m venv .venv
   .venv\Scripts\Activate.ps1
   ```

   **Linux / macOS:**

   ```bash
   python3.11 -m venv .venv
   source .venv/bin/activate
   ```

3. **Atualize o pip e instale o projeto em modo editável com dependências de desenvolvimento:**

   ```bash
   python -m pip install --upgrade pip
   pip install -e ".[dev]"
   ```

4. **Crie o arquivo de variáveis de ambiente:**

   **Windows (PowerShell):**

   ```powershell
   Copy-Item .env.example .env
   ```

   **Linux / macOS:**

   ```bash
   cp .env.example .env
   ```

### 3. Subir Infraestrutura Local (Docker)

Inicie o banco vetorial (**Qdrant**) e o servidor de métricas (**MLflow**):

```bash
docker compose -f infra/docker-compose.yml up -d
```

**Interfaces disponíveis:**

- **Qdrant Dashboard:** [http://localhost:6333/dashboard](http://localhost:6333/dashboard)
- **MLflow UI:** [http://localhost:5000](http://localhost:5000)

---

## Guia de Bolso Git (Fluxo Diário)

### 1. Atualizar a máquina antes de começar

```bash
git checkout develop
git pull origin develop
```

### 2. Criar a branch de trabalho

```bash
git checkout -b feat/nome-da-tarefa

# Ou utilize:
# fix/nome-do-bug
# chore/nome-da-tarefa
```

### 3. Validar e gravar as alterações

Execute as ferramentas de formatação, lint e testes antes de registrar as alterações:

```bash
ruff format .
ruff check .
pytest -v
git add .
git commit -m "feat: descricao curta da alteracao"
```

### 4. Enviar a branch e abrir o PR

```bash
git push -u origin feat/nome-da-tarefa
```

Acesse o GitHub e abra um **Pull Request (PR)** com destino à branch **`develop`**.

### 5. Como revisar o PR de um colega

```bash
git fetch origin
git checkout feat/branch-do-colega
pytest -v
```

Após testar localmente, aprove na interface do GitHub:

**Files changed → Review changes → Approve**

---

## Como Salvar e Subir as Alterações na Branch Atual

No PowerShell, ainda na branch `chore/setup-infra-e-dependencias`, execute:

```powershell
git add README.md
git commit -m "docs: adiciona guia de instalacao, docker e requisitos de sistema ao readme"
git push
```

Esses comandos irão:

1. Adicionar o `README.md` às alterações preparadas para commit.
2. Criar um commit documentando as alterações.
3. Enviar o commit para a branch remota atual, caso ela já tenha um upstream configurado.
