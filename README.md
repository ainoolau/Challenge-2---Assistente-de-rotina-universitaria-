
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

## Demonstração de Recuperação na Base Vetorial (TASK-05)

Script de terminal que recebe uma pergunta, busca os 3 trechos mais próximos no Qdrant
e mostra, para cada um, o score de similaridade, o arquivo de origem e o trecho exato.
Os problemas encontrados, o resultado do ensaio e as limitações estão em
[`observacoes.md`](observacoes.md).

### 1. Instalar as dependências (versões testadas)

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
pip install torch==2.15.0 --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```

### 2. Programas externos para a ingestão (OCR e áudio)

- **Tesseract em português:** depois de instalar o Tesseract (seção de pré-requisitos acima),
  baixe o [`por.traineddata`](https://github.com/tesseract-ocr/tessdata/raw/main/por.traineddata)
  para uma pasta junto com `eng.traineddata` e `osd.traineddata`, copiados de
  `C:\Program Files\Tesseract-OCR\tessdata`. Em seguida, configure:

  ```powershell
  $env:TESSDATA_PREFIX = "C:\caminho\para\tessdata"
  $env:TESSERACT_CMD   = "C:\Program Files\Tesseract-OCR\tesseract.exe"
  ```

- **ffmpeg** (o Whisper usa para ler os áudios), copiado do pacote `imageio-ffmpeg` para dentro do venv:

  ```powershell
  copy (python -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())") .venv\Scripts\ffmpeg.exe
  ```

### 3. Popular a base vetorial (ingestão da TASK-03)

Coloque os documentos (`.pdf`, `.png`, `.jpg`, `.jpeg`, `.ogg`, `.mp3`, `.wav`, `.docx`, `.txt`)
direto em `data/samples/`, sem subpastas, e nomeados como `Nome_pdf.*` e `Nome_audio.*`.
Depois rode:

```powershell
python -m src.data_pipeline.ingestion
```

A base fica em `data/qdrant/`, na collection `rotina_estudante_multimodal`.

> Requer o código da TASK-03 (`src/data_pipeline/ingestion.py` e `extractors.py`).
> Na branch atual dela, o `extractors.py` tem um erro que impede a execução.
> Veja o item 1 de [`observacoes.md`](observacoes.md).

### 4. Rodar a demonstração

```powershell
# Ensaio: roda as 3 perguntas de scripts/demo_questions.json e mostra OK/FALHA
python scripts/demo_retrieval.py --ensaio

# Uma pergunta
python scripts/demo_retrieval.py "Quando é a aula de Econometria?"

# Modo interativo (recomendado para apresentar: o modelo é carregado uma vez só)
python scripts/demo_retrieval.py --offline
```

| Opção | Efeito |
| --- | --- |
| `--ensaio [arquivo.json]` | Roda as perguntas de ensaio e confere se a fonte e o trecho esperados vêm no top-3 em menos de 1 s. |
| `--offline` | Usa só o modelo em cache, sem acessar a internet. |
| `--top-k N` | Quantidade de trechos retornados (padrão: 3). |
| `--collection NOME` | Outra collection (padrão: `rotina_estudante_multimodal`). |

Variáveis de ambiente opcionais:

- `QDRANT_URL`: usa o servidor Qdrant do Docker (por exemplo, `http://localhost:6333`) em vez da base local.
- `QDRANT_PATH`: outra pasta para a base local.
- `QDRANT_COLLECTION`: outro nome padrão de collection.

> Abrir o script leva cerca de 30 s, por causa do carregamento das bibliotecas de IA.
> Cada consulta leva menos de 50 ms.

### 5. Testes e lint

```powershell
ruff format --check .
ruff check .
pytest -q
```

Os testes de `tests/test_retrieval.py` usam um embedder falso e o Qdrant em memória,
então não baixam o modelo nem precisam da base populada.

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
