# TASK-05: Script Executável de Demonstração · Observações

Script de terminal que consulta a base vetorial (Qdrant) e mostra os 3 trechos mais
próximos de uma pergunta: score de similaridade, arquivo de origem e trecho exato.

## Arquivos desta task

| Arquivo | O que faz |
| --- | --- |
| `scripts/demo_retrieval.py` | A demo: pergunta por argumento, modo interativo ou `--ensaio`. |
| `scripts/demo_questions.json` | As 3 perguntas de ensaio, com a fonte e o trecho esperados. |
| `src/data_pipeline/retrieval.py` | Busca no Qdrant e verificação do trecho esperado (reaproveitável pelo agente RAG). |
| `tests/test_retrieval.py` | Testes com embedder falso e Qdrant em memória (não baixam modelo). |
| `requirements.txt` | Versões testadas das dependências. |

A demo **não faz ingestão**. Ela lê a base criada pela TASK-03 (`src/data_pipeline/ingestion.py`)
e usa o mesmo contrato dela:

- collection `rotina_estudante_multimodal`
- modelo `all-MiniLM-L6-v2` (384 dimensões, cosseno)
- payload com `text`, `source`, `task_type` e `chunk_index`
- Qdrant local em `data/qdrant`, ou um servidor, se `QDRANT_URL` estiver definida (por exemplo, `http://localhost:6333`, da TASK-02)

## Resultado do ensaio

Base: os 15 arquivos de `data/samples/` (7 áudios e 8 grades horárias), que geraram 41 trechos.

| Pergunta | Fonte esperada | Posição | Tempo |
| --- | --- | --- | --- |
| Quando é a aula de Econometria? | `Sophia_audio.mp3` | #1 | 20–29 ms |
| Atividades de orientação exigem dedicação em período integral? | `Geovanna_pdf.jpg` | #1 | 26–41 ms |
| Quais dias a Mahiaara vai para a academia? | `Mahiaara_audio.mp3` | #2 | 19–31 ms |

**3/3 aprovadas**: o trecho esperado aparece no top-3, e cada consulta leva menos de 1 s.
Os resultados se repetem entre execuções, porque a busca é determinística.

## Como testar

### 1. Ambiente Python

```powershell
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install torch==2.15.0 --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```

### 2. Programas externos (só para rodar a ingestão)

