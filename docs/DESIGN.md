# DESIGN — Diretrizes de UX, Interface e Sistema Visual do Vezo

> **Interface Oficial:** PWA responsivo em **Next.js / React + Tailwind CSS + shadcn/ui** (`frontend/`)
> **Status da Identidade Visual:** Estrutura de UX, componentes e tokens semânticos definidos; **paleta oficial de cores em alinhamento final pela equipe** (candidata em discussão externa ainda não versionada no repositório).

---

## 1. Princípios de Design e Experiência (UX)

O usuário do Vezo é um estudante universitário em multijornada, frequentemente cansado e sob pressão de prazos. A interface deve **reduzir carga cognitiva**, não adicionar ruído visual.

1. **Clareza Funcional e Calma Cognitiva:** priorizar leitura escaneável de horários, prioridades da semana e conflitos logo no primeiro olhar.
2. **Transparência de IA (Trust by Design):**
   - Toda afirmação factual mostra sua fonte rastreável (`[C1: edital_residencia_02.pdf]`) com inspeção do trecho literal recuperado.
   - Lacunas e abstenções seguras aparecem com clareza e sem aparência de "erro quebrado".
   - **Separação visual inequívoca** entre *compromissos confirmados*, *sono protegido* e *proposta de estudo sugerida pela IA* (`requires_confirmation=True`).
3. **Mobile-First + Produtividade Desktop (PWA):** instalável no celular para consulta rápida no deslocamento e espaçoso no desktop (dashboard + chat lado a lado).

### Anti-Padrões Obrigatórios ("Sem Cara de Vibe Coding")

Para garantir acabamento profissional e autoral na entrega aos mentores:

- **PROIBIDO** usar gradientes genéricos roxo-para-azul em cabeçalhos, botões, fundos ou cards.
- **PROIBIDO** encher a tela de ícones excessivamente arredondados em bolhas coloridas decorativas, sombras *glow/neon* ou emojis como substitutos de hierarquia visual.
- **PREFERIR** superfícies limpas, bordas finas (`1px`), espaçamento consistente, tipografia forte com contraste bem calibrado e ícones lineares discretos (`lucide-react`, padrão do `shadcn/ui`).

---

## 2. Stack de Frontend e PWA

| Camada | Escolha | Motivo |
| :--- | :--- | :--- |
| **Framework** | Next.js (App Router) + React + TypeScript | Estrutura moderna, tipagem alinhada aos schemas da API FastAPI e fácil suporte a PWA. |
| **Estilização** | Tailwind CSS + CSS Variables (Design Tokens) | Produtividade e troca instantânea de paleta sem refatorar componentes. |
| **Biblioteca de Componentes** | `shadcn/ui` (sobre Radix UI) + `lucide-react` | Componentes acessíveis, limpos, personalizáveis e sem visual genérico engessado. |
| **PWA** | `manifest.webmanifest` + ícones + layout responsivo | Permite "Adicionar à tela inicial" no celular com navegação fluida. |

---

## 3. Sistema de Design Tokens (Paleta Desacoplada)

Como a paleta oficial do Vezo ainda está em definição pela equipe (com uma paleta candidata externa pronta para ser incorporada), todos os componentes devem consumir **exclusivamente tokens semânticos** via CSS variables (`globals.css` / Tailwind), nunca códigos hexadecimais hardcoded.

### 3.1. Tokens Base (`shadcn/ui`)

| Token | Papel na Interface | Diretriz Temporária (até plugar a paleta oficial) |
| :--- | :--- | :--- |
| `--background` / `--foreground` | Fundo principal e texto primário | Neutro limpo de alto contraste (claro como padrão; dark mode opcional) |
| `--card` / `--border` | Cartões de agenda, painéis e divisórias | Superfície levemente destacada com borda sutil (`1px`) |
| `--primary` / `--primary-foreground` | Ações principais (ex.: "Confirmar plano", envio no chat) | Reservado para a cor primária oficial do Vezo |
| `--secondary` / `--muted` | Chips de filtro (Hoje/Semana/Mês), metadados, timestamps | Neutros suaves sem competir com os compromissos |
| `--accent` | Hover, foco e destaque de seleção | Tom de apoio da paleta oficial |
| `--destructive` | Conflitos de horário (`input_conflicts`) e alertas críticos | Vermelho sóbrio de alta legibilidade |
| `--warning` | Lacunas documentais, horas `unallocated` e prazos apertados | Âmbar sóbrio |
| `--success` | Plano auditado/confirmado e status saudável | Verde sóbrio |

