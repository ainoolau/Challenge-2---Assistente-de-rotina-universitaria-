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

- 31 testes novos de contratos, handoffs, limite de correção, gate, citações,
  refinamento, erro sanitizado, uso de tokens, agenda e CLI.
- Teste com 50 agendas geradas com seed fixa verifica invariantes e contabilização.
- Teste de transição de horário de verão verifica sono atravessando a meia-noite.
- Suíte combinada com zero-shot, Golden Set e smoke: 80 testes aprovados.
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
