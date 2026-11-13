# Relatório Técnico de Execução
## Cenário 3 — Naive RAG + LLM

**Arquivos relacionados:**
- Código: `scripts/scenarios/naive_rag.py`
- Resultados: `reports/scenarios/naive_rag_results.json`
- Esquema de validação: `tests/benchmark_result_schema.json`
- Versões: `contract_version: 1.0.0` e `golden_set_version: 1.0.0`

---

## 1. Visão geral

O objetivo do **Cenário 3 (`naive_rag`)** foi avaliar um sistema de geração de respostas que consulta documentos antes de acionar um modelo de linguagem, mas **sem uma camada de bloqueio de perguntas pouco relevantes**.

Essa abordagem é conhecida como **RAG (Retrieval-Augmented Generation)**: o sistema recupera trechos da base de conhecimento e os fornece ao modelo de linguagem (LLM), que tenta responder com base nesses materiais.

Neste cenário, todas as perguntas são encaminhadas à LLM, mesmo quando a busca encontra apenas conteúdos pouco relacionados. A decisão de responder ou se abster depende das instruções do prompt e da análise feita pelo próprio modelo.

### Principais resultados

- **12 consultas executadas:** todas concluídas com `status: success`.
- **12 chamadas à LLM:** incluindo a única pergunta fora do domínio da base.
- **5 abstenções registradas:** o modelo optou por não responder às consultas GS-01, GS-05, GS-06, GS-11 e GS-12.
- **9.274 tokens consumidos:** 8.380 de entrada e 894 de saída, segundo o consolidado registrado.
- **Tempo médio de resposta informado:** aproximadamente 2,52 segundos por consulta.
- **Problemas identificados:** uma citação de arquivo escrita incorretamente e uma resposta com informações misturadas de perfis diferentes.

O Cenário 3 é importante como **referência de comparação (baseline)** para avaliar o que muda ao adicionar a camada de proteção do Cenário 4 (`guardrail_rag`).

---

## 2. Configuração do cenário

O experimento utiliza a busca vetorial construída na Sprint 2, disponível em `src/data_pipeline/retrieval.py`, conectada diretamente ao modelo de linguagem pelo provedor Groq.

### 2.1. Tecnologias e parâmetros

| Componente | Configuração |
|---|---|
| Banco de dados vetorial | Qdrant |
| Coleção utilizada | `rotina_estudante_multimodal` |
| Quantidade de trechos armazenados | 162 chunks |
| Método de comparação | Similaridade de cosseno |
| Modelo de embeddings | `paraphrase-multilingual-MiniLM-L12-v2` |
| Dimensão dos embeddings | 384 |
| Quantidade de trechos recuperados | Top-3 |
| Guardrail | `null` (sem bloqueio pré-LLM) |
| Provedor da LLM | Groq |
| Modelo de linguagem | `openai/gpt-oss-20b` |
| Esforço de raciocínio | `reasoning_effort="low"` |
| Temperatura | `0.0` |
| Limite de tokens de saída | `768` |
| Template de prompt | `rag_v1` |

### 2.2. Como funciona o Naive RAG?

O fluxo de cada consulta é:

1. O usuário envia uma pergunta.
2. O sistema transforma a pergunta em uma representação numérica, chamada **embedding**.
3. O Qdrant identifica os três trechos de documentos mais próximos da pergunta (**Top-3**).
4. Esses trechos são enviados ao modelo de linguagem com o prompt `rag_v1`.
5. O modelo tenta gerar uma resposta fundamentada ou informa que não existem evidências suficientes.

**Diferença essencial:** não há uma verificação de relevância capaz de interromper a chamada à LLM antes da geração. Mesmo uma pergunta fora do contexto chega ao modelo.

### 2.3. Conceitos importantes

- **Chunk:** fragmento de um documento armazenado para facilitar a busca.
- **Score de similaridade:** pontuação que indica o quanto um trecho recuperado se aproxima semanticamente da pergunta. Um score alto ajuda a identificar textos relacionados, mas não garante que contenham a resposta exata.
- **Abstenção:** situação em que o sistema informa não ter evidências suficientes para responder.
- **Tokens:** unidades de texto processadas pelo modelo, usadas para acompanhar o consumo de recursos.

---

## 3. Resultados dos testes

