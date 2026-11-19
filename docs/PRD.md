# PRD — Vezo: Assistente Inteligente de Rotina Universitária

> **Produto:** Vezo (`assistente-rotina-academica`)
> **Contexto:** Challenge 2 — Residência em IA (UnB / Instituto Eldorado / Softex) · *Big Idea:* Qualidade de Vida
> **Marco de Entrega Final:** `11/12/2026`
> **Status:** Em desenvolvimento ativo (Backend RAG & Multiagentes v1 consolidados; API, Observabilidade e PWA em construção)

---

## 1. Visão do Produto e Problema

Estudantes universitários em **multijornada** precisam conciliar simultaneamente aulas presenciais/EaD, residência/estágio/trabalho CLT, iniciação científica (PIBIC), monitorias, deslocamentos e vida pessoal. Informações críticas ficam espalhadas em formatos heterogêneos (PDFs de editais e calendários acadêmicos, prints/fotos de grades horárias, comunicados de WhatsApp e relatos em áudio), gerando sobrecarga cognitiva, perda de prazos e conflitos de agenda.

O **Vezo** resolve esse problema oferecendo um assistente confiável, auditável e centrado em bem-estar que:

1. **Responde dúvidas acadêmicas e de rotina com rastreabilidade documental** (RAG multimodal com citações literais verificadas e abstenção segura quando não há evidência).
2. **Propõe planos de estudo sem invadir sono nem compromissos fixos**, usando um motor determinístico auditável e exigindo **confirmação explícita** do estudante (`requires_confirmation=True`).
3. **Entrega visibilidade imediata da rotina em um PWA instalável no celular**, combinando dashboard de agenda, alertas de conflitos e chat assistente no mesmo lugar.

---

## 2. Objetivos Estratégicos da Entrega (`11/12/2026`)

1. **Rigor Técnico e Aprendizado (Residência em IA):** manter excelente observabilidade (MLflow), evidências quantitativas de benchmark (LLM vs. RAG vs. Multiagentes) e arquitetura limpa, testável e documentada.
2. **Impacto de Produto ("Brilho no Olho" dos Mentores):** entregar um **PWA responsivo e polido** de ponta a ponta (Next.js/React + FastAPI), com sessões persistentes, visual limpo (sem cara genérica de *vibe coding*) e demonstração fluida no desktop e no celular.

---

## 3. Público-Alvo e Personas

Baseado nos 8 perfis reais anonimizados coletados em `data/samples/perfis_rotina_forms.txt`:

- **Universitário em Multijornada Intensa:** concilia Residência em IA (seg/qua/sex 08h–18h), trabalho CLT ou estágio (ter/qui), aulas noturnas/presenciais e projetos acadêmicos, com janelas livres escassas e alto risco de conflito de horários e privação de sono.
- **Universitário de Graduação com Pesquisa/Monitoria:** alterna entre grade horária fragmentada, laboratórios/PIBIC, regras de monitoria e prazos de calendário acadêmico (trancamento, provas A1/F2/substitutiva).

---

## 4. Escopo do MVP (Entrega de `11/12/2026`)

### 4.1. Núcleo de IA, Dados e Planejamento (Backend)

| Capacidade | Descrição Funcional | Critério de Confiabilidade |
| :--- | :--- | :--- |
| **Ingestão Multimodal** | Extração e indexação de PDFs (digitais/escaneados), imagens (Tesseract OCR), áudios (Whisper) e textos/Word na coleção Qdrant `rotina_estudante_multimodal`. | Chunking estrutural com contexto preservado e anonimização LGPD. |
| **RAG com Guardrail Pré-LLM** | Busca vetorial multilíngue (`paraphrase-multilingual-MiniLM-L12-v2`, 384d `COSINE`) com bloqueio pré-LLM (`top_score < 0.50`) e evolução para reranking Top-10 → Top-3. | Zero chamadas ao LLM em consultas fora de domínio bloqueadas; abstenção segura padronizada. |
| **Colaboração Multiagentes** | Orquestração determinística entre `ResearchAgent`, `AnalysisPlanningAgent` e `ValidationAgent` com no máximo 1 rodada de correção (limite de 6 chamadas LLM). | Citações literais verificadas em código (`[C1: arquivo.ext]`) + auditoria semântica + lacunas explícitas. |
| **Motor Determinístico de Agenda** | Alocação algorítmica de metas de estudo em blocos de até 60 min respeitando fuso IANA, horizonte ≤ 14 dias, prazos, prioridades, sono recorrente (padrão 22h–06h) e eventos fixos. | Nenhuma escrita automática (`requires_confirmation=True`); conflitos pré-existentes sinalizados sem mover eventos fixos; 100% auditado por `audit_plan`. |
| **API FastAPI + Sessões Persistentes** | Camada `src/api/` expondo consulta/planejamento, gestão de agenda do estudante, histórico de conversas e sessões persistentes entre acessos. | Contratos Pydantic v2 estritos (`extra="forbid"`), sanitização de erros e zero exposição de segredos. |
| **Observabilidade MLOps** | Camada `src/mlops/` integrada ao **MLflow** registrando latência (retrieval, geração, pacing), consumo de tokens, taxa de abstenção, acertos de retrieval (`Hit@3`, `MRR`) e validações. | Evidências comparáveis entre versões do pipeline e cenários do benchmark. |

