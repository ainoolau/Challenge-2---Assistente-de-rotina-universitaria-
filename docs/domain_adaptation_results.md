# Adaptação de Domínio de Embeddings: Benchmark e Aprendizados da Task-06

## 1. Visão Geral e Contexto do Experimento

### O que estamos testando aqui?

Quando um estudante faz uma pergunta ao nosso assistente de rotina, o sistema não pesquisa por palavras soltas em um banco de dados relacional comum. Ele converte a pergunta em uma lista de números chamada **embedding** (um vetor) e busca no nosso banco vetorial (**Qdrant**) quais trechos de documentos (sejam textos puros, editais, transcrições de áudios ou tabelas extraídas de imagens via OCR) possuem um significado matemático mais próximo.

Nesta **Task-06**, o objetivo foi responder na prática a uma dúvida central de arquitetura:

> *Se ajustarmos os pesos do modelo de embeddings (*fine-tuning*) com termos do nosso dia a dia universitário, o sistema vai recuperar respostas melhores ou vamos perder robustez em outros pontos?*

### Os Modelos Comparados:

* **Baseline (`paraphrase-multilingual-MiniLM-L12-v2`):** É o modelo pré-treinado padrão. Ele foi treinado em um volume massivo de dados em vários idiomas e já possui uma compreensão semântica muito estável.
* **Fine-Tuned v2 (`models/MiniLM-L12-rotina-v2`):** Versão em que fizemos um treinamento adaptativo usando exemplos do nosso domínio acadêmico através da técnica de **triplas com negativos difíceis** (*hard negatives*), que ensina o modelo a diferenciar detalhes sutis entre regras ou horários parecidos.

---

## 2. Guia Rápido das Métricas (Como Interpretar os Dados)

Para facilitar a leitura por toda a equipe, aqui está o que cada métrica mede na prática:

* **Hit Rate @ 1 (Tiro Certeiro):** Em quantas buscas o documento com a resposta exata ficou no topo absoluto (1º lugar).
* **Hit Rate @ 3 (Janela Útil do RAG):** Em quantas buscas o documento correto apareceu entre os **3 primeiros colocados**. Essa é a nossa métrica mais importante no dia a dia, pois é exatamente o pacote de 3 documentos ($K=3$) que enviamos para o modelo de linguagem (LLM) redigir a resposta ao aluno.
* **Hit Rate @ 5:** Se o documento certo apareceu pelo menos até a 5ª posição.
* **MRR (Mean Reciprocal Rank - Qualidade do Ranking):** Avalia a posição média do acerto. Se o documento certo vem em 1º, a nota é $1.0$; se vem em 2º, cai para $0.5$; se vem em 3º, é $0.33$. Quanto mais perto de $1.0$, mais alto na lista os documentos relevantes estão subindo.
* **Abstenção (Filtro Anti-Alucinação):** Quando o usuário faz uma pergunta que nada tem a ver com o nosso conteúdo (ex: vestibular geral), o sistema precisa dar uma nota de similaridade baixa ($< 0.50$) para assumir com segurança que "não sabe", evitando inventar respostas.
* **Latência Média:** O tempo que a consulta leva para ser processada e retornar do banco vetorial.

---

## 3. Tabela Comparativa de Resultados

Dados consolidados a partir das execuções de avaliação (`reports/evaluation_summary.json` vs. `reports/evaluation_finetuned.json`):

| Métrica Avaliada | Baseline (`paraphrase-multilingual`) | Fine-Tuned v2 (`MiniLM-rotina-v2`) | Variação (Delta) | Impacto Prático no Projeto |
| :--- | :---: | :---: | :---: | :--- |
| **Total de Perguntas Factuais** | 11 | 11 | — | Conjunto de teste cobrindo editais, áudios e OCR. |
| **Hit Rate @ 1** | **54.55%** (6/11) | 45.45% (5/11) | -9.10 p.p. | O baseline colocou a resposta exata em 1º com mais frequência. |
| **Hit Rate @ 3 (Janela RAG)** | **90.91%** (10/11) | 72.73% (8/11) | -18.18 p.p. | O baseline entregou o documento certo no Top-3 em 10 de 11 casos. |
| **Hit Rate @ 5** | **100.00%** (11/11) | 81.82% (9/11) | -18.18 p.p. | No baseline, o conteúdo relevante nunca ficou de fora do Top-5. |
| **Match de Palavras-Chave @ 3** | **90.91%** | 72.73% | -18.18 p.p. | Capacidade de preservar termos técnicos e siglas acadêmicas. |
| **MRR (Qualidade de Posição)** | **0.7197** | 0.5939 | -0.1258 | No baseline, os itens corretos ficaram posicionados mais acima. |
| **Abstenção Fora de Escopo** | **Sucesso** (Score < 0.50) | **Falha** (Score 0.573) | Falso Positivo | O baseline barrou a pergunta; o fine-tuned quase alucinou. |
| **Latência de Busca / Inferência** | 49.68 ms (vetor) / ~2050 ms (total) | ~2066.92 ms (total) | Neutro | Sem variação perceptível de desempenho computacional. |

