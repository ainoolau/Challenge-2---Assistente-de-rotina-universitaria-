# Catálogo da Base de Conhecimento Multimodal (`data/samples/`)

| Campo | Registro |
| --- | --- |
| **Frente** | F1 · Produto, UX & Requisitos (`TASK-01`) |
| **Responsável Principal** | Antônio (`@AntonioLeonardoUNB`) |
| **Par de Revisão** | Milena (`@milenamso`) |
| **Total de Documentos** | **25 documentos** (`DOC-01` a `DOC-25`) curados, padronizados e anonimizados |
| **Coleção Alvo no Qdrant** | `rotina_estudante_multimodal` |

---

## 1. Convenção de Padronização e Governança (LGPD)

1. **Padronização de Nomenclatura:** Todos os arquivos seguem nomenclatura estrita em letras minúsculas, sem espaços, caracteres especiais ou acentuação, agrupados por prefixo semântico e índice sequencial:
   - `grade_aluno_XX.<ext>` — Grades horárias e comprovantes de matrícula dos estudantes (`01` a `08`).
   - `audio_rotina_XX.<ext>` — Relatos em voz das rotinas e compromissos informais dos estudantes (`01` a `08`).
   - `edital_residencia_XX.pdf` / `edital_pibic_04.jpg` / `comunicado_monitoria_05.jpg` — Editais, regulamentos, planos de trabalho e comunicados normativos.
   - `calendario_academico_XX.<ext>` — Calendários acadêmicos oficiais de provas/recessos e quadros horários consolidados.
   - `perfis_rotina_forms.txt` — Síntese estruturada das respostas do formulário de coleta (curso, semestre, jornadas conciliadas, horas livres e gargalos).
2. **Compatibilidade com o Pipeline (`Tesseract OCR` + `Whisper` + `PyMuPDF`):**
   - Áudios gravados originalmente em `.m4a` foram convertidos para `.wav` (`16 kHz`, mono, `PCM 16-bit`), garantindo suporte direto no `Whisper` e nas extensões aceitas em `src/data_pipeline/ingestion.py` (`.ogg`, `.mp3`, `.wav`).
   - Imagens estão em `.png`, `.jpg` e `.jpeg` para leitura via `Tesseract OCR` (`--psm 6`, idioma `por`).
   - PDFs escaneados receberam camada textual pesquisável (`searchable PDF`) após o tarjamento visual.
3. **Anonimização e Conformidade LGPD:**
   - Todos os participantes assinaram o **Termo de Consentimento Livre e Esclarecido (LGPD / Uso Acadêmico)** no formulário de coleta.
   - Todos os dados pessoais identificáveis (**nomes completos, números de matrícula/RA/RGA, CPFs, filiação, datas de nascimento, endereços residenciais, e-mails pessoais, números de telefone, fotos de perfil e códigos/QR codes de validação eletrônica**) foram tarjados visualmente e removidos da camada de texto digital dos arquivos.

---

## 2. Catálogo Descritivo dos Documentos (`DOC-01` a `DOC-25`)

