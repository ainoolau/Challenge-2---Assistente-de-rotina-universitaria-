# Cenário 1 — LLM puro (TASK-S3-02)

Executor independente em `scripts/scenarios/zero_shot.py`, usando Python 3.11,
jsonschema e Ollama. Não importa Qdrant, embeddings, extratores nem outros cenários.
Cada chamada contém exatamente uma mensagem de usuário com a pergunta, sem histórico,
respostas esperadas, evidências, documentos, exemplos ou ferramentas.

## Executar

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
`--provider` aceita `ollama`; outros provedores não estão implementados.
Não requer chave de API para o servidor local.

Entrada padrão: `tests/benchmark_llm_rag_queries.json`. O documento é validado contra
`$defs/golden_set` de `tests/benchmark_result_schema.json` antes de qualquer chamada.
São exigidas 12 perguntas e IDs únicos. Somente `queries[].query_id` e
`queries[].question` entram no executor de inferência. A versão, o status e o hash
do Golden Set são usados exclusivamente na rastreabilidade da exportação.

Configuração padrão: temperatura 0, seed 42, limite de saída 512 tokens e timeout
120 segundos por pergunta. Configure com `--temperature`, `--seed`, `--max-tokens`
e `--timeout`. Modelo é obrigatório via `--model` ou `ZERO_SHOT_MODEL`; nenhum modelo
foi escolhido implicitamente. A TASK-S3-01 não especifica modelo/provedor comparativo.
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
da versão congelada. Não há modelo instalado no Ollama deste ambiente.
