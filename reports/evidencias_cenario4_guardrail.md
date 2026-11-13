# Relatório Técnico de Execução — Cenário 4: RAG Avançado com Guardrail

**Projeto:** Vezo — Benchmark Comparativo entre LLM e RAG  
**Sprint:** 3  
**Task:** `TASK-S3-04` (Issue #22)  
**Epic:** `EPIC-S3-01` — Benchmark Comparativo e Decisão de Arquitetura: LLM vs. RAG  
**Responsável:** Hazel

**Arquivos relacionados:**

- Código: `scripts/scenarios/guardrail_rag.py`
- Resultados: `reports/scenarios/guardrail_rag_results.json`

---

## 1. Visão Geral

O objetivo do Cenário 4 foi avaliar uma versão mais segura do sistema RAG (*Retrieval-Augmented Generation*) desenvolvido para o assistente Vezo.

O RAG funciona buscando informações em documentos antes de gerar uma resposta com inteligência artificial. Dessa forma, o modelo utiliza informações recuperadas da base de conhecimento, em vez de depender apenas do que aprendeu durante seu treinamento.

Neste cenário, adicionamos uma camada de proteção chamada **guardrail**, responsável por verificar se os documentos encontrados são suficientemente relevantes para responder à pergunta do usuário.

A ideia é simples: **se o sistema não encontrar informações relacionadas à pergunta, ele não deve tentar inventar uma resposta.**

Essa verificação acontece antes de chamar o modelo de linguagem (LLM), permitindo evitar respostas fora do contexto e reduzir o consumo desnecessário de recursos.

### 1.1. Principais resultados

Durante a execução, foram realizadas 12 consultas, sendo 11 relacionadas ao conteúdo disponível na base de conhecimento e uma propositalmente fora do domínio do projeto.

- **12 consultas avaliadas:** 11 relacionadas à base e uma fora do domínio.
- **11 consultas liberadas:** todas as perguntas relacionadas ao conteúdo passaram pela verificação inicial.
- **1 consulta bloqueada:** a pergunta fora do domínio foi identificada corretamente.
- **Nenhum bloqueio indevido:** o guardrail não impediu nenhuma das 11 perguntas válidas de chegar ao modelo.
- **Economia de recursos:** a consulta bloqueada não consumiu tokens de geração de resposta.

Os resultados demonstram que, no conjunto avaliado, o guardrail conseguiu distinguir as perguntas relacionadas ao projeto daquela que não possuía relação suficiente com a base de conhecimento.

Também foram identificadas oportunidades de melhoria na forma como os documentos são divididos e recuperados.

---

## 2. Configuração do Cenário

O Cenário 4 aproveita a estrutura de busca vetorial desenvolvida durante a Sprint 2, adicionando uma verificação de relevância antes da geração das respostas.

### 2.1. Tecnologias e parâmetros utilizados

| Componente | Configuração |
| --- | --- |
| Banco de dados vetorial | Qdrant |
| Coleção utilizada | `rotina_estudante_multimodal` |
| Quantidade de trechos armazenados | 162 chunks |
| Método de comparação | Similaridade de cosseno |
| Modelo de embeddings | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` |
| Dimensão dos embeddings | 384 |
| Quantidade de trechos recuperados | Top-3 |
| Limite mínimo de relevância | 0,50 |
| Provedor da LLM | Groq |
| Modelo de linguagem | `openai/gpt-oss-20b` |
| Temperatura | 0,1 |
| Limite de tokens de saída | 2048 |
| Template de prompt | `rag_v1` |

### 2.2. Como funciona o guardrail?

Antes de explicar o funcionamento, é importante entender dois conceitos:

**Embeddings:** são representações numéricas dos textos que permitem comparar o significado de diferentes conteúdos. Isso ajuda o sistema a encontrar informações relacionadas a uma pergunta, mesmo quando as palavras utilizadas não são exatamente iguais.

**Score de similaridade:** é a pontuação usada para representar o quanto um trecho recuperado está semanticamente relacionado à pergunta.

Neste experimento, utilizamos um limite mínimo de similaridade de **0,50**.

O funcionamento segue estas etapas:

1. O usuário envia uma pergunta ao assistente.
2. O sistema pesquisa os documentos armazenados no Qdrant.
3. São recuperados os três trechos considerados mais relevantes (Top-3).
4. O guardrail verifica a pontuação do trecho mais relevante.
5. Se a pontuação for igual ou superior a 0,50, a pergunta é encaminhada ao modelo de linguagem.
6. Se a pontuação for inferior a 0,50, a pergunta é bloqueada antes da geração.

Em outras palavras:

- **Score ≥ 0,50:** a pergunta pode ser encaminhada à LLM com os documentos recuperados.
- **Score < 0,50:** o sistema considera que não existe relação suficiente com a base e evita chamar a LLM.

Passar pelo guardrail **não garante que a resposta esteja presente** nos trechos encontrados. Essa decisão apenas indica que existe uma relação semântica mínima entre a pergunta e o conteúdo recuperado.

O modelo ainda precisa verificar se as informações disponíveis são suficientes para formular uma resposta confiável.

---

## 3. Resultados dos Testes

Foram realizadas 12 consultas, identificadas de `GS-01` a `GS-12`.

Os testes incluíram informações provenientes de diferentes tipos de documentos:

- **PDF:** editais, calendários e outros documentos textuais.
- **Imagem com OCR:** informações extraídas de imagens, fotografias e capturas de tela.
- **Áudio com Whisper:** informações obtidas por meio de transcrições de áudio.
- **Fora de domínio:** uma pergunta sem relação suficiente com o conteúdo disponível.

### 3.1. Resultados por consulta

| Consulta | Tipo de conteúdo | Similaridade | Decisão | Tokens (entrada + saída) | Tempo total |
| --- | --- | ---: | --- | ---: | ---: |
| GS-01 | PDF | 0,6404 | Liberada | 707 + 580 | 3.712,85 ms |
| GS-02 | PDF | 0,6449 | Liberada | 721 + 219 | 2.654,26 ms |
| GS-03 | PDF | 0,7480 | Liberada | 659 + 219 | 2.867,36 ms |
| GS-04 | PDF | 0,6328 | Liberada | 690 + 322 | 2.967,50 ms |
| GS-05 | PDF | 0,6148 | Liberada | 823 + 446 | 2.973,65 ms |
| GS-06 | PDF | 0,6732 | Liberada | 698 + 237 | 2.669,92 ms |
| GS-07 | Imagem (OCR) | 0,6579 | Liberada | 712 + 229 | 2.755,80 ms |
| GS-08 | Imagem (OCR) | 0,5203 | Liberada | 745 + 462 | 3.069,01 ms |
| GS-09 | Áudio (Whisper) | 0,6621 | Liberada | 803 + 378 | 3.035,25 ms |
| GS-10 | Áudio (Whisper) | 0,6389 | Liberada | 775 + 415 | 2.851,94 ms |
| GS-11 | Áudio (Whisper) | 0,6704 | Liberada | 810 + 1158 | 6.914,41 ms |
| **GS-12** | **Fora de domínio** | **0,4328** | **Bloqueada** | **0 + 0** | **2.081,90 ms** |

Todas as 11 consultas relacionadas à base de conhecimento foram encaminhadas à LLM. A consulta `GS-12` foi bloqueada antes dessa etapa.

### 3.2. Documentos recuperados

A tabela abaixo apresenta os arquivos registrados como fontes durante cada consulta.

| Consulta | Documentos recuperados |
| --- | --- |
| GS-01 | `perfis_rotina_forms.txt` |
| GS-02 | `edital_residencia_02.pdf`, `edital_residencia_01.pdf` |
| GS-03 | `edital_residencia_02.pdf` |
| GS-04 | `edital_residencia_02.pdf` |
| GS-05 | `calendario_academico_02.pdf` |
| GS-06 | `edital_residencia_02.pdf`, `edital_residencia_01.pdf` |
| GS-07 | `grade_aluno_06.jpg` |
| GS-08 | `comunicado_monitoria_05.jpg`, `grade_aluno_06.jpg`, `edital_residencia_02.pdf` |
| GS-09 | `perfis_rotina_forms.txt` |
| GS-10 | `perfis_rotina_forms.txt` |
| GS-11 | `perfis_rotina_forms.txt` |
| GS-12 | Nenhuma fonte utilizada na resposta |

**Observação:** os documentos listados representam as fontes registradas no resultado de cada consulta. Isso não significa necessariamente que todas as informações necessárias para responder estavam presentes nos trechos efetivamente enviados ao modelo.

---

## 4. Análise de Desempenho

Além de verificar se o guardrail funcionava corretamente, avaliamos o consumo de tokens e o tempo necessário para processar cada pergunta.

### 4.1. Taxa de liberação e bloqueio

Das 12 consultas realizadas:

- **11 foram liberadas:** 91,67% do total.
- **1 foi bloqueada:** 8,33% do total.

Todas as perguntas relacionadas à base de conhecimento passaram pelo guardrail, enquanto a única pergunta fora do domínio foi bloqueada.

Portanto, dentro do conjunto avaliado:

- **Taxa de liberação das consultas válidas:** 100%.
- **Taxa de bloqueio das consultas fora de domínio:** 100%.
- **Bloqueios indevidos:** nenhum.

Embora os resultados tenham sido positivos, apenas uma pergunta fora do domínio foi testada. Portanto, o resultado de 100% representa o desempenho observado neste conjunto específico, e não uma garantia de que todas as perguntas irrelevantes serão bloqueadas.

### 4.2. Consumo de tokens

| Tipo | Quantidade |
| --- | ---: |
| Tokens de entrada | 8.143 |
| Tokens de saída | 4.665 |
| **Total** | **12.808** |
| Tokens na consulta bloqueada | 0 |

Tokens são unidades de texto processadas pelo modelo e influenciam tanto o consumo de recursos quanto o custo de utilização da API.

Na consulta `GS-12`, o guardrail identificou a baixa relevância antes da chamada à LLM. Como resultado, não houve consumo de tokens de entrada ou saída para geração de resposta.

Esse comportamento é relevante principalmente em aplicações com grande volume de usuários, nas quais perguntas fora de contexto podem gerar chamadas desnecessárias ao modelo.

### 4.3. Tempo de resposta

A latência representa o tempo necessário para o sistema processar uma consulta e retornar seu resultado.

| Etapa | Tempo médio informado |
| --- | ---: |
| Recuperação de informações | Aproximadamente 2.075 ms |
| Geração da resposta | Aproximadamente 1.240 ms |
| Tempo médio total das consultas liberadas | 3.315,63 ms |
| Tempo da consulta bloqueada (`GS-12`) | 2.081,90 ms |

Na consulta bloqueada, o sistema realizou a busca e a análise de relevância, mas não precisou executar a etapa de geração. Isso elimina o tempo e o consumo de tokens dessa etapa, embora a consulta ainda tenha custo de processamento relacionado à busca vetorial.

**Nota de conferência:** o valor agregado informado para a latência média das consultas liberadas é de 3.315,63 ms. Entretanto, a média aritmética dos 11 tempos individuais apresentados na tabela é de aproximadamente 3.315,99 ms. A pequena diferença deve ser conferida no arquivo JSON original antes da publicação definitiva.

---

## 5. Análise dos Comportamentos Observados

A execução mostrou que o sistema consegue atuar em dois níveis diferentes para evitar respostas sem fundamentação.

### 5.1. Primeiro nível: bloqueio antes da LLM

**Consulta analisada:** `GS-12`.

A consulta `GS-12` foi criada para testar o comportamento do sistema diante de uma pergunta fora do domínio.

Ela recebeu uma pontuação de similaridade de **0,4328**, inferior ao limite configurado de 0,50. Por esse motivo, o guardrail impediu a chamada ao modelo de linguagem.

O resultado foi o comportamento esperado:

- A pergunta não foi encaminhada à LLM.
- Nenhum token de geração foi consumido.
- O sistema retornou a mensagem de abstenção configurada.

Esse teste demonstra que é possível evitar determinadas respostas fora de contexto antes mesmo da etapa de geração.

### 5.2. Segundo nível: recusa por falta de informação suficiente

**Consultas analisadas:** `GS-05`, `GS-06` e `GS-08`.

Nessas três consultas, a busca vetorial encontrou documentos relacionados às perguntas, e todas ultrapassaram o limite mínimo de similaridade.

Entretanto, os trechos recuperados não continham todas as informações necessárias para elaborar uma resposta precisa. Isso aconteceu porque alguns documentos foram divididos em fragmentos que acabaram separando informações importantes, como partes de tabelas ou cláusulas de editais.

Nessas situações, o modelo seguiu as instruções do prompt `rag_v1` e respondeu:

> Não há evidência suficiente nos documentos.

Esse comportamento é importante porque demonstra que o sistema não depende apenas do guardrail para evitar informações inventadas. Mesmo quando uma pergunta passa pela primeira verificação, o modelo ainda pode reconhecer que não possui evidências suficientes para responder.

Por outro lado, essas recusas também mostram que existe um problema na recuperação dos documentos: em alguns casos, a informação pode existir na base, mas não chegar ao modelo de maneira completa.

### 5.3. Diferença entre segurança e capacidade de resposta

Os resultados mostram dois aspectos que precisam ser avaliados separadamente:

- **Segurança:** o sistema deve evitar responder quando não possui informações confiáveis.
- **Capacidade de resposta:** o sistema deve conseguir localizar e utilizar corretamente as informações que existem na base.

No Cenário 4, o guardrail apresentou o comportamento esperado de segurança. Entretanto, as consultas `GS-05`, `GS-06` e `GS-08` demonstram que a recuperação de informações ainda pode ser aprimorada.

Assim, o objetivo das próximas melhorias não é simplesmente fazer o modelo responder mais perguntas, mas garantir que ele tenha acesso ao contexto correto para responder com segurança.

---

## 6. Ajuste no Limite de Tokens

Durante o desenvolvimento do cenário, também foi necessário ajustar a configuração de geração do modelo `openai/gpt-oss-20b`.

Inicialmente, o limite máximo de saída estava configurado para 512 tokens. Entretanto, esse modelo utiliza mecanismos internos de raciocínio, o que pode aumentar a quantidade de tokens necessária para concluir uma resposta.

Com o limite inicial, algumas respostas apresentavam problemas de truncamento, ou seja, eram interrompidas antes de serem concluídas.

Para resolver esse problema, o limite foi aumentado para **2048 tokens**.

O ajuste permitiu acomodar respostas mais longas, como a da consulta `GS-11`, que utilizou 1158 tokens de saída. Após a alteração, não foram observados os truncamentos identificados anteriormente nos testes relatados.

Esse resultado reforça a importância de configurar o limite de saída de acordo com as características do modelo utilizado.

---

## 7. Problemas Identificados na Recuperação de Informações

A análise dos resultados mostrou que a principal oportunidade de melhoria está na forma como os documentos foram divididos e armazenados durante a Sprint 2.

Atualmente, a base possui **162 chunks**, que são pequenos fragmentos de texto utilizados pelo sistema durante as buscas.

Essa divisão é necessária porque documentos muito longos não são ideais para recuperação direta. Entretanto, quando o corte é realizado apenas por tamanho fixo, informações relacionadas podem acabar separadas.

### 7.1. Fragmentação de tabelas e cláusulas

**Consultas relacionadas:** `GS-05` e `GS-06`.

Algumas informações estavam organizadas em tabelas de calendários acadêmicos ou em cláusulas de editais. Durante a divisão dos documentos, partes dessas estruturas foram separadas.

Isso fez com que o sistema encontrasse o documento correto, mas recuperasse apenas uma parte da informação necessária.

**Exemplo simplificado:** imagine uma tabela com uma atividade e sua respectiva data. Se o documento for dividido entre o nome da atividade e a data correspondente, o sistema pode encontrar apenas um desses elementos.

Nesse caso, a busca identifica corretamente o assunto, mas o modelo não recebe o contexto suficiente para responder à pergunta.

### 7.2. Perda de contexto em documentos longos

**Consulta relacionada:** `GS-01`.

Outro problema observado foi a ausência de informações de identificação em alguns trechos recuperados.

No arquivo `perfis_rotina_forms.txt`, por exemplo, determinados fragmentos não apresentavam o nome do estudante ou a seção à qual pertenciam. Isso dificulta a interpretação dos dados, porque o modelo pode receber uma informação sem saber exatamente a quem ela se refere.

Além disso, alguns trechos de tabelas extraídas por OCR, como os do arquivo `calendario_academico_03.png`, competiram nas pontuações de similaridade com conteúdos mais relevantes.

Esse comportamento indica que a organização dos documentos influencia diretamente a qualidade das buscas.

### 7.3. Limitações da divisão atual

Os problemas identificados não indicam necessariamente uma falha do modelo de linguagem.

Em diversas situações, a dificuldade aparece antes da geração da resposta, quando o sistema seleciona os documentos que serão enviados ao modelo.

Por isso, melhorar apenas o prompt ou trocar a LLM não resolveria completamente a situação. O ajuste prioritário deve ocorrer na preparação e na recuperação dos documentos.

---

## 8. Avaliação do Fine-Tuning de Embeddings

Também foram realizados experimentos preliminares de adaptação do modelo de embeddings ao domínio do projeto.

Essa técnica, conhecida como *fine-tuning*, consiste em realizar um treinamento adicional para que o modelo represente melhor determinados tipos de conteúdo.

Nos testes preliminares, foi utilizada uma abordagem baseada em **Triplet Loss**, que busca ensinar ao modelo quais textos devem ser considerados mais próximos ou mais distantes semanticamente.

Entretanto, os experimentos com a base atual de 162 chunks apresentaram resultados inferiores aos do modelo original, que não havia passado por esse treinamento adicional.

Uma possível explicação é que os fragmentos utilizados no treinamento continham informações incompletas ou fora de contexto. Dessa forma, o modelo pode ter aprendido relações pouco úteis, associadas a fragmentos de texto, em vez de aprender corretamente o significado das informações.

**Recomendação:** antes de realizar novos experimentos de fine-tuning, é necessário melhorar a organização e a divisão dos documentos. Isso permitirá trabalhar com dados mais completos e reduzir o risco de adaptar o modelo a informações fragmentadas.

---

## 9. Melhorias Recomendadas

Com base nos resultados do Cenário 4, foram identificadas três melhorias prioritárias para as próximas iterações do projeto.

### 9.1. Melhorar a divisão dos documentos (Chunking Estrutural)

Atualmente, os documentos são divididos utilizando uma estratégia de tamanho fixo. A recomendação é utilizar estratégias de divisão adaptadas ao tipo de conteúdo.

| Tipo de documento | Estratégia recomendada |
| --- | --- |
| Formulários e perfis de estudantes | Separar os registros pelo delimitador `---` |
| Calendários e tabelas | Preservar linhas completas e suas relações |
| Editais e documentos longos | Dividir por títulos, seções e parágrafos |
| Textos extensos | Utilizar blocos de 800 a 1000 caracteres, com sobreposição de 15% a 20% |

A sobreposição, também chamada de *overlap*, consiste em repetir uma pequena parte do texto entre dois fragmentos consecutivos. Isso ajuda a evitar a perda de informações que estejam próximas do ponto de divisão.

**Benefício esperado:** aumentar a chance de que os trechos recuperados contenham informações completas, reduzindo recusas provocadas pela fragmentação dos documentos.

### 9.2. Adicionar contexto aos fragmentos (Contextual Retrieval)

A segunda recomendação é incluir informações de identificação nos próprios chunks antes de armazená-los no banco vetorial.

Por exemplo, em vez de armazenar apenas um parágrafo retirado de um edital, o sistema pode registrar também o nome do documento e a seção correspondente.

**Exemplo de estrutura:**

```text
[Documento: edital_residencia_02.pdf | Seção: Requisitos de Inscrição]

Conteúdo do fragmento...
```

Essa abordagem permite que cada trecho carregue informações sobre sua origem.

**Benefício esperado:** facilitar a identificação do assunto, do documento e da seção à qual cada informação pertence, especialmente em arquivos longos ou com estruturas repetitivas.

### 9.3. Implementar busca em duas etapas (Reranking)

Atualmente, o sistema recupera diretamente os três trechos com maiores pontuações de similaridade.

A proposta é utilizar duas etapas de busca:

1. **Recuperação inicial:** buscar os 10 trechos mais relevantes no Qdrant.
2. **Reclassificação:** utilizar um modelo especializado, chamado *Cross-Encoder Reranker*, para avaliar esses 10 candidatos e selecionar os três melhores.

O objetivo do reranking é melhorar a seleção final dos documentos que serão apresentados à LLM.

Isso é especialmente útil quando vários fragmentos possuem conteúdos semelhantes, mas apenas alguns contêm a informação exata necessária para responder.

**Benefício esperado:** melhorar a precisão das informações recuperadas e reduzir a presença de trechos pouco úteis no contexto enviado ao modelo.

Essa alteração também exigirá uma nova avaliação do guardrail, pois mudanças no processo de seleção e pontuação podem afetar o comportamento do limite de similaridade atualmente utilizado.

---

## 10. Priorização das Próximas Etapas

| Prioridade | Melhoria | Objetivo |
| --- | --- | --- |
| 1 — Alta | Reestruturação do chunking | Evitar cortes de informações importantes |
| 2 — Alta | Inclusão de metadados nos chunks | Preservar a identificação e o contexto |
| 3 — Média | Top-10 com reranking | Melhorar a seleção dos documentos |
| 4 — Posterior | Novos testes de fine-tuning | Avaliar a adaptação dos embeddings após melhorar a base |
| 5 — Validação | Ampliação dos testes do guardrail | Verificar o desempenho com mais perguntas válidas e fora de domínio |

A ordem proposta considera as dependências entre as melhorias. Primeiro, é necessário garantir que os documentos estejam bem estruturados. Depois, será possível avaliar com mais precisão o impacto das técnicas de recuperação e da adaptação do modelo de embeddings.

Também é recomendável repetir o benchmark após as alterações, utilizando as mesmas consultas e novos casos de teste. Dessa forma, será possível comparar os resultados e verificar se as mudanças realmente melhoraram a qualidade das respostas.

---

## 11. Conclusão

O Cenário 4 demonstrou que a inclusão de um guardrail baseado em similaridade semântica é uma abordagem promissora para aumentar a segurança do assistente Vezo.

Nos testes realizados, o sistema liberou todas as 11 consultas relacionadas à base de conhecimento e bloqueou corretamente a única pergunta fora do domínio.

Além disso, o comportamento do prompt `rag_v1` mostrou que o modelo consegue reconhecer situações nas quais os documentos recuperados não apresentam evidências suficientes para responder.

Esses resultados indicam que a combinação entre **busca documental, verificação de relevância e instruções de resposta fundamentada** contribui para reduzir a geração de informações sem suporte na base.

Entretanto, a execução também revelou limitações na estratégia atual de recuperação. O principal problema identificado foi a fragmentação dos documentos em chunks de tamanho fixo, que pode separar informações importantes e dificultar a obtenção de respostas completas.

Por esse motivo, a principal recomendação para a próxima etapa é melhorar a organização dos documentos antes de investir em técnicas mais avançadas, como fine-tuning de embeddings.

### 11.1. Recomendação para o projeto Vezo

Considerando os resultados observados, o **RAG com guardrail é a arquitetura recomendada para continuidade do desenvolvimento do assistente Vezo**, sujeita à validação comparativa final com os demais cenários da Sprint 3.

A abordagem oferece três vantagens principais:

- **Maior controle sobre as respostas:** o sistema verifica a relevância dos documentos antes de utilizar a LLM.
- **Redução de respostas sem fundamentação:** o modelo pode se abster quando não encontra evidências suficientes.
- **Melhor utilização de recursos:** perguntas bloqueadas não geram consumo de tokens na LLM.

A próxima etapa deve concentrar esforços na melhoria do chunking, na inclusão de metadados e na avaliação de uma busca com reranking.

Com essas alterações, espera-se aumentar a qualidade das informações recuperadas e, consequentemente, a capacidade do assistente de oferecer respostas completas, confiáveis e fundamentadas nos documentos disponíveis.

**Resultado final:** o Cenário 4 apresentou o comportamento de segurança esperado nos testes executados e fornece evidências para apoiar a escolha arquitetural na consolidação da `TASK-S3-05`.