### 3.2. Tokens Semânticos de Domínio (Agenda)

| Token | Tipo de Evento (`ScheduleSlot.kind` / Estado) | Tratamento Visual |
| :--- | :--- | :--- |
| `--slot-class` | Aulas (`class`) | Bloco sólido com barra lateral de cor primária |
| `--slot-work` | Trabalho / Residência (`work`) | Bloco sólido neutro/secundário estruturado |
| `--slot-commute` | Deslocamento (`commute`) | Faixa compacta e discreta |
| `--slot-sleep` | Sono protegido (`sleep`, padrão `22h–06h`) | Faixa suave hachurada com ícone de bloqueio (não editável pela IA) |
| `--slot-conflict` | Conflito pré-existente (`input_conflicts`) | Borda de alerta + badge "Conflito" + botão "Resolver com Vezo" |
| `--slot-study-proposed` | Estudo sugerido (`ProposedBlock`) | **Borda tracejada** + badge "Proposta" (só vira sólido após confirmação) |

> **Como aplicar a paleta final da equipe:** ao adicionar a imagem/guia de identidade visual do Vezo ao repositório, atualizar apenas os valores de tokens em `frontend/src/app/globals.css` e documentar os hexadecimais finais nesta seção.

---

## 4. Arquitetura de Telas e Fluxos do MVP

### 4.1. Layout Geral (Desktop vs. Mobile PWA)

- **Desktop (`>= 1024px`):** layout em duas colunas com barra lateral recolhível de sessões:
  - **Esquerda (60%–65%):** Dashboard de Rotina (Hoje / Semana / Mês + Prioridades + Alertas de Conflitos + Visualizador de Agenda).
  - **Direita (35%–40%):** Painel fixo do **Chat Assistente Vezo**.
- **Mobile PWA (`< 1024px`):** barra de navegação inferior fixa com 3 abas principais (**Hoje/Agenda**, **Assistente**, **Prioridades/Sessões**) e targets de toque `>= 44px`.

### 4.2. Componentes Principais

1. **Seletor de Visão (Hoje / Semana / Mês):**
   - **Hoje:** timeline detalhada por hora com foco imediato no próximo compromisso, sono protegido e janelas livres.
   - **Semana:** grade semanal destacando carga por dia, prioridades da semana e conflitos sobrepostos.
   - **Mês:** calendário macro destacando prazos críticos (provas, entregas, trancamento, metas de estudo).
2. **Painel de Cenário do Estudante (Prioridades & Conflitos):**
   - Lista ordenada de metas de estudo (`StudyGoal`) com prazo, prioridade (`1–5`) e minutos restantes.
   - Banner acionável quando houver `input_conflicts` (ex.: CLT vs. Aula de Econometria), deixando claro que o Vezo **não move compromissos fixos sozinho** e oferecendo envio direto ao chat.
3. **Chat Assistente Integrado:**
   - **Mensagem do Assistente com Evidências:** texto claro + badges de citação (`[C1: arquivo.pdf]`). Clicar na citação abre um popover/drawer com o trecho literal (`quote`/`text`), modalidade (`PDF`/`OCR`/`Áudio`) e score.
   - **Bloco de Limitações / Lacunas:** seção colapsável discreta quando `retrieval.gaps` ou `proposal.limitations` não estiverem vazios.
   - **Estado de Abstenção Segura:** visual informativo neutro (ícone de escudo/info) explicando que não houve evidência suficiente na base para responder com segurança.
   - **Card de Proposta de Agenda (Preview + Confirmação):** lista os blocos sugeridos (`ProposedBlock`), exibe `diff_summary`, destaca minutos `unallocated` se houver e apresenta os botões **"Confirmar e aplicar"** e **"Descartar"**.
4. **Seletor de Sessões Persistentes:** permite alternar entre sessões anteriores sem perder o histórico de conversas nem o estado da agenda.

---

## 5. Acessibilidade e Qualidade Visual

- Contraste mínimo **WCAG AA** (`4.5:1` para texto normal, `3:1` para texto grande e controles).
- Navegação completa por teclado e `focus-visible` preservado em todos os componentes Radix/`shadcn/ui`.
- Estados explícitos de carregamento (*skeleton* na agenda e indicador discreto de etapas no chat: *Pesquisando documentos → Planejando → Validando*), estado vazio orientativo e tratamento gracioso de falhas da API.