- **Tesseract OCR**, para as grades em imagem e para PDFs escaneados:
  `winget install --id UB-Mannheim.TesseractOCR -e`.
  O instalador traz só o inglês. Baixe o
  [`por.traineddata`](https://github.com/tesseract-ocr/tessdata/raw/main/por.traineddata)
  e coloque-o numa pasta que também tenha `eng.traineddata` e `osd.traineddata`,
  copiados de `C:\Program Files\Tesseract-OCR\tessdata`. Em seguida, aponte para ela:
  ```powershell
  $env:TESSDATA_PREFIX = "C:\caminho\para\tessdata"
  $env:TESSERACT_CMD   = "C:\Program Files\Tesseract-OCR\tesseract.exe"
  ```
- **ffmpeg**, para o Whisper ler os áudios. O `winget install Gyan.FFmpeg` falhou nesta
  máquina. A alternativa que funcionou foi copiar o binário do `imageio-ffmpeg` para dentro do venv:
  ```powershell
  copy (python -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())") .venv\Scripts\ffmpeg.exe
  ```

### 3. Popular a base (código da TASK-03)

```powershell
python -m src.data_pipeline.ingestion
```

Atenção: veja o problema 1 abaixo. Na branch `feat/task-03-ingestion`, esse comando hoje
**falha** antes de começar. Também é preciso que `src/data_pipeline/ingestion.py` e
`extractors.py` estejam presentes, o que significa ter a TASK-03 mergeada ou fazer
checkout dos dois arquivos.

### 4. Rodar a demo

```powershell
python scripts/demo_retrieval.py --ensaio            # as 3 perguntas, com resumo OK/FALHA
python scripts/demo_retrieval.py "Quando é a aula de Econometria?"
python scripts/demo_retrieval.py --offline           # modo interativo, sem internet
pytest -q                                            # testes
```

O `--offline` usa o modelo que já está em cache, sem consultar o Hugging Face.
Ele só funciona depois que o modelo foi baixado pelo menos uma vez.

## Problemas encontrados e pontos de atenção

### 1. A ingestão da TASK-03 não roda (bloqueante, responsabilidade da TASK-03)

Em `feat/task-03-ingestion`, o arquivo `src/data_pipeline/extractors.py` tem o conteúdo
**colado duas vezes**, e o `import os` da segunda cópia ficou cortado (` os`). Isso gera
`IndentationError` na linha 157, e a ingestão para antes de processar qualquer arquivo.
**Correção sugerida:** apagar da linha 157 até o fim do arquivo, porque as duas metades são iguais.
A branch da TASK-03 não foi alterada por esta task. A base usada no ensaio foi gerada a
partir de uma cópia local corrigida.

### 2. Arquivos `.m4a` são ignorados sem aviso (TASK-03)

A ingestão só aceita `.ogg`, `.mp3` e `.wav`. Os 5 áudios recebidos em `.m4a` (Geovanna,
Julia, Mahiaara, Milena e Sophia) foram convertidos para `.mp3`, e os originais foram removidos.
**Sugestão para a TASK-03:** incluir `.m4a` em `FORMATOS_ACEITOS`, porque o Whisper já lê esse formato.

### 3. Qualidade da recuperação é baixa fora das perguntas de ensaio

As 3 perguntas de ensaio funcionam, mas várias outras perguntas testadas trazem trechos errados:

| Pergunta testada | O que voltou |
| --- | --- |
| Quais disciplinas tenho na quarta-feira? | áudios de outras pessoas, sem relação |
| Quando começa e termina o período letivo 2026.2? | trechos sem a data |
| Quais aulas a Jhecy tem na segunda-feira à noite? | grade do Antonio e áudios de outras pessoas |
| Quando a Julia trabalha? | áudios de outras pessoas |

Causas prováveis:

- **Modelo de embeddings em inglês.** O `all-MiniLM-L6-v2` foi treinado principalmente em
  inglês, e todos os documentos estão em português. Vale avaliar um modelo multilíngue, como
  `paraphrase-multilingual-MiniLM-L12-v2` ou `multilingual-e5-base`, como já prevê
  `docs/pipeline_arquitetura.md`. Trocar o modelo exige reindexar tudo e alterar o modelo
  nas duas tasks.
- **Texto com ruído.** O Whisper `tiny` erra bastante em português ("segunda-squartas",
  "oitoas dezoito"), e o OCR das grades em imagem embaralha a tabela de horários
  (por exemplo, "Econosa Ecoos4" no lugar de "ECO0054").
- **O nome da pessoa não está no trecho.** A ligação entre a pessoa e o arquivo existe só
  no nome do arquivo (`source`), que não entra no embedding. Por isso perguntas como
  "aulas da Jhecy" não encontram a pessoa. A ingestão sempre grava `user_id` como
  `usuario_teste`. Uma sugestão é gravar o nome da pessoa no `user_id` e permitir filtrar
  a busca por ele.
- **Tabelas de horário cortadas em blocos de 500 caracteres.** O código da disciplina e o
  dia da semana acabam ficando em trechos diferentes.

### 4. Nenhum documento sobre prazos de prova

A task citava "prazos de prova" como exemplo de pergunta, mas nenhum dos documentos
coletados tem essa informação. As perguntas de ensaio cobrem horário de aula, regra de
carga horária e rotina.

### 5. Abrir a demo leva cerca de 30 s

A consulta leva menos de 50 ms, mas o `import` do `transformers` leva aproximadamente
25 s nesta máquina. Na apresentação, abra o modo interativo antes de começar e faça
as perguntas dentro dele.

### 6. Qdrant local e Docker são bases diferentes

A TASK-03 grava no Qdrant local (`data/qdrant`), e a TASK-02 sobe um servidor no Docker
(`localhost:6333`). A demo lê a base local por padrão, e lê o servidor só se `QDRANT_URL`
estiver definida. O time precisa escolher uma das duas. No modo local, só um processo pode
abrir a pasta por vez, então a ingestão precisa terminar antes de a demo abrir.

### 7. Dados pessoais (LGPD)

Os documentos de `data/samples/` trazem nome completo, matrícula, nome da mãe, data de
nascimento e voz de pessoas reais. Por isso, **eles não foram enviados nesta branch**. Quem
for testar precisa receber os arquivos por outro meio e colocá-los em `data/samples/`.

Atenção: o `.gitignore` do projeto libera essa pasta para versionamento, então um
`git add .` adicionaria esses documentos. Antes de fazer commit, confira o `git status`.
Sugestão para o time: tirar `data/samples/` do versionamento no `.gitignore`, ou versionar
ali só documentos sem dados pessoais.

### 8. Diferenças em relação ao enunciado

- A busca usa `client.query_points(...)` no lugar de `client.search(...)`. O `search` está
  obsoleto e foi removido nas versões recentes do `qdrant-client`. O resultado é o mesmo:
  os top-k mais próximos por cosseno.
- O arquivo de origem de Sophia foi renomeado de `IMG_5088 - Sophia Soares.jpeg` para
  `Sophia_pdf.jpeg`, seguindo o padrão `Nome_pdf.*` / `Nome_audio.*`.

## Cobertura dos documentos

| Pessoa | Grade horária | Áudio |
| --- | --- | --- |
| Antonio | PDF | — |
| Geovanna | imagem | sim |
| Hazel | imagem | — |
| Jhecy | PDF | sim |
| Julia | imagem | sim |
| Laura | — | sim |
| Mahiaara | imagem | sim |
| Milena | PDF escaneado (OCR) | sim |
| Sophia | imagem | sim |