---

## 4. Diagnóstico Específico: A Imagem de OCR (`grade_aluno_06.jpg`)

Um ponto crítico do nosso pipeline é conseguir resgatar informações extraídas de prints e digitalizações (como horários e grades de disciplinas).

### O histórico desse documento:

1. **O que aconteceu na versão v1:**  
   No primeiro experimento de ajuste (*v1*, treinando apenas aproximando pares diretos de pergunta e resposta), o modelo sofreu um desvio semântico. Ao buscar informações sobre regras de dedicação integral presentes no print `grade_aluno_06.jpg`, o documento caiu para a **4ª posição (Rank #4)**. Como nosso sistema só repassa os 3 primeiros ($K=3$) para o LLM, essa informação foi simplesmente perdida.

2. **A correção na versão v2:**  
   Na versão **v2**, adotamos o treinamento com triplas: fornecemos a pergunta, o trecho correto do print e um exemplo negativo difícil (um horário de outro aluno com formato muito similar).
   * **Resultado:** O modelo aprendeu a notar os detalhes visuais/estruturais da tabela e o documento `grade_aluno_06.jpg` **subiu de volta para o Rank #3 (Top-3)**, entrando novamente no campo de visão do gerador.

---

## 5. O Teste de Abstenção: Por que o modelo adaptado falhou?

Fizemos intencionalmente uma pergunta fora do escopo da rotina de matérias do estudante:

> *"Qual é a nota de corte do vestibular de Medicina da UnB?"*

* **Comportamento esperado:** O sistema deveria identificar que não tem esse dado na base e retornar uma similaridade menor que **0.50**, acionando a resposta padrão de "não sei".
* **No Baseline:** Teve pontuação abaixo de 0.50 e barrou a pergunta com sucesso.
* **No Fine-Tuned v2:** Atribuiu similaridade de **0.573**, superando a linha de corte e indicando falsamente que havia encontrado uma resposta válida.

### Por que isso acontece de forma intuitiva?

O modelo base conhece um universo amplo de assuntos (culinária, esportes, leis, faculdades, etc.). Quando pegamos esse modelo e o treinamos exclusivamente com textos acadêmicos, o "mundo" dele encolhe. Para esse modelo adaptado, qualquer frase que contenha termos como *"UnB"*, *"Medicina"* ou *"Vestibular"* passa a soar extremamente familiar, fazendo com que ele aproxime vetores de assuntos que na verdade não têm relação direta.

---

## 6. Decisão Técnica da Equipe e Próximos Passos

Este experimento trouxe lições valiosas de engenharia para o nosso projeto e para o acompanhamento com os mentores:

1. **Evolução clara de aprendizado (v1 para v2):**  
   Comprovamos que treinar embeddings só com pares positivos gera colapso no espaço vetorial. A mudança para uma abordagem contrastiva com triplas e *hard negatives* surtiu efeito direto, corrigindo a recuperação de tabelas de OCR (`grade_aluno_06.jpg`), subindo o Hit Rate @ 3 de 63.6% para 72.7% e o MRR de 0.5182 para 0.5939.

2. **Custo computacional idêntico:**  
   Ambos os modelos mantêm a dimensão de 384 números por vetor ($d=384$). Isso significa que a busca no Qdrant tem exatamente a mesma complexidade matemática ($\mathcal{O}(d)$), comprovando que a adaptação de domínio não adiciona gargalos de latência ou custos extras de servidor.

3. **Decisão prática de produto:**  
   Como a nossa prioridade número um é **entregar respostas precisas e evitar alucinações**, decidimos manter a coleção **Baseline** (`rotina_estudante_multimodal`) ativa em produção, já que ela entrega 90.91% de precisão no Top-3 e mantém o filtro de abstenção seguro.

4. **Legado para as próximas iterações (v3):**  
   O modelo adaptado, os datasets de triplas e os scripts de fine-tuning ficam preservados no repositório. Para uma futura versão `v3`, o caminho claro é adicionar exemplos negativos de fora de domínio no treinamento para evitar que o modelo compacte excessivamente o espaço vetorial.