# Assistente de Rotina e Gestão de Tempo

Assistente inteligente para universitários em multijornada (faculdade, trabalho, residência/projetos e estudo autônomo).

## Stack Principal
- Python 3.11
- FastAPI (Backend e APIs)
- MLflow (Tracking e MLOps)
- Pytest & Ruff (Qualidade e Testes)
﻿# Assistente de Rotina e Gestão de Tempo

## TASK-03 - Pipeline de Ingestão Multimodal

### O que é?

A **ingestão multimodal** permite receber e processar informações de diferentes formatos, como imagens, áudios e documentos textuais.

Nesta tarefa, desenvolvemos um pipeline que extrai o conteúdo desses arquivos, divide o texto em blocos menores e o transforma em vetores numéricos, que são armazenados para consultas futuras pelos agentes de inteligência artificial.

**Fluxo do processamento:**

Documentos → Extração do texto → Chunking → Embeddings → Qdrant

- **Chunking:** divisão do texto em blocos de até 500 caracteres, com sobreposição de 50 caracteres.
- **Embeddings:** representações numéricas dos textos, com 384 dimensões.
- **Qdrant:** banco de dados vetorial que armazena os embeddings e os metadados dos documentos.
  
**Formatos aceitos:** .png, .jpg, .jpeg, .ogg, .mp3, .wav, .pdf, .docx e .txt.

---
**Exemplo de aplicação:**

Um estudante envia uma imagem da grade de horários da universidade.

O sistema deverá:
1. Ler o texto presente na imagem.
2. Identificar as informações extraídas.
3. Dividir o texto em blocos menores, quando necessário.
4. Transformar esses blocos em vetores numéricos.
5. Armazenar os vetores e suas informações de origem.
6. Permitir que outros componentes do sistema consultem posteriormente essas informações.
---

### Tecnologias utilizadas

| Tecnologia | Função |
|---|---|
| Python versão 3.13 | Linguagem utilizada no desenvolvimento. |
| Tesseract OCR | Reconhece textos presentes em imagens. |
| Whisper tiny | Transcreve áudios para texto. |
| PyMuPDF | Extrai textos de PDFs. |
| python-docx | Lê documentos Word .docx. |
| Sentence Transformers | Gera embeddings. |
| all-MiniLM-L6-v2 | Modelo que produz os vetores. |
| Qdrant | Banco de dados vetorial. |

### Organização dos arquivos
```text
Challenge-2-Equipe/
├── executar_ingestao.py   # Inicia o pipeline pelo botão
├── README.md
├── requirements.txt
├── data/
│   └── samples/           # Documentos de entrada
└── src/
    └── data_pipeline/
        ├── extractors.py  # Extrai o conteúdo dos arquivos
        └── ingestion.py   # Gera embeddings e armazena no Qdrant
```

### Testes e próximas etapas

O pipeline foi testado inicialmente com quatro documentos (imagem, áudio, PDF e Word), sem falhas. A reexecução também não gerou novos pontos duplicados na coleção de teste.

**Pendências:**

- [ ] Validar a ingestão dos 20 documentos da equipe.
- [ ] Conferir a qualidade dos textos extraídos e dos embeddings.

### Execução do pipeline

O código da TASK-03 está localizado em `src/data_pipeline/`.

O arquivo `extractors.py` contém as funções de extração de conteúdo, enquanto o `ingestion.py` organiza as etapas de processamento e armazenamento.

Os documentos de entrada devem ser colocados na pasta `data/samples/`.

**Observação:** o pipeline utiliza Tesseract OCR e FFmpeg, que precisam estar instalados no computador, além das bibliotecas Python presentes no `requirements.txt`.
