# Execução e validação do sistema multiagentes

## Ambiente e execução

Python 3.11. As dependências estão no pyproject.toml; para testes leves:

```sh
pip install pytest 'pydantic>=2.6.0' jsonschema
python -m pytest tests/test_multiagents.py tests/test_zero_shot.py tests/test_benchmark_golden_set.py tests/test_smoke.py -q
python scripts/demo_multiagents.py
```

Sem argumentos, executa quatro demonstrações SIMULADAS. Não abre o Qdrant, não
carrega embeddings e não chama a Groq. Os tokens simulados são null, exceto no
bloqueio pré-LLM, que registra consumo zero. Não são medições de qualidade do LLM.

Para usar a base real, instale as dependências do projeto e configure
GROQ_API_KEY no ambiente ou num arquivo .env local ignorado pelo Git:

```sh
python scripts/demo_multiagents.py --mode live --env-file .env \
  --qdrant-path data/qdrant --output-dir reports/multiagents
```

Também pode usar servidor com QDRANT_URL e QDRANT_API_KEY no ambiente. Não passe
--qdrant-path nesse caso. O modelo de embeddings será carregado em CPU; ele precisa
estar em cache ou acessível para download. A base local admite apenas um processo
por vez. Não rode simultaneamente ingestão e demonstração na mesma pasta.

Groq: modelo padrão openai/gpt-oss-20b, temperatura 0, seed 42, 2048 tokens máximos,
reasoning_effort=low, include_reasoning=false, timeout 120s. O limite inclui tokens
de raciocínio. Pode configurar --model, --max-tokens e --threshold. As chaves não
são copiadas automaticamente entre checkouts. A chave do teste anterior expira em
18/11; confirme uma credencial válida para a apresentação de 20/11.

O modo live executa três cenários reais e mantém “correcao” explicitamente simulado
para injetar uma citação inválida sem contaminar resultados reais. É possível
selecionar --scenario documental, planejamento, fora_dominio ou correcao.

Pedidos próprios: `--request caminho/request.json`, conforme AgentRequest. As
metas e compromissos precisam de datas absolutas com fuso; não há parsing de
agenda a partir de texto livre. Exemplo de entrada é gerado pelo comando:

```sh
python -c 'import json; from src.agents.demo import demo_request; print(demo_request("planejamento").model_dump_json(indent=2))' > request.json
python scripts/demo_multiagents.py --mode live --env-file .env --request request.json
```

Resultados ficam em `<output-dir>/<modo>/<run_id>/<cenario>.json`, sem sobrescrever
execuções anteriores. Exit codes: 0 para fluxo concluído ou abstenção segura,
1 para erro registrado num fluxo e 2 para configuração/preparação inválida. Na
abstenção, a proposta intermediária pode existir no trace para auditoria, mas não
é apresentada como resposta validada em final_answer.

## Roteiro de demonstração

1. Documental: frequência e advertências. Mostrar consultas, citações, lacunas,
   síntese e auditoria. Se faltar uma parte, declarar a lacuna.
2. Planejamento: horário de Econometria e meta fictícia de 240 minutos, agenda de
   17 a 20/11, sono 22h–06h, CLT, aula e deslocamento. Mostrar as janelas calculadas,
   o conflito original CLT/aula e requires_confirmation=true.
3. Fora de domínio: nota de corte de Medicina. Registrar o score realmente retornado;
   não impor o valor histórico 0,4328. Se o gate bloquear, mostrar zero chamadas.
4. Correção simulada: primeira resposta usa C999. Validação reprova, devolve
   “Citação inexistente”, Análise corrige e a segunda validação aprova. Mostrar no
   trace as duas propostas. Essa demonstração é um teste controlado, não LLM real.

O código não assume que a mera aprovação do validador equivale à verdade. Na
apresentação, conferir os trechos e os dados de agenda junto aos resultados.

## Relação com a proposta

TASK-F3-09: schemas.py. TASK-F3-10: research_agent.py. TASK-F3-11:
analysis_planning_agent.py e planning.py. TASK-F3-12/F3-13: validation_agent.py e
orchestrator.py. TASK-F3-14: CLI, documentação e evidências. Esses identificadores
vêm da proposta; não foram presumidos números de issue nem criadas issues novas.

Diferenças documentadas: pesquisa pode fazer uma rodada de refinamento; até seis
chamadas LLM no pior caso; minutos e compromissos são estruturados explicitamente;
traces privados são ignorados pelo Git. Os exemplos de score e ganho de 65% de
latência da proposta não são tratados como medições reproduzidas.

Para entrega no Teams, revisar os traces e montar o pacote local com código,
documentação, testes e evidências. Esta implementação não envia mensagens ou
arquivos ao Teams automaticamente.

## Cotas e interpretação de latência

A CLI usa --min-call-interval 15 por padrão no modo live, compartilhado entre os
cenários. É espaçamento entre inícios de requisição, não retry. Ajuste conforme as
cotas da conta; 15 segundos não garante ausência de 429 se houver outros usuários
ou limites diários. Use 0 somente quando as cotas permitirem.

O trace separa `rate_limit_wait_ms` e `latency_ms` por chamada do cliente. A latência
total do fluxo e a latência das etapas incluem a espera; a latência individual da
chamada HTTP exclui esse pacing. Tokens de respostas truncadas/JSON inválido são
preservados quando informados pelo provedor. Se uma tentativa não informa uso,
o total é null em vez de subestimar o consumo; valores conhecidos continuam nos
registros individuais. Não se infere custo faturado a partir desses totais.