Foram avaliadas 12 consultas, identificadas de GS-01 a GS-12, envolvendo PDFs, imagens interpretadas por OCR, informações provenientes de áudio transcrito pelo Whisper e uma pergunta fora do domínio.

### 3.1. Resultados por consulta

| Consulta | Tipo de conteúdo | Similaridade | LLM acionada? | Abstenção? | Tokens (entrada + saída) | Tempo total |
|---|---|---:|---|---|---:|---:|
| GS-01 | PDF | 0,6404 | Sim | Sim | 681 + 33 | 2.572,25 ms |
| GS-02 | PDF | 0,6449 | Sim | Não | 694 + 79 | 2.658,27 ms |
| GS-03 | PDF | 0,7480 | Sim | Não | 632 + 52 | 2.422,95 ms |
| GS-04 | PDF | 0,6328 | Sim | Não | 663 + 168 | 2.529,92 ms |
| GS-05 | PDF | 0,6148 | Sim | Sim | 796 + 43 | 2.672,08 ms |
| GS-06 | PDF | 0,6732 | Sim | Sim | 671 + 47 | 2.583,30 ms |
| GS-07 | Imagem (OCR) | 0,6579 | Sim | Não | 685 + 75 | 2.546,67 ms |
| GS-08 | Imagem (OCR) | 0,5203 | Sim | Não | 718 + 80 | 2.485,01 ms |
| GS-09 | Áudio (Whisper) | 0,6621 | Sim | Não | 777 + 78 | 2.435,85 ms |
| GS-10 | Áudio (Whisper) | 0,6389 | Sim | Não | 748 + 103 | 2.422,56 ms |
| GS-11 | Áudio (Whisper) | 0,6704 | Sim | Sim | 783 + 62 | 2.491,05 ms |
| **GS-12** | **Fora de domínio** | **0,4328** | **Sim** | **Sim** | **612 + 34** | **2.397,57 ms** |

**Leitura dos resultados:** todas as 12 perguntas acionaram a LLM. Em cinco delas, o sistema registrou abstenção, mas isso só aconteceu **depois** de a chamada ao modelo ter sido feita.

### 3.2. Fontes registradas em cada consulta

| Consulta | Fontes registradas | Observação |
|---|---|---|
| GS-01 | Nenhuma (`[]`) | Abstenção pelo prompt |
| GS-02 | `edital_residencia_02.pdf` | Fonte válida |
| GS-03 | `edital_residencia_02.pdf` | Fonte válida |
| GS-04 | `edital_residencia_02.pdf` | Fonte válida |
| GS-05 | Nenhuma (`[]`) | Abstenção pelo prompt |
| GS-06 | Nenhuma (`[]`) | Abstenção pelo prompt |
| GS-07 | `grade_aluno_06.jpg` | Fonte válida |
| GS-08 | `comunicado_monitoria_05.jpg` | Fonte válida |
| GS-09 | Nenhuma (`[]`) | Nome de arquivo citado incorretamente pelo modelo |
| GS-10 | `perfis_rotina_forms.txt` | Fonte válida, mas houve mistura de contexto na resposta |
| GS-11 | Nenhuma (`[]`) | Abstenção pelo prompt |
| GS-12 | Nenhuma (`[]`) | Abstenção em pergunta fora do domínio |

**Observação:** uma fonte registrada como válida não garante, por si só, que a resposta esteja correta. A consulta GS-10, por exemplo, teve uma fonte reconhecida, mas apresentou um erro de interpretação do contexto.

---

## 4. Análise de desempenho

### 4.1. Chamadas ao modelo e abstenções

O sistema acionou a LLM em **100% das consultas (12 de 12)**, inclusive na GS-12, que estava fora do domínio.

O modelo registrou abstenção em **5 das 12 perguntas (41,67%)**. Isso indica que as instruções do prompt `rag_v1` conseguem levar o modelo a reconhecer a falta de evidências em alguns casos.

Entretanto, essa proteção funciona **após** o envio da consulta ao modelo. Assim, mesmo quando o resultado é uma recusa, há consumo de tokens e tempo de geração.

### 4.2. Consumo de tokens

| Métrica | Quantidade informada |
|---|---:|
| Tokens de entrada | 8.380 |
| Tokens de saída | 894 |
| **Total** | **9.274** |
| Chamadas à LLM | 12 |

