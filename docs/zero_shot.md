# Cenário 1 — LLM puro (TASK-S3-02)

Executor independente em `scripts/scenarios/zero_shot.py`, usando Python 3.11,
jsonschema e Groq/Ollama. Não importa Qdrant, embeddings, extratores nem outros cenários.
Cada chamada contém exatamente uma mensagem de usuário com a pergunta, sem histórico,
respostas esperadas, evidências, documentos, exemplos ou ferramentas.

## Executar com Groq (opção escolhida)

Provedor `groq`, modelo `openai/gpt-oss-20b`. A escolha foi autorizada para teste
nesta tarefa; os demais cenários devem usar o mesmo modelo para comparação.
Crie uma chave no [console Groq](https://console.groq.com/keys) e salve somente
localmente no `.env` ignorado pelo Git, no formato `GROQ_API_KEY=valor`.
O script não imprime nem exporta a chave. Use:

```sh
python scripts/scenarios/zero_shot.py --provider groq --env-file .env \
  --model openai/gpt-oss-20b --temperature 0 --seed 42 \
  --max-tokens 2048 --reasoning-effort low --timeout 120
```

Alternativamente, configure `GROQ_API_KEY` no ambiente e omita `--env-file`.
A variável de ambiente tem precedência. O arquivo só carrega essa chave, sem
executar comandos nem carregar outras variáveis. A conexão usa exclusivamente
`https://api.groq.com/openai/v1/chat/completions`; `--base-url` é apenas para Ollama.

A inferência envia somente a pergunta, `tool_choice=none`, sem ferramentas ou
documentos. Usa `include_reasoning=false` para preservar apenas a resposta final;
`reasoning_effort=low` continua consumindo tokens internos. O limite de 2048 inclui
os tokens de raciocínio, portanto não equivale a 2048 tokens de resposta visível.
A temperatura solicitada é 0; a Groq documenta conversão interna para 1e-8.
Os parâmetros são registrados em config. Não há retries automáticos: 429 e demais
falhas HTTP são registrados com o código, sem corpo de resposta ou credenciais.
Respostas com `finish_reason` diferente de `stop` são tratadas como falha, evitando
que uma geração truncada seja registrada como sucesso. Tokens de uma resposta
rejeitada não são contabilizados; o custo real pode incluir essas tentativas.

Referências consultadas: [API](https://console.groq.com/docs/api-reference),
[raciocínio](https://console.groq.com/docs/reasoning),
[compatibilidade e temperatura](https://console.groq.com/docs/openai).

## Executar com Ollama

Instale `jsonschema` (`pip install 'jsonschema>=4.18.0'`) e inicie o Ollama com o
modelo acordado pela equipe:

```sh
ollama serve
# Em outro terminal, substitua MODELO pelo identificador acordado:
ollama pull MODELO
python scripts/scenarios/zero_shot.py --model MODELO
```

O cliente usa `POST /api/chat` com `stream=false`, conforme a
[documentação do Ollama](https://docs.ollama.com/api/chat).
Pode apontar para uma instalação remota via `--base-url` ou `OLLAMA_HOST`.
`--provider ollama` mantém o cliente local; Groq é a alternativa remota implementada.
Não requer chave de API para o servidor local.

Entrada padrão: `tests/benchmark_llm_rag_queries.json`. O documento é validado contra
`$defs/golden_set` de `tests/benchmark_result_schema.json` antes de qualquer chamada.
São exigidas 12 perguntas e IDs únicos. Somente `queries[].query_id` e
`queries[].question` entram no executor de inferência. A versão, o status e o hash
do Golden Set são usados exclusivamente na rastreabilidade da exportação.

Configuração padrão: temperatura 0, seed 42, limite de saída 512 tokens e timeout
120 segundos por pergunta. Configure com `--temperature`, `--seed`, `--max-tokens`
e `--timeout`. Modelo é obrigatório via `--model` ou `ZERO_SHOT_MODEL`; nenhum modelo
foi escolhido implicitamente. A TASK-S3-01 não especifica modelo/provedor; nesta tarefa foi escolhido Groq/GPT-OSS 20B para teste.
Use os mesmos parâmetros nos cenários comparáveis. A seed não garante determinismo
entre diferentes versões/hardwares.

## Resultados e contrato oficial 1.0.0

A saída padrão `reports/scenarios/zero_shot_results.json` é um objeto com
`contract_version`, `golden_set_version`, `scenario`, `run_id`, `generated_at`,
`config` e `results`, validado contra o schema oficial antes da gravação.
Parâmetros, seed, timeout, status e SHA-256 da entrada ficam em `config`.
Cada pergunta mantém seu ID oficial, na ordem original.

Campos de recuperação são listas vazias; `retrieval_latency_ms` é `null`.
Latências em milissegundos medem a chamada completa, incluindo rede e carregamento.
Tokens vêm de `prompt_eval_count` e `eval_count`; se ausentes ficam `null`.
Erros individuais não interrompem as demais perguntas: status `timeout` ou `error`,
resposta e tokens `null`, tipo e mensagem genérica sem corpo HTTP ou credenciais.

`abstained` é booleano nas respostas bem-sucedidas, inferido por uma heurística
conservadora de recusa explícita (por exemplo, “não sei” ou “não posso confirmar”).
Ela usa exclusivamente a resposta do modelo, sem gabarito. Requer revisão manual
pela TASK-S3-05, pois pode produzir falsos positivos/negativos. Respostas originais
são preservadas, inclusive recusas espontâneas; não são reescritas para parecerem
respostas de um guardrail. Em falhas de inferência, `abstained` fica `null`.

O arquivo é substituído atomicamente ao terminar. Use `--output` com caminhos
distintos para preservar execuções. O caminho de saída não pode coincidir com a
entrada ou schema. Saída do processo: 0 para sucesso integral, 1 se qualquer
inferência falhar e 2 para erro de configuração/entrada.

```sh
python -m pytest tests/test_zero_shot.py tests/test_benchmark_golden_set.py tests/test_smoke.py -q
```

Os testes processam as 12 perguntas oficiais com respostas simuladas em diretórios
temporários, validam exportações de sucesso e falha contra o contrato e verificam
que evidências não chegam ao modelo. Não produzem resultados factuais de benchmark.

Na integração, o Golden Set versionado em develop declara `status: release_candidate`,
embora a descrição do PR da TASK-S3-01 mencione `frozen`. O executor preserva esse
status em config sem alterar o dataset. A execução final e o versionamento de
`zero_shot_results.json` dependem do modelo acordado e disponível e da confirmação
da versão congelada. Não há modelo instalado no Ollama deste ambiente. A integração Groq está disponível; veja o diário de validação em `docs/zero_shot_validation.md`.