| Identificador | Nome do Arquivo | Modalidade | Formato | Breve Descrição do Conteúdo |
| :---: | --- | :---: | :---: | --- |
| `DOC-01` | `grade_aluno_01.pdf` | Documento / Texto (`texto`) | `PDF` | Declaração de matrícula do 6º período de Ciência de Dados e IA (IESB, semestre 2/2026), apresentando a organização das aulas noturnas de segunda, terça e sexta-feira (*Aprendizagem de Máquina*, *Projeto Integrador II* e *Amostragem Aplicada*). Nome, RA, CPF e QR code tarjados. |
| `DOC-02` | `grade_aluno_02.jpeg` | Imagem / OCR (`ocr`) | `JPEG` | Grade horária de Análise e Desenvolvimento de Sistemas (Unisinos, 2026/2), apresentando a organização semanal das disciplinas noturnas em modalidade imersiva às quartas e sextas-feiras (*Fundamentos de Redes de Computadores*, *Métricas e Gerenciamento Quantitativo de Projetos* e *Processos de Teste de Software*). |
| `DOC-03` | `grade_aluno_03.png` | Imagem / OCR (`ocr`) | `PNG` | Captura do portal acadêmico Siscad (UFMS, 2026.2) de estudante concluinte de Tecnologia da Informação (93,04% da carga horária cumprida), listando 5 disciplinas em modalidade EaD (*Comportamento Organizacional*, *Estudo de Libras* e *Projetos Integradores de TI I, II e III*). Nome e RGA tarjados. |
| `DOC-04` | `grade_aluno_04.pdf` | Documento / Texto (`texto`) | `PDF` | Comprovante de solicitação de matrícula 2026.2 no SIGAA/UnB (Engenharia de Software - FCTE Gama), detalhando as turmas solicitadas e a grade horária deferida nas manhãs de quarta e sexta-feira das 10h00 às 11h50 (*Fundamentos de Sistemas Embarcados*). Matrícula, nome e código tarjados. |
| `DOC-05` | `grade_aluno_05.jpeg` | Imagem / OCR (`ocr`) | `JPEG` | Grade horária 2026.2 no SIGAA/UnB (Ciências Econômicas), apresentando a distribuição semanal das disciplinas *Econometria* e *Microeconomia 1* (terça e quinta pela manhã), *Teoria Política Moderna* e *Contabilidade Nacional* (segunda e quarta à tarde e à noite), além de *Monitoria em Economia Quantitativa 1*. |
| `DOC-06` | `grade_aluno_06.jpg` | Imagem / OCR (`ocr`) | `JPG` | Declaração de matrícula e tabela de horários 2026.2 no SIGAA/UnB (Ciências Biológicas, 7º semestre), contendo 4 disciplinas presenciais (*Delineamento Experimental*, *Fisiologia Animal 2*, *Tópicos em Botânica 2* e *Zoologia dos Invertebrados*) e 2 atividades acadêmicas (*Estágio em Botânica* e *Pesquisa em Micologia*). Dados pessoais tarjados. |
| `DOC-07` | `grade_aluno_07.pdf` | Documento / Texto (`texto`) | `PDF` | Declaração de turmas e grade horária 2026.2 no SIGAA/UnB (Engenharia Elétrica, 12º semestre), apresentando as aulas concentradas às terças e quintas-feiras entre 10h00 e 17h50 (*Circuitos Polifásicos*, *Teoria da Informação* e *Eletromagnetismo 1*). Matrícula, nome, filiação e data de nascimento tarjados. |
| `DOC-08` | `grade_aluno_08.jpeg` | Imagem / OCR (`ocr`) | `JPEG` | Grade horária 2026.2 no SIGAA/UnB (História), apresentando a organização semanal de 5 disciplinas de terça a sábado: *Canto Coral 1* e *Prática Desportiva 1* (terça e quinta manhã), *Prática de Pesquisa Histórica* (quarta das 14h00 às 18h55), *Cinema Brasileiro* (sexta manhã) e *Promoção da Saúde 3* (sábado manhã). |
| `DOC-09` | `audio_rotina_01.ogg` | Áudio / Whisper (`audio`) | `OGG` | Relato de voz de estudante de Ciência de Dados que inicia a rotina às 06h, concilia a Residência em IA às segundas, quartas e sextas (08h–18h) com trabalho às terças e quintas (08h–17h), aulas presenciais noturnas (segunda, terça e sexta) e Iniciação Científica nas noites livres de quarta e quinta-feira. |
| `DOC-10` | `audio_rotina_02.mp3` | Áudio / Whisper (`audio`) | `MP3` | Relato de voz de estudante de ADS que acorda às 06h para cuidar dos pets, percorre 45 km de carro até o Gama para a Residência presencial às segundas e quartas (08h–18h), retorna às 19h e concilia estudos da faculdade com trabalho autônomo de tradução de roteiros e tarefas domésticas. |
| `DOC-11` | `audio_rotina_03.wav` | Áudio / Whisper (`audio`) | `WAV` | Relato de voz de estudante de TI (EaD) que inicia a rotina às 06h, concilia a Residência em IA às segundas, quartas e sextas (08h–18h) com trabalho CLT às terças e quintas (08h–18h), frequenta a academia à noite e concentra os estudos das disciplinas EaD e entregas da residência aos sábados e domingos. |
| `DOC-12` | `audio_rotina_04.wav` | Áudio / Whisper (`audio`) | `WAV` | Relato de voz de estudante de Engenharia de Software que acorda às 05h e dorme às 23h30, conciliando a Residência em IA (segunda, quarta e sexta), Iniciação Científica nos intervalos de almoço (12h–14h) e início da noite (18h–20h), trabalho CLT às terças e quintas (08h–19h), academia e aulas presenciais. |
| `DOC-13` | `audio_rotina_05.wav` | Áudio / Whisper (`audio`) | `WAV` | Relato de voz de estudante de Ciências Econômicas que dedica as manhãs livres à leitura de textos obrigatórios, assiste às aulas de *Teoria Política Moderna* e *Contabilidade Nacional* (segunda e quarta) e *Econometria* e *Microeconomia 1* (terça e quinta), realiza reuniões de orientação/monitoria à tarde e reserva a sexta-feira para estudo autônomo. |
| `DOC-14` | `audio_rotina_06.wav` | Áudio / Whisper (`audio`) | `WAV` | Relato de voz de estudante de Ciências Biológicas que concilia aulas pela manhã (segunda, terça e quinta) e quinta-feira integral (10h00 às 22h30) com estágio de PIBIC no laboratório de Botânica (segunda, quarta e sexta), estágio em segundo laboratório na terça à tarde e estudos no fim de semana divididos com cuidados familiares. |
| `DOC-15` | `audio_rotina_07.ogg` | Áudio / Whisper (`audio`) | `OGG` | Relato de voz de estudante de Engenharia Elétrica que concilia a Residência em IA às segundas e quartas-feiras (08h–18h) e sextas-feiras pela manhã (08h–12h) com a grade presencial da universidade às terças e quintas-feiras (*Circuitos Polifásicos* às 10h, *Teoria da Informação* às 14h e *Eletromagnetismo* às 16h). |
| `DOC-16` | `audio_rotina_08.wav` | Áudio / Whisper (`audio`) | `WAV` | Relato de voz de estudante de História que acorda às 06h e concilia estágio nas manhãs de segunda e quarta e nas tardes de terça e quinta com aulas presenciais na UnB (terça, quinta e sexta pela manhã e quarta à tarde), além de exercícios físicos noturnos e cuidados com a casa. |
| `DOC-17` | `edital_residencia_01.pdf` | Documento / Texto (`texto`) | `PDF` | Termo de Concessão de Bolsa de Residência em Software (Instituto Eldorado / Softex — Residência em TIC 21, 6 páginas anonimizadas), contendo as cláusulas de bolsa (8 parcelas de R$ 1.500,00), vigência (17/08/2026 a 16/04/2027), execução presencial na UnB Gama, aviso prévio de 30 dias para rescisão e propriedade intelectual. |
| `DOC-18` | `edital_residencia_02.pdf` | Documento / Texto (`texto`) | `PDF` | Regulamento e Plano de Trabalho do Programa de Residência em TIC/IA (Instituto Eldorado / Softex — Anexo II, 9 páginas anonimizadas), contendo informações sobre regras de frequência mínima presencial de **90%**, carga horária, código de conduta, regime disciplinar (desligamento com 3 advertências), uso de equipamentos e cronograma de 8 meses. |
| `DOC-19` | `edital_residencia_03.pdf` | Documento / Texto (`texto`) | `PDF` | Diretrizes Oficiais e Roadmap do Challenge 2 da Residência em IA (UnB / Eldorado / Softex, 6 páginas), apresentando a *Big Idea* (Qualidade de Vida), o *Challenge Statement*, as 5 restrições técnicas obrigatórias e o cronograma semanal de entregáveis das Semanas 1 a 7. |
| `DOC-20` | `edital_pibic_04.jpg` | Imagem / OCR (`ocr`) | `JPG` | Comprovante oficial de inscrição e participação ativa no Edital PIBIC 2026 na plataforma PLIC/UnB, vinculado ao projeto de pesquisa em Botânica (*"Anatomia comparada de acessos contrastantes de Solanum ao nematoide das lesões radiculares"*). Número de inscrição tarjado. |
| `DOC-21` | `comunicado_monitoria_05.jpg` | Imagem / OCR (`ocr`) | `JPG` | Comunicado de coordenação docente da disciplina *Introdução à Anatomia Vegetal (IAV 2026.2 - UnB)* detalhando as regras de presença obrigatória dos monitores nas aulas práticas, publicação do cronograma revisado no SIGAA e regras de revezamento na turma noturna. Nomes, fotos e telefones tarjados. |
| `DOC-22` | `calendario_academico_01.pdf` | Documento / Texto (`texto`) | `PDF` | Calendário Acadêmico Oficial do Centro Universitário IESB (Semestre 2/2026 — Outubro a Dezembro), contendo datas de lançamento da Avaliação A1 (03/10), aplicação das Avaliações F2 híbridas (16/11 a 21/11) e presenciais (23/11 a 28/11), Prova Substitutiva (05/12 a 11/12), término do semestre (12/12), revisão de menção e feriados. |
| `DOC-23` | `calendario_academico_02.pdf` | Documento / Texto (`texto`) | `PDF` | Calendário Universitário Oficial de Graduação da UnB por Atividades (Período 2026.2, 4 páginas), contendo datas de início e fim das aulas (10/08 a 14/12/2026), marcos de 25%, 50% e 75% do semestre, prazos de matrícula/rematrícula, trancamento parcial (até 09/10/2026), trancamento geral (até 12/11/2026), Semana Universitária e feriados. |
| `DOC-24` | `calendario_academico_03.png` | Imagem / OCR (`ocr`) | `PNG` | Quadro estruturado de rotina semanal completa (segunda a sexta-feira, das 06h00 às 22h30), integrando horários fixos da Residência em IA (*Daily*, *Sprint Planning*, *Hands-on*, *Tech Review*), blocos de estudo da graduação, trabalho freelance de tradução, deslocamentos de 45 km e rotina doméstica. |
| `DOC-25` | `perfis_rotina_forms.txt` | Documento / Texto (`texto`) | `TXT` | Consolidação textual estruturada e anonimizada das respostas do formulário de coleta dos 8 estudantes (`aluno_01` a `aluno_08`), registrando curso, instituição, semestre, jornadas conciliadas, disponibilidade diária de horas livres, principais gargalos de rotina e dias mais cheios da semana. |

---

## 3. Resumo de Cobertura da Base

| Modalidade no Pipeline (`task_type`) | Extrator Utilizado (`src/data_pipeline/extractors.py`) | Quantidade | Formatos |
| --- | --- | :---: | --- |
| **Documento / Texto (`texto`)** | `PyMuPDF` (`extrair_texto_pdf`) / Leitura UTF-8 (`txt`) | **10** | `9x PDF`, `1x TXT` |
| **Imagem / OCR (`ocr`)** | `Tesseract OCR` (`extrair_texto_imagem`, `lang="por"`, `--psm 6`) | **7** | `3x JPEG`, `2x JPG`, `2x PNG` |
| **Áudio / Transcrição (`audio`)** | `Whisper tiny` (`transcrever_audio`, `language="pt"`) | **8** | `5x WAV`, `2x OGG`, `1x MP3` |
| **Total Geral** | — | **25 documentos** | Mínimo exigido na `TASK-01`: 20 documentos |
