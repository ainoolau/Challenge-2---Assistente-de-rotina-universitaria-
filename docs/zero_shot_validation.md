# Diário de implementação e validação — TASK-S3-02

Data: 11/11/2026 (America/Sao_Paulo).
Branch: `codex/task-s3-02-zero-shot`. Trabalho isolado em `zero-shot-task` para
preservar as alterações locais preexistentes em `rag-projeto`.

## Etapas concluídas

1. Inspeção do projeto e das issues #19/#20. Inicialmente, develop não continha
   Golden Set nem schema. Implementado cliente independente para Ollama,
   parâmetros configuráveis, latência, tokens e falhas por pergunta. Fixture
   provisória com 12 perguntas da Sprint 2 foi usada somente para desenvolvimento.
2. Commit `13184db`: primeira implementação; 8 testes aprovados.
3. Integração de develop após merge do PR #24 (TASK-S3-01). Substituída a fixture
   pelo Golden Set oficial 1.0.0. Corrigida a exportação para o envelope oficial,
   retrieval_latency_ms=null e status timeout. Adicionada validação de entrada e
   saída com jsonschema e heurística revisável de abstenção. Commit `10daf15`;
   39 testes aprovados.
4. Consulta à documentação dos provedores. Escolhido Groq e modelo
   `openai/gpt-oss-20b` com autorização do usuário. Implementado cliente HTTP
   sem SDK adicional, sem ferramentas, busca ou contexto externo. Mantido Ollama.
5. Criada, com confirmação do usuário, chave dedicada `vezo-benchmark-s3` no
   projeto padrão, com expiração em 18/11/2026. Credencial salva exclusivamente
   no `.env` local com permissão 0600; arquivo ignorado pelo Git. Nenhum valor
   de credencial é incluído nos relatórios, documentação ou testes.
6. Testes adicionais de payload Groq, tokens, recusa explícita, ausência de chave,
   resposta truncada/vazia, contagens inválidas, ausência de escolhas, chamada de
   ferramenta indevida, HTTP 429 e sanitização de erros. Total: 49 testes aprovados
   antes da execução real. Respostas simuladas ficam apenas em temporários.

## Protocolo da execução real

- Golden Set: `tests/benchmark_llm_rag_queries.json`, versão 1.0.0, 12 perguntas
  (GS-01 a GS-12), na ordem original; sem usar o gabarito na inferência.
- O arquivo integrado declara `release_candidate`, apesar de o texto do PR #24
  mencionar `frozen`. O dataset não foi alterado; status e hash ficam na saída.
- Provedor: Groq; modelo: `openai/gpt-oss-20b`.
- Temperatura solicitada: 0 (Groq documenta conversão interna para 1e-8).
- Seed: 42; reasoning_effort: low; include_reasoning: false.
- max_completion_tokens: 1024 (inclui raciocínio); timeout: 120s por pergunta.
- Uma mensagem de usuário por pergunta; sem histórico, system prompt, gabarito,
  documentos, Qdrant, embeddings ou ferramentas; tool_choice=none.
- Execução sequencial, sem retries automáticos. Medição de latência inclui rede,
  processamento remoto e parsing da resposta. Falhas não interrompem o conjunto.
- Finalização diferente de stop é rejeitada como falha, sem resposta parcial.
- Saída validada com o JSON Schema 1.0.0 antes de ser gravada atomicamente.
- Abstenção é heurística sobre a resposta e requer revisão manual. Sucesso técnico
  não significa precisão factual. A comparação factual pertence à avaliação.

Comando reproduzível (a chave não faz parte do comando):

```sh
python scripts/scenarios/zero_shot.py --provider groq --env-file .env \
  --model openai/gpt-oss-20b --temperature 0 --seed 42 \
  --max-tokens 1024 --reasoning-effort low --timeout 120
```

## Fontes técnicas

