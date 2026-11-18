# Registro de implementação e testes multiagentes

Data: 16/11/2026. Origem do trabalho: proposta consolidada de arquitetura e execução
fornecida pelo usuário. Base Git: develop em 028560b; branch isolada
codex/sistema-multiagentes; checkout local multiagents-task. As alterações anteriores
em rag-projeto e zero-shot-task foram preservadas.

## Implementação

Três agentes com contratos Pydantic próprios, cliente HTTP Groq estruturado,
recuperação reutilizada, gate pré-LLM, agenda determinística, orquestração com uma
correção máxima e CLI com traces. Teste de correção usa uma citação C999 em uma
resposta simulada; fica explicitamente separado das evidências de LLM real.

A pesquisa de uma pergunta composta inicialmente retornou apenas a regra de
advertências. O sistema indicou a lacuna sobre frequência. Foi adicionada busca
por partes e uma rodada limitada de refinamento sugerida pelo agente. Isso não
substitui a necessidade de melhorar a recuperação nem garante encontrar toda a
informação solicitada. Resposta parcial com lacunas explícitas não equivale a
cobertura completa da pergunta.

As demonstrações usam agenda fictícia. Meta de 240 minutos e prazos absolutos
foram fornecidos como dados estruturados, não extraídos ou inferidos pelo LLM.
O conflito entre CLT e aula foi mantido e sinalizado, sem mover compromissos.

## Verificações

- 32 testes novos de contratos, handoffs, limite de correção, gate, citações,
  refinamento, erro sanitizado, uso de tokens, agenda e CLI.
- Teste com 50 agendas geradas com seed fixa verifica invariantes e contabilização.
- Teste de transição de horário de verão verifica sono atravessando a meia-noite.
- Suíte combinada com zero-shot, Golden Set e smoke: 81 testes aprovados.
- Ruff check no repositório e Ruff format aprovados.
- MyPy no src: sem erros em 17 arquivos, como no comando do CI.
- CI atualizado para instalar Pydantic e executar a nova suíte.

## Execuções reais e incidentes

O usuário autorizou explicitamente o envio à Groq dos trechos recuperados no
Qdrant para estes testes. Não foram enviados gabaritos do Golden Set nem a chave
em prompts. Não foi feita ingestão ou alteração de coleção. A credencial foi lida
do .env já existente no checkout anterior, sem copiar seu valor para a branch.

Execuções exploratórias mostraram: (a) síntese parcial com lacunas, (b) rejeição
real de uma afirmação imprecisa pelo validador e revisão pelo agente de análise,
(c) resposta de horário de Econometria com proposta de agenda sem novas violações,
(d) bloqueio pré-LLM da pergunta de Medicina com score 0,43283698491196365.

Duas tentativas registraram HTTP 429; a primeira antecedeu o registro explícito do
código HTTP e a segunda confirmou o código 429 no trace. São falhas preservadas,
não execuções completas. Não se alega que os dados de uma falha comprovem sucesso.
Foi adicionado pacing configurável de 15 segundos na CLI para reduzir pressão
sobre as cotas. Não há retries escondidos ou alteração de respostas para obter
aprovação. Resultados anteriores permanecem locais para auditoria.

Os traces completos ficam em reports/multiagents e não são publicados no Git.
O quadro final e o pacote local selecionam execuções explicitamente identificadas;
a demonstração simulada não é apresentada como execução de Groq.


## Quadro da demonstração final

Pacing configurado em 15 segundos; valores em milissegundos. A coluna HTTP soma
as chamadas individuais, incluindo transporte/parsing, sem o pacing.

| Cenário | Modo | Estado | Chamadas | Tempo total | Espera por cota | Soma HTTP | Tokens entrada / saída |
|---|---|---|---:|---:|---:|---:|---|
| documental | live | completed | 4 | 45713.83 | 41252.34 | 4207.18 | 4502 / 383 |
| planejamento | live | completed | 4 | 60616.62 | 57037.76 | 3477.06 | 4862 / 608 |
| fora_dominio | live | abstained | 0 | 30.10 | 0.00 | 0.00 | 0 / 0 |
| correcao | simulated | completed | 4 | 0.23 | 0.00 | 0.00 | None / None |

Na consulta documental, a regra de três advertências foi recuperada; a frequência
mínima permaneceu como lacuna mesmo após refinamento. Estado completed significa
que a colaboração terminou com resposta auditada, não cobertura completa da
pergunta ou precisão de 100%. Esse caso aponta melhoria pendente do retrieval.

No planejamento, foram sugeridos cinco blocos somando 240 minutos, sem novos
conflitos, com sono e compromissos fixos protegidos. O conflito original CLT/aula
foi sinalizado. Não houve alteração de agenda. No caso negativo, o score medido
foi 0,43283698491196365 e o gate bloqueou a geração.

Os traces selecionados são:

- `reports/multiagents/live/multiagent-4cb583d41d294c7abd7bfd04a47d2108/documental.json`
- `reports/multiagents/live/multiagent-92fd7a9f51c44470aa3a600c5fba63cc/planejamento.json`
- `reports/multiagents/live/multiagent-cb8fb3b9fe8e4f9f9136aeb31b4e8dd2/fora_dominio.json`
- `reports/multiagents/simulated/multiagent-08dc545bd05b4739ab299b4157b2bb91/correcao.json`


## Revisão de 18/11/2026

Restaurados os comandos de ambiente virtual, requirements e Docker Compose no README,
com o modelo multilíngue correto. O carregamento de GROQ_API_KEY agora pertence a
src/agents/llm.py e preserva o ambiente existente, sem importar scripts de benchmark.
Buscas simples continuam com até três chunks; buscas compostas e refinamentos
retêm até cinco, com deduplicação e identificadores únicos. Testes controlados
cobrem ambos os limites e a preservação de evidência com score menor.

Os resultados reais acima são históricos, anteriores à ampliação do limite.
Não foi feita nova chamada à Groq nesta revisão; a cobertura factual real ainda
precisa ser medida novamente. A suíte completa revelou também uma asserção global
no teste zero-shot: outros testes já haviam importado Qdrant. A verificação agora
compara os módulos antes e depois da execução zero-shot, sem depender da ordem.