A configuração `reasoning_effort="low"` foi utilizada para limitar o esforço de raciocínio do modelo. O relatório da execução registra uma média de aproximadamente **74,5 tokens de saída por consulta**, permitindo respostas relativamente curtas.

O menor consumo de tokens de saída **não significa necessariamente maior qualidade**. A avaliação também precisa considerar a exatidão das respostas, a fundamentação documental e a presença de abstenções ou citações incorretas.

### 4.3. Tempo de resposta

| Métrica | Valor informado |
|---|---:|
| Latência média total | 2.518,12 ms |
| Tempo médio de recuperação (retrieval) | Aproximadamente 2.085 ms |
| Tempo médio de geração | Aproximadamente 442 ms |

O tempo de recuperação dos documentos representa a maior parte da latência observada.

Na consulta GS-12, mesmo sem informações relevantes para responder, o sistema ainda consumiu **612 tokens de entrada, 34 de saída e 347,79 ms de geração**. Esses recursos poderiam ter sido economizados caso existisse um bloqueio anterior à LLM.

**Nota de conferência:** os valores agregados desta seção foram preservados conforme o relatório fornecido. Antes da publicação definitiva, vale reconciliá-los com o JSON da execução, pois a soma dos tokens de entrada exibidos nas 12 linhas é **8.460**, e não 8.380; a soma dos tokens de saída exibidos é **854**, e não 894. Além disso, a média aritmética dos tempos individuais exibidos é de aproximadamente **2.518,96 ms**, em vez de 2.518,12 ms.

---

## 5. Comportamentos e problemas identificados

### 5.1. A pergunta fora do domínio ainda acionou a LLM

**Consulta analisada: GS-12**

A consulta GS-12 recebeu score de similaridade de **0,4328**, indicando baixa relação com os conteúdos armazenados.

Como o Naive RAG não possui um limite mínimo para interromper o fluxo, a pergunta foi encaminhada normalmente ao modelo. Ele acabou se abstendo, mas somente depois de processar a solicitação.

**Impacto:** o sistema evitou uma resposta sem fundamento, porém realizou uma chamada desnecessária à API.

### 5.2. Erro no nome de um documento citado

**Consulta analisada: GS-09**

O modelo apresentou a informação esperada sobre o horário da aula de Econometria, mas escreveu o nome do arquivo citado de forma incorreta:

- Nome gerado: `perfils_rotina_forms.txt`
- Nome correto: `perfis_rotina_forms.txt`

O validador de fontes identificou a diferença e não aceitou essa referência, registrando `sources: []`.

**Impacto:** mesmo quando a informação principal está correta, uma citação inexistente reduz a rastreabilidade da resposta. O validador evitou que a referência incorreta fosse registrada como fonte válida, mas não impediu o erro de aparecer no texto produzido.

### 5.3. Mistura de informações entre perfis de estudantes

**Consulta analisada: GS-10**

Nessa pergunta, os três trechos recuperados pertenciam a perfis diferentes de estudantes.

O modelo acabou associando ao estudante de TI um horário de residência ou trabalho como se fosse o horário de academia.

Esse tipo de erro ocorre quando informações de pessoas ou seções diferentes aparecem próximas, sem identificação suficientemente clara.

**Impacto:** o sistema pode gerar uma resposta aparentemente coerente, mas baseada em uma combinação incorreta de dados.

O problema reforça a necessidade de dividir os documentos por perfil de estudante e preservar identificadores em cada trecho recuperado.

### 5.4. Abstenções em perguntas relacionadas à base

**Consultas analisadas: GS-01, GS-05, GS-06 e GS-11**

Nessas quatro consultas relacionadas ao domínio do projeto, o modelo optou por não responder.

Isso é preferível a inventar informações quando não há evidências suficientes no contexto recuperado. Por outro lado, pode indicar que documentos relevantes não foram apresentados de forma completa ao modelo.

Esse resultado merece investigação na etapa de recuperação: uma pergunta pode ser válida e, ainda assim, não receber resposta porque o fragmento selecionado não contém o trecho necessário.

---

## 6. Comparação com o Cenário 4 — RAG com Guardrail

O Cenário 3 fornece uma referência para avaliar a adição de uma camada de proteção pré-LLM no Cenário 4.