- [Groq Chat API](https://console.groq.com/docs/api-reference)
- [Groq: reasoning e parâmetros GPT-OSS](https://console.groq.com/docs/reasoning)
- [Compatibilidade e temperatura](https://console.groq.com/docs/openai)
- [Modelos disponíveis](https://console.groq.com/docs/models)

## Publicação

A branch foi publicada no GitHub. A tentativa anterior de criar PR pelo conector
recebeu HTTP 403 (`Resource not accessible by integration`). Isso não é evidência
de um PR criado; a publicação do PR deve ser verificada separadamente.

## Tentativa 1 e diagnóstico

A primeira execução real retornou HTTP 403 nas 12 perguntas. Relatório preservado
em `reports/scenarios/zero_shot_attempt_01_http403.json`; não representa respostas
do modelo. Uma chamada autenticada de listagem de modelos retornou HTTP 200 e
confirmou a disponibilidade de `openai/gpt-oss-20b`. Uma chamada curta de diagnóstico
com o mesmo payload de geração e User-Agent `vezo-benchmark/1.0` retornou HTTP 200,
resposta “teste”, 77 tokens de entrada e 33 de saída (23 de raciocínio).

A diferença observada foi o User-Agent: o cliente Python usava o padrão urllib.
Foi adicionado o identificador do benchmark ao cliente Groq e à sua verificação
unitária. Os 49 testes continuaram passando. Atribuir a rejeição a uma política
específica de firewall seria especulação; apenas a diferença observada está
registrada. A tentativa seguinte mantém os mesmos parâmetros de geração.


## Isolamento solicitado e tentativa 2

Antes de versionar as alterações Groq, foi criada a branch
`codex/task-s3-02-groq-benchmark`, derivada da implementação zero-shot já publicada.
A branch nova reúne a integração Groq, os testes, a documentação e os relatórios.
Nenhuma alteração foi aplicada diretamente em develop nem no checkout original.

A tentativa 2 com 1024 tokens gerou 10 respostas e duas falhas de validação
(GS-07 e GS-08), preservada em `zero_shot_attempt_02_1024_tokens.json`.
O diagnóstico das duas perguntas será feito sem usar respostas esperadas.


## Diagnóstico de truncamento e tentativa 3

Uma repetição diagnóstica de GS-07/GS-08 confirmou finish_reason=length em ambas,
com 1024 completion_tokens em cada chamada. GS-07: 85 prompt_tokens, 66 tokens
internos de raciocínio; GS-08: 92 prompt_tokens, 10 internos. Conteúdos parciais não
foram usados como respostas válidas nem substituídos por gabaritos.

O limite foi elevado uniformemente para 2048 tokens em uma nova execução integral,
sem alterar perguntas, temperatura, seed ou esforço. Esse ajuste corrige um limite
de execução; não seleciona respostas por acerto factual. Use 2048 nos demais
cenários ao comparar esta execução. As tentativas anteriores ficam preservadas.


## Resultado da execução integral com 2048 tokens

```json
{
  "run_id": "zero_shot-180ca97a09c24be98bb8ce906af401bd",
  "success_count": 12,
  "error_count": 0,
  "input_tokens": 1066,
  "output_tokens": 5525,
  "mean_latency_ms": 1287.881,
  "median_latency_ms": 1253.658,
  "total_query_latency_ms": 15454.568,
  "heuristic_abstention_ids": [
    "GS-09"
  ]
}
```

Arquivo: `reports/scenarios/zero_shot_results.json`. As três exportações validam
contra o schema oficial 1.0.0. O total de latências soma as chamadas medidas, sem
incluir inicialização e exportação. Tokens de diagnósticos e tentativas anteriores
não integram os totais desta execução. Nenhum custo foi inferido como cobrança real.

Validação final: 49 testes aprovados; Ruff check e format aprovados para os
arquivos alterados; git diff --check aprovado. A análise factual e a revisão da
heurística de abstenção permanecem para o benchmark comparativo (TASK-S3-05).
O sucesso de 12/12 significa conclusão técnica, não acerto de 12/12 respostas.
