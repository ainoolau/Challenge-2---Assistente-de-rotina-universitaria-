---
name: pr-review
description: >-
  Use this skill when reviewing a pull request from a teammate or performing a
  pre-PR self-review targeting develop or main in the Vezo repository. Inspects
  PR scope against the requested task, verifies security/LGPD guardrails, checks
  RAG/multiagent/frontend contracts, and runs the local CI helper script.
---

# Skill: `pr-review` — Revisão Estruturada de Pull Requests do Vezo

## 1. Quando Usar

Ative esta skill sempre que for revisar um PR de colegas ou validar sua própria branch antes de abrir um PR para `develop` ou `main`.

## 2. Fluxo Obrigatório de Revisão

### Etapa 1 — Mapeamento de Escopo e Arquivos (`git diff`)

Antes de julgar o código, verifique exatamente o que mudou em relação à branch base (`develop`, ou `main` em release) e compare com o objetivo da task/issue:

```bash
git diff --name-status develop...HEAD
git diff --stat develop...HEAD
git diff develop...HEAD
```

Verifique:
- Todos os arquivos alterados pertencem ao escopo pedido pela task/issue?
- Há arquivos acidentais, temporários, scripts soltos ou refatorações fora de escopo que deveriam estar em outro PR?
- Se o PR inclui descrição ou número de issue, todos os critérios de aceite (*Definition of Done*) foram atendidos?

### Etapa 2 — Automação Local de Pré-CI (`scripts/check_pr.py`)

Execute o script auxiliar desta skill para rodar em um único comando o relatório de arquivos alterados, os guardrails de binários/LGPD, `ruff`, `mypy` e a suíte leve do `pytest`:

```bash
python .agents/skills/pr-review/scripts/check_pr.py --base develop
```

*(Se estiver usando o ambiente virtual no Windows: `.\.venv\Scripts\python.exe .agents/skills/pr-review/scripts/check_pr.py --base develop`.)*

### Etapa 3 — Checklist de Critérios Bloqueantes (🔴)

Qualquer violação abaixo **bloqueia** a aprovação do PR:

1. **Segurança, Segredos & LGPD:**
   - Nenhum `.env`, `GROQ_API_KEY`, credencial, trace privado (`reports/multiagents/`) ou banco local (`data/qdrant/`, `*.db`) versionado.
   - Nenhum peso de modelo (`.bin`, `.pt`, `.pth`, `.gguf`, `.safetensors`, `.onnx`) em qualquer diretório.
   - Nenhuma mídia/arquivo compactado/PDF (`.tar.gz`, `.zip`, `.wav`, `.mp3`, `.m4a`, `.pdf`) ou arquivo `> 10 MB` fora de `data/samples/`.
   - Nenhum dado pessoal real (nome completo, matrícula/RA, CPF, telefone) em código, docs, fixtures ou testes.
2. **Contratos do Benchmark & Isolamento:**
   - `tests/benchmark_result_schema.json` (`contract_version: 1.0.0`) e `tests/benchmark_llm_rag_queries.json` sem quebra de contrato.
   - Scripts de benchmark leem **somente** `query_id` e `question` — nunca enviam `expected_answer`, `key_facts` ou `evidence` ao LLM.
   - `scripts/scenarios/zero_shot.py` permanece 100% isolado (sem importar `qdrant_client` ou `src.data_pipeline`).
   - Sem retries HTTP ocultos que mascarem falhas ou distorçam métricas.
3. **Invariantes Multiagentes, Agenda & Segurança de LLM:**
   - Contratos Pydantic v2 em `src/agents/schemas.py` mantêm `extra="forbid"` e `allow_inf_nan=False`.
   - `src/agents/planning.py` mantém `requires_confirmation=True`, proteção de sono no fuso IANA e nunca move compromissos fixos ou escreve na agenda automaticamente.
   - Prompts tratam documentos, perguntas e pareceres como dados não confiáveis, com `tool_choice="none"`.
   - Exceções sanitizadas: nunca gravar corpo HTTP bruto ou credenciais em logs, traces ou respostas de API.
4. **Qualidade & Tipagem (paridade com CI):**
   - `ruff check .`, `ruff format --check .`, `mypy src --ignore-missing-imports --no-warn-return-any` e suíte `pytest` leve passando 100%.
5. **Frontend PWA (quando `frontend/` for alterado):**
   - Segue `docs/DESIGN.md`: **proibido** visual genérico de *vibe coding* (gradientes roxo-para-azul, bolhas decorativas) e **proibido** cores hexadecimais hardcoded fora dos tokens semânticos CSS.
   - Preserva `requires_confirmation=True` na UX (botão explícito de confirmação antes de aplicar agenda).
   - Typecheck (`tsc --noEmit`), lint e build de produção do Next.js sem erros.

### Etapa 4 — Checklist de Qualidade e Boas Práticas (🟡)

- Código novo vem acompanhado de testes unitários/contrato em `tests/` (ou testes do `frontend/`).
- Decisões técnicas novas ou mudanças de status relevantes refletidas em `docs/TASKS.md` ou `docs/MEMORY.md`.
- Sem dependência de rede externa ou Docker nos testes leves do CI.

## 3. Formato Obrigatório do Parecer de Review

Entregue a revisão seguindo exatamente esta estrutura:

```markdown
## Veredito: [APROVAR | PEDIR AJUSTES | BLOQUEAR]

### 1. Escopo vs. Task
- Arquivos alterados: <N>
- Aderência ao escopo: <aderente / arquivos fora do escopo listados>

### 2. Checks Automatizados (`check_pr.py`)
- Guardrails LGPD/Binários: PASS/FAIL
- Ruff (check + format): PASS/FAIL
- MyPy (`src/`): PASS/FAIL
- Pytest (suíte leve): PASS/FAIL

### 3. Achados
- **[BLOQUEANTE]** `caminho/arquivo.py:L42` — descrição objetiva + correção sugerida.
- **[IMPORTANTE]** `caminho/arquivo.py:L88` — descrição objetiva.
- **[SUGESTÃO]** `caminho/arquivo.py:L10` — melhoria opcional.
```