| Aspecto | Cenário 3 — Naive RAG | Cenário 4 — Guardrail RAG |
|---|---|---|
| Verificação de similaridade antes da LLM | Não | Sim, limite de 0,50 |
| Chamadas à LLM | 12 de 12 | 11 de 12 |
| Tratamento da consulta GS-12 | Enviada à LLM, que se absteve | Bloqueada antes da LLM |
| Tokens consumidos em GS-12 | 612 de entrada + 34 de saída | 0 |
| Tempo de geração em GS-12 | 347,79 ms | Nenhuma geração |
| Possibilidade de abstenção pelo prompt | Sim | Sim |
| Busca inicial | Top-3 | Top-3 |

### 6.1. Principal ganho observado

Na consulta fora de domínio (GS-12), o Cenário 4 impediu a chamada que o Cenário 3 realizou.

Isso representa uma economia direta de **646 tokens e 347,79 ms de geração naquela consulta**, conforme os resultados apresentados.

### 6.2. Limites da comparação

Os dois cenários não utilizaram exatamente a mesma configuração de geração:

- Cenário 3: temperatura `0.0`, limite de `768` tokens de saída e `reasoning_effort="low"`.
- Cenário 4: temperatura `0.1` e limite de `2048` tokens de saída.

Por isso, **não é adequado atribuir diferenças globais de consumo de tokens, latência ou extensão das respostas exclusivamente à presença do guardrail**. A comparação mais direta é o comportamento da GS-12, na qual o bloqueio pré-LLM explica a ausência de geração no Cenário 4.

---

## 7. Recomendações para evolução

### 7.1. Adicionar uma verificação pré-LLM

Implementar um limite mínimo de similaridade, como o testado no Cenário 4, para evitar chamadas em perguntas claramente desconectadas da base.

**Benefício esperado:** reduzir chamadas desnecessárias, consumo de tokens e risco de respostas fora do domínio.

### 7.2. Melhorar a divisão dos documentos

Substituir a divisão exclusivamente por tamanho fixo por uma estratégia que respeite a estrutura do conteúdo:

- Separar formulários por perfil de estudante.
- Preservar linhas de tabelas e cláusulas completas.
- Manter títulos e identificadores associados a cada fragmento.

**Benefício esperado:** reduzir erros como o da GS-10 e melhorar a recuperação de evidências necessárias para responder a perguntas válidas.

### 7.3. Fortalecer o controle de fontes

Manter a validação estrita dos nomes de arquivos e considerar a construção das citações a partir dos metadados de recuperação, em vez de depender apenas dos nomes escritos livremente pelo modelo.

**Benefício esperado:** evitar referências inexistentes e aumentar a rastreabilidade das respostas.

### 7.4. Ampliar os testes de qualidade

Adicionar casos que verifiquem separadamente:

- Se a pergunta está dentro ou fora do domínio.
- Se o documento correto foi recuperado.
- Se a informação necessária estava presente no trecho enviado à LLM.
- Se a resposta final está correta e devidamente fundamentada.
- Se a abstenção foi apropriada.

**Benefício esperado:** distinguir problemas na busca de documentos de problemas na geração das respostas.

---

## 8. Conclusão

O **Cenário 3 (`naive_rag`)** foi implementado e executado com sucesso, atendendo ao esquema de resultados definido para o benchmark da Sprint 3.

Os testes demonstraram que o pipeline é capaz de recuperar trechos e encaminhá-los ao modelo de linguagem, que pode gerar respostas ou se abster quando não encontra evidências suficientes.

Entretanto, também foram identificadas limitações importantes:

- Todas as consultas acionam a LLM, mesmo quando a relevância dos documentos é baixa.
- O modelo pode produzir nomes de fontes incorretos.
- Trechos de perfis diferentes podem ser combinados de maneira equivocada.
- Algumas perguntas válidas não recebem resposta por falta de contexto suficiente nos fragmentos recuperados.

**Recomendação para o projeto Vezo:** utilizar o Naive RAG como **baseline de comparação**, e não como a arquitetura final preferencial. Os resultados dão suporte à evolução para um RAG com guardrail, acompanhada de melhorias na preparação dos documentos, na recuperação de contexto e na validação das fontes.

A consolidação da `TASK-S3-05` deverá considerar tanto a segurança e a economia de chamadas quanto a qualidade efetiva das respostas produzidas.
