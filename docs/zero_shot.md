# Cenário 1 — LLM puro (TASK-S3-02)

Executor independente em `scripts/scenarios/zero_shot.py`, usando apenas a biblioteca
padrão do Python 3.11. Não importa Qdrant, embeddings, extratores nem outros cenários.
Cada chamada contém exatamente uma mensagem de usuário com a pergunta, sem histórico,
respostas esperadas, evidências, documentos, exemplos ou ferramentas.

## Executar

Instale e inicie o Ollama e disponibilize o modelo acordado pela equipe:

```sh
ollama serve
# Em outro terminal, substitua MODELO pelo identificador acordado:
ollama pull MODELO
python scripts/scenarios/zero_shot.py --model MODELO
```

O cliente usa `POST /api/chat` com `stream=false`, conforme a
[documentação do Ollama](https://docs.ollama.com/api/chat).
Também pode apontar para uma instalação remota via `--base-url` ou `OLLAMA_HOST`.
`--provider` aceita `ollama`; outros provedores não estão implementados.
Não requer chave de API para o servidor local.

Entrada padrão: `tests/benchmark_llm_rag_queries.json`. Aceita uma lista de objetos
ou um objeto com `queries`; cada item precisa de `query_id` (alias `id`) e `question`
(alias `query`). IDs devem ser strings únicas. Campos de referência são descartados
antes da inferência. O conjunto inteiro é validado antes da primeira requisição.

Configuração padrão: temperatura 0, seed 42, limite de saída 512 tokens e timeout
120 segundos por pergunta. Configure com `--temperature`, `--seed`, `--max-tokens`
e `--timeout`. Modelo é obrigatório via `--model` ou `ZERO_SHOT_MODEL`; nenhum modelo
foi escolhido implicitamente. Use os mesmos parâmetros nos cenários comparáveis.
A seed não garante determinismo entre diferentes versões/hardwares.

## Resultados e contrato provisório

A saída padrão é `reports/scenarios/zero_shot_results.json`, uma lista com os 17
campos previstos na issue #19. `scenario=zero_shot`, `provider=ollama`, status
`success` ou `error`. Campos de recuperação são listas vazias e latência de
recuperação é 0. Latências em milissegundos medem a chamada completa, incluindo
rede e carregamento do modelo. Tokens vêm de `prompt_eval_count` e `eval_count`;
quando ausentes ficam `null`. Em falha, resposta e tokens ficam `null` e o erro
registra tipo e mensagem genérica, sem corpo HTTP ou credenciais.
`abstained=null` aguarda avaliação posterior: o executor não deduz abstenção por
palavras-chave nem usa o gabarito para classificá-la.

Um arquivo irmão `zero_shot_results.metadata.json` registra parâmetros, modelo,
provedor, horário UTC, quantidade e SHA-256 do arquivo de entrada. Resultados são
salvos com substituição atômica ao terminar; uma falha individual não interrompe
as demais perguntas. O processo retorna 1 se alguma inferência falhar, 2 se houver
erro de configuração/entrada e 0 em sucesso integral. Para preservar execuções
anteriores, use `--output` com caminhos distintos. Não use o caminho de entrada
como saída.

A TASK-S3-01 ainda não publicou o Golden Set oficial nem o JSON Schema em develop
na implementação desta tarefa. Os nomes, valores de enumeração e formato do erro
precisam ser conferidos com `tests/benchmark_result_schema.json` quando disponível,
assim como a compatibilidade com o agregador da TASK-S3-05. Esta entrega não declara
validação contra um schema ainda ausente.

Para desenvolvimento existe `tests/fixtures/zero_shot_queries.provisional.json`,
com as 12 perguntas da avaliação da Sprint 2 e IDs explicitamente provisórios:

```sh
python scripts/scenarios/zero_shot.py --model MODELO \
  --golden-set tests/fixtures/zero_shot_queries.provisional.json \
  --output reports/scenarios/zero_shot_provisional_results.json
python -m pytest tests/test_zero_shot.py tests/test_smoke.py -q
```

Os testes usam respostas simuladas somente em diretórios temporários e não geram
resultados de benchmark para versionamento. Nenhum resultado factual é fabricado.
Para concluir a validação final, a equipe deve publicar o Golden Set e schema,
confirmar modelo/parâmetros, executar as 12 perguntas oficiais em um LLM real,
validar o JSON contra o contrato e versionar o relatório produzido. O arquivo
`zero_shot_results.json` só deverá ser entregue após essa execução real.