### 4.2. Experiência Web / Mobile (Frontend PWA)

- **PWA Responsivo (Next.js / React + Tailwind CSS + shadcn/ui):** instalável no celular (manifest, ícones e layout mobile-first).
- **Dashboard de Rotina (Hoje / Semana / Mês):** visão rápida dos compromissos do estudante e das prioridades da semana.
- **Visualizador de Cenário do Estudante:** exibição dos blocos fixos, janela de sono protegida e **destaque imediato de conflitos detectados** com atalho para resolvê-los com o assistente.
- **Chat Assistente Integrado ao Dashboard:**
  - Respostas fundamentadas com citações rastreáveis e visualização do trecho original;
  - Exibição clara de lacunas/limitações e mensagens de abstenção segura;
  - Preview visual dos blocos de estudo sugeridos e **botão explícito de confirmação** antes de incorporar à agenda da sessão.

---

## 5. Escopo Plus / Pós-MVP

Funcionalidades fora do caminho crítico de `11/12/2026` (podem entrar como diferencial extra apenas se o MVP + observabilidade estiverem 100% estabilizados):

- **Importação/Exportação de Agenda:** integração com Google Calendar e geração/leitura de arquivos `.ics`.
- **Integrações Institucionais:** importação direta de grades e calendários de portais (SIGAA, Siscad).
- **Notificações Externas:** envio proativo via Teams, WhatsApp ou e-mail.
- **Fine-Tuning de Embeddings:** novos experimentos supervisionados apenas após consolidação do chunking estrutural.

---

## 6. Requisitos Não Funcionais e Guardrails Obrigatórios

1. **Privacidade e LGPD:** base de demonstração anonimizada em `data/samples/` (`DOC-01` a `DOC-25`); bloqueio automatizado no CI para pesos de modelos e mídias/PDFs/`>10 MB` fora de `data/samples/`; traces privados (`reports/multiagents/`) e `.env` nunca versionados.
2. **Segurança contra Prompt Injection e Vazamentos:** documentos e entradas do usuário tratados como dados não confiáveis; `tool_choice="none"`; nunca registrar `GROQ_API_KEY`, prompts sensíveis ou corpo bruto de erros HTTP em logs/respostas.
3. **Integridade do Benchmark:** gabaritos (`expected_answer`, `key_facts`, `evidence`) de `tests/benchmark_llm_rag_queries.json` nunca podem ser enviados ao LLM.
4. **Controle Humano:** nenhuma ação do LLM altera a agenda do usuário sem aprovação explícita.

---

## 7. Métricas de Sucesso

| Dimensão | Métrica | Meta / Referência |
| :--- | :--- | :--- |
| **Retrieval** | `Hit@3` / `Hit@5` / `MRR` no Golden Set (`GS-01`–`GS-11`) | `Hit@3 >= 90%`, `Hit@5 >= 95%`, superando lacunas atuais de `GS-01/05/06/08` |
| **Segurança RAG** | Abstenção pré-LLM fora de domínio (`GS-12` e casos negativos) | `100%` de bloqueio com `0` tokens de geração |
| **Fidelidade** | Taxa de afirmações sustentadas por citações literais válidas | `100%` de conformidade estrutural (`ValidationAgent`) |
| **Agenda** | Violações de invariantes (sono, prazo, sobreposição, fixos) | `0` violações aprovadas (`audit_plan == []`) |
| **Observabilidade** | Execuções rastreadas no MLflow (latência, tokens, status) | `100%` dos experimentos e fluxos instrumentados |
| **Produto (PWA)** | Fluxo completo fim-a-fim (Dashboard → Chat → Citação → Confirmação) | Instalável no mobile, responsivo e persistindo sessões sem erros |
