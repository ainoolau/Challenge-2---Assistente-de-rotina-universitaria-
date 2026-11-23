# DESIGN — Diretrizes de UX, Interface e Sistema Visual do Vezo

> **Interface Oficial:** PWA responsivo em **Next.js / React + Tailwind CSS + shadcn/ui** (`frontend/`)
> **Status da Identidade Visual:** **Consolidada (`TASK-F1-03` / `#46`)** — paleta oficial da marca Vezo codificada em [`frontend/src/styles/tokens.css`](../frontend/src/styles/tokens.css) e [`frontend/src/app/globals.css`](../frontend/src/app/globals.css), com preview interativo em [`docs/design_tokens_preview.html`](design_tokens_preview.html) e guia visual anexado à Issue/PR `#46`.
> **Assinaturas da Marca:** *"Sua rotina, no seu ritmo."* · *"Simplifique seu dia a dia."*

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
| **Estilização** | Tailwind CSS + CSS Variables (Design Tokens) | Produtividade e manutenção centralizada da paleta sem refatorar componentes. |
| **Biblioteca de Componentes** | `shadcn/ui` (sobre Radix UI) + `lucide-react` | Componentes acessíveis, limpos, personalizáveis e sem visual genérico engessado. |
| **PWA** | `manifest.webmanifest` + ícones + layout responsivo | Permite "Adicionar à tela inicial" no celular com navegação fluida. |

---

## 3. Sistema de Design Tokens e Identidade Oficial do Vezo

Todos os componentes em `frontend/` devem consumir **exclusivamente tokens semânticos** via CSS variables definidos em [`frontend/src/styles/tokens.css`](../frontend/src/styles/tokens.css) (importado por [`frontend/src/app/globals.css`](../frontend/src/app/globals.css)). **Nunca** espalhar códigos hexadecimais hardcoded nos componentes.

### 3.1. Paleta Oficial da Marca (Primitivos)

Extraída diretamente do guia oficial de identidade visual da marca Vezo (evidência anexada na Issue/PR `#46`):

| Nome Oficial | Variável Primitiva | Hexadecimal | RGB | Papel na Identidade |
| :--- | :--- | :--- | :--- | :--- |
| **Azul-Oceano** | `--vezo-ocean` | `#094D60` | `9, 77, 96` | Cor primária no modo claro, ações principais, aulas (`class`) |
| **Turquesa Vibrante** | `--vezo-turquoise` | `#25CBC1` | `37, 203, 193` | Cor primária no modo escuro, acento de foco e propostas da IA |
| **Verde-Folha Claro** | `--vezo-leaf` | `#94E09F` | `148, 224, 159` | Destaque positivo no modo escuro, estudo confirmado e confirmação |
| **Verde-Menta** | `--vezo-mint` | `#75D0A4` | `117, 208, 164` | Estado de sucesso no modo escuro e base de tons de confirmação |
| **Amarelo-Pastel** | `--vezo-butter` | `#FCEC95` | `252, 236, 149` | Avisos, lacunas documentais e horas `unallocated` |
| **Fundo Escuro Base** | `--vezo-ink-dark` | `#101C1C` | `16, 28, 28` | `--foreground` no modo claro e `--background` no modo escuro |
| **Superfície Escura** | `--vezo-surface-dark` | `#1B2A2F` | `27, 42, 47` | `--card` e `--popover` no modo escuro |
| **Superfície Elevada** | `--vezo-surface-elevated` | `#27373D` | `39, 55, 61` | `--secondary` no modo escuro |

> **Regra de uso:** os primitivos `--vezo-*` existem apenas como base em `tokens.css`. Os componentes devem referenciar os tokens semânticos das seções **3.2** e **3.3**.

### 3.2. Tokens Semânticos Base (`shadcn/ui` — Claro e Escuro)

| Token | Modo Claro (`:root`) | Modo Escuro (`.dark`) | Papel na Interface |
| :--- | :--- | :--- | :--- |
| `--background` | `#F6FAFA` | `#101C1C` | Fundo principal da aplicação |
| `--foreground` | `#101C1C` | `#F0F7F7` | Texto primário |
| `--card` / `--card-foreground` | `#FFFFFF` / `#101C1C` | `#1B2A2F` / `#F0F7F7` | Cartões de agenda, painéis e containers |
| `--popover` / `--popover-foreground` | `#FFFFFF` / `#101C1C` | `#1B2A2F` / `#F0F7F7` | Popovers de citação, menus e drawers |
| `--primary` / `--primary-foreground` | `#094D60` / `#FFFFFF` | `#25CBC1` / `#072226` | Ações principais ("Confirmar plano", envio no chat) |
| `--secondary` / `--secondary-foreground` | `#EBF3F4` / `#101C1C` | `#27373D` / `#E6F2F2` | Botões secundários e chips de filtro (Hoje/Semana/Mês) |
| `--muted` / `--muted-foreground` | `#EDF4F4` / `#42585E` | `#1F3036` / `#9FB7BC` | Fundos sutis, metadados, horários e timestamps |
| `--accent` / `--accent-foreground` | `#E1F6F5` / `#094D60` | `#123C47` / `#94E09F` | Hover, item selecionado e destaques discretos |
| `--border` | `#C5D7DA` | `#324950` | Bordas finas `1px` e divisórias |
| `--input` | `#738F96` | `#607F87` | Borda de inputs/selects (contraste UI `>= 3:1`) |
| `--ring` | `#094D60` | `#25CBC1` | Anel de foco acessível (`focus-visible`) |
| `--destructive` / `--destructive-foreground` | `#B91C1C` / `#FFFFFF` | `#F87171` / `#3B0808` | Conflitos (`input_conflicts`), erro `409` e ações destrutivas |
| `--destructive-subtle` / `*-foreground` | `#FEF2F2` / `#991B1B` | `#2E1518` / `#FCA5A5` | Banners e alertas suaves de conflito/erro |
| `--warning` / `--warning-foreground` | `#9A6700` / `#FFFFFF` | `#FCEC95` / `#101C1C` | Lacunas, prazos apertados e minutos `unallocated` |
| `--warning-subtle` / `*-foreground` | `#FEFBE6` / `#6B4700` | `#2C2814` / `#FCEC95` | Banners e alertas suaves de lacunas/atenção |
| `--warning-accent` / `*-foreground` | `#FCEC95` / `#101C1C` | `#FCEC95` / `#101C1C` | Badge sólido em Amarelo-Pastel oficial com texto escuro |
| `--success` / `--success-foreground` | `#176B45` / `#FFFFFF` | `#75D0A4` / `#0B2419` | Plano auditado/confirmado e status saudável |
| `--success-subtle` / `*-foreground` | `#ECFDF3` / `#135336` | `#132E24` / `#94E09F` | Banners de confirmação aplicada |

### 3.3. Tokens Semânticos de Domínio (Agenda Vezo)

Classes utilitárias prontas em `tokens.css`: `.vezo-slot-class`, `.vezo-slot-work`, `.vezo-slot-commute`, `.vezo-slot-sleep`, `.vezo-slot-conflict`, `.vezo-slot-study-proposed`, `.vezo-slot-study-confirmed`.

| Token | Tipo (`ScheduleSlot.kind` / Estado) | Claro (`bg` / `fg` / `border`) | Escuro (`bg` / `fg` / `border`) | Tratamento Visual Obrigatório |
| :--- | :--- | :--- | :--- | :--- |
| `--slot-class` | Aulas (`class`) | `#E7F4F7` / `#083D4C` / `#094D60` | `#0D3644` / `#D8F6F8` / `#25CBC1` | Bloco sólido com barra lateral esquerda (`4px`) primária |
| `--slot-work` | Trabalho / Residência (`work`) | `#EEF2F3` / `#1B2A2F` / `#42585E` | `#23343A` / `#E6F2F2` / `#6F8B92` | Bloco sólido neutro estruturado com barra lateral (`4px`) |
| `--slot-commute` | Deslocamento (`commute`) | `#F4F7F7` / `#374B50` / `#7A9399` | `#18262B` / `#BDD0D4` / `#5A757D` | Faixa compacta e discreta (`1px` sólido) |
| `--slot-sleep` | Sono protegido (`sleep`, `22h–06h`) | `#E9EFF1` (+ listra `#DCE6E9`) / `#2B4046` / `#617B82` | `#162328` (+ listra `#1E2E34`) / `#B8CDD1` / `#5D7980` | **Faixa suave hachurada diagonal** + ícone de cadeado (`Lock`) — não editável pela IA |
| `--slot-conflict` | Conflito pré-existente (`input_conflicts`) | `#FEF2F2` / `#991B1B` / `#B91C1C` | `#2E1518` / `#FCA5A5` / `#F87171` | Borda de alerta (`1.5px` + barra `4px`) + badge **"Conflito"** + botão *"Resolver com Vezo"* |
| `--slot-study-proposed` | Estudo proposto (`ProposedBlock`) | `#E5F9F7` / `#094D60` / `#0E7A74` | `#113335` / `#75ECE4` / `#25CBC1` | **Borda tracejada (`2px dashed`)** + badge **"Proposta"** (nunca sólido antes da confirmação) |
| `--slot-study-confirmed` | Estudo confirmado (`study` após aceite) | `#E9F8F0` / `#135336` / `#1F7A52` | `#143025` / `#94E09F` / `#75D0A4` | Bloco sólido com barra lateral verde-menta após clique em Confirmar |

### 3.4. Matriz de Validação WCAG AA (Fórmula WCAG 2.1)

Todos os pares críticos de texto (`>= 4.5:1`) e controles/bordas (`>= 3.0:1`) foram validados matematicamente nos dois temas:

| Par Avaliado | Requisito | Contraste Claro | Contraste Escuro | Status |
| :--- | :--- | :--- | :--- | :--- |
| `--foreground` sobre `--background` | `>= 4.5:1` | `16.58:1` | `16.06:1` | PASS (AAA) |
| `--card-foreground` sobre `--card` | `>= 4.5:1` | `17.43:1` | `13.64:1` | PASS (AAA) |
| `--muted-foreground` sobre `--background` / `--card` | `>= 4.5:1` | `7.16:1` / `7.53:1` | `8.28:1` / `7.03:1` | PASS (AAA) |
| `--primary-foreground` sobre `--primary` | `>= 4.5:1` | `9.37:1` | `8.21:1` | PASS (AAA) |
| `--accent-foreground` sobre `--accent` | `>= 4.5:1` | `8.34:1` | `7.61:1` | PASS (AAA) |
| `--input` (borda) sobre `--card` | `>= 3.0:1` | `3.44:1` | `3.44:1` | PASS (AA UI) |
| `--ring` (foco) sobre `--background` | `>= 3.0:1` | `8.91:1` | `8.62:1` | PASS (AA UI) |
| `--destructive-foreground` sobre `--destructive` | `>= 4.5:1` | `6.47:1` | `6.20:1` | PASS (AA+) |
| `--destructive-subtle-foreground` sobre `--destructive-subtle` | `>= 4.5:1` | `7.60:1` | `8.95:1` | PASS (AAA) |
| `--warning-foreground` sobre `--warning` | `>= 4.5:1` | `4.87:1` | `14.58:1` | PASS (AA+) |
| `--warning-subtle-foreground` sobre `--warning-subtle` | `>= 4.5:1` | `7.98:1` | `12.37:1` | PASS (AAA) |
| `--warning-accent-foreground` sobre `--warning-accent` (`#FCEC95`) | `>= 4.5:1` | `14.58:1` | `14.58:1` | PASS (AAA) |
| `--success-foreground` sobre `--success` | `>= 4.5:1` | `6.51:1` | `8.84:1` | PASS (AA+) |
| `--success-subtle-foreground` sobre `--success-subtle` | `>= 4.5:1` | `8.59:1` | `9.30:1` | PASS (AAA) |
| `--slot-class` (`fg` / `bg`) | `>= 4.5:1` | `10.48:1` | `11.34:1` | PASS (AAA) |
| `--slot-work` (`fg` / `bg`) | `>= 4.5:1` | `13.13:1` | `11.30:1` | PASS (AAA) |
| `--slot-commute` (`fg` / `bg`) | `>= 4.5:1` | `8.53:1` | `9.72:1` | PASS (AAA) |
| `--slot-sleep` (`fg` / `bg`) | `>= 4.5:1` | `9.40:1` | `9.72:1` | PASS (AAA) |
| `--slot-conflict` (`fg` / `bg` · `border` / `bg`) | `>= 4.5:1` / `3:1` | `7.60:1` · `5.91:1` | `8.95:1` · `6.14:1` | PASS (AAA) |
| `--slot-study-proposed` (`fg` / `bg` · `border` / `bg`) | `>= 4.5:1` / `3:1` | `8.57:1` · `4.74:1` | `9.60:1` · `6.71:1` | PASS (AAA) |
| `--slot-study-confirmed` (`fg` / `bg`) | `>= 4.5:1` | `8.26:1` | `9.07:1` | PASS (AAA) |

### 3.5. Tipografia, Escala de Espaçamento, Raios e Responsividade

- **Famílias Tipográficas:**
  - **Sans (`--font-sans`):** `Inter` (ou `Plus Jakarta Sans` via `next/font/google`) com fallback do sistema — alta legibilidade para horários, tabelas e blocos densos.
  - **Mono (`--font-mono`):** `JetBrains Mono` / `ui-monospace` — uso exclusivo em horários tabulares (`font-variant-numeric: tabular-nums`), badges de citação (`[C1]`) e códigos de erro/versão.
- **Escala Tipográfica:**
  - `xs` (`12px` / `0.75rem`): metadados, timestamps, score de citação e badges.
  - `sm` (`14px` / `0.875rem`): labels de formulário, itens de agenda e descrições secundárias.
  - `base` (`16px` / `1rem`): corpo principal, inputs (evita auto-zoom no iOS Safari) e mensagens do chat.
  - `lg` (`18px` / `1.125rem`): título de cards e modais.
  - `xl` (`20px` / `1.25rem`): cabeçalho de seção.
  - `2xl` (`24px`) no mobile / `3xl` (`30px`) no desktop: título da tela.
- **Espaçamento e Bordas:** grade base de `4px` (`--space-1` a `--space-12`), bordas finas `--border-width: 1px`, raios sóbrios (`6px` badges, `8px` inputs/botões/slots, `10px` cards, `12px` modais).
- **Responsividade & Toque:**
  - Mobile-first a partir de `360px` (`--breakpoint-mobile-min`), quebra para layout de duas colunas em `>= 1024px` (`--breakpoint-desktop`).
  - Todo botão, tab da barra inferior, checkbox/label clicável e botão de fechar modal deve ter alvo de toque mínimo de **`44px × 44px`** (`--touch-target-min: 44px`).

---

## 4. Arquitetura de Telas e Fluxos do MVP

### 4.1. Layout Geral (Desktop vs. Mobile PWA)

- **Desktop (`>= 1024px`):** layout em duas colunas com barra lateral recolhível de sessões:
  - **Esquerda (60%–65%):** Dashboard de Rotina (Hoje / Semana / Mês + Prioridades + Alertas de Conflitos + Visualizador de Agenda).
  - **Direita (35%–40%):** Painel fixo do **Chat Assistente Vezo**.
- **Mobile PWA (`< 1024px`):** barra de navegação inferior fixa com 3 abas principais (**Hoje/Agenda**, **Assistente**, **Prioridades/Sessões**) e targets de toque `>= 44px`.

### 4.2. Especificação dos Componentes Mínimos (`shadcn/ui` + `lucide-react`)

Guia pronto para implementação direta nas tasks `#47`, `#45`, `#48` e `#49`:

#### 1. Formulário / Input com Estados de Erro (`409` / `422`)
- **Base `shadcn/ui`:** `Input`, `Label`, `Select`, `Checkbox`, `Alert`.
- **Regras visuais:**
  - Altura mínima `44px` (`--touch-target-min`), fonte `16px` (`--text-base`), borda `1px solid var(--input)` sobre `--card`, foco com `2px solid var(--ring)`.
  - **Estado `422` (Validação de campo — ex.: `end <= start` ou `sleep_start == sleep_end`):** borda `var(--destructive)`, mensagem inline abaixo do campo em `var(--destructive-subtle-foreground)` com `aria-invalid="true"` e `aria-describedby`.
  - **Estado `409` (Conflito / Invasão de Sono Protegido ou versão defasada):** banner `Alert` usando `var(--destructive-subtle)` + borda `var(--destructive)` + ícone `ShieldAlert`, explicando em português qual regra foi protegida (ex.: *"Este horário invade sua janela de sono protegido (22:00–06:00). Ajuste o horário ou suas preferências."*).

#### 2. Card de Evento / Bloco de Agenda
- **Base `shadcn/ui`:** `Card` + classes `.vezo-slot-*` de `tokens.css` + ícones `lucide-react` (`GraduationCap`, `Briefcase`, `Bus`, `Moon`/`Lock`, `AlertTriangle`, `Sparkles`/`CalendarPlus`, `CheckCircle2`).
- **Anatomia obrigatória:**
  - Linha 1: horário em fonte tabular (`08:00 – 09:50`) + badge de estado (ex.: *Fixo*, *Protegido*, *Conflito*, *Proposta*).
  - Linha 2: título do compromisso (`label`, máx. 2 linhas com truncamento limpo) + metadado opcional (buffer ou meta vinculada).
  - **Distinção inequívoca:** compromissos fixos têm borda sólida + barra lateral `4px`; sono tem fundo hachurado + ícone `Lock`; propostas da IA têm **borda `2px dashed`** e só viram bloco sólido (`.vezo-slot-study-confirmed`) após confirmação explícita.

#### 3. Badges de Carga e Status
- **Base `shadcn/ui`:** `Badge` (borda `1px`, raio `--radius-sm` ou `--radius-full`, sem sombras neon).
- **Variantes oficiais:**
  - **Fixo:** `--secondary` / `--secondary-foreground` + ícone `Pin`.
  - **Sono Protegido:** `--slot-sleep-bg` / `--slot-sleep-fg` + ícone `Lock`.
  - **Conflito:** `--destructive-subtle` / `--destructive-subtle-foreground` + borda `--destructive` + ícone `AlertTriangle`.
  - **Proposta (Pendente):** `--slot-study-proposed-bg` / `--slot-study-proposed-fg` + borda tracejada `--slot-study-proposed-border`.
  - **Confirmado / Auditado:** `--success-subtle` / `--success-subtle-foreground` + ícone `Check`.
  - **Abstenção Segura / Lacuna:** `--warning-subtle` / `--warning-subtle-foreground` (ou `--warning-accent` / `--warning-accent-foreground` para destaque compacto) + ícone `ShieldCheck` ou `Info`.
  - **Carga Diária:** indicador limpo `Leve` (`--success-subtle`), `Moderada` (`--accent`), `Intensa` (`--warning-subtle`), `Sobrecarga` (`--destructive-subtle`).

#### 4. Modal / Drawer de Confirmação de Proposta (`requires_confirmation=True`)
- **Base `shadcn/ui`:** `Dialog` (desktop) / `Drawer` ou `Sheet` (mobile), `Button`, `Separator`, `Alert`.
- **Anatomia obrigatória:**
  - Cabeçalho claro: título (*"Revisar proposta de agenda"*) + aviso de que **nenhuma alteração foi aplicada ainda** (`base_version` exibida discretamente).
  - Lista de `diff` (blocos **Adicionados**, **Movidos** `de → para` e **Preservados**) renderizados com `.vezo-slot-study-proposed`.
  - Banner `warning` explícito caso existam minutos `unallocated` (declarando que sono e compromissos fixos foram preservados).
  - Rodapé com ações claras (`>= 44px`): botão secundário **"Descartar"** (`POST .../reject`) e botão primário **"Confirmar e aplicar"** (`--primary`, `POST .../confirm`).

#### 5. Card de Citação Documental (Chat Assistente)
- **Base `shadcn/ui`:** `Card`, `Badge`, `Collapsible` / `Popover` + ícone `FileText` / `Mic` / `Image`.
- **Anatomia obrigatória:**
  - Chip clicável inline no texto da resposta: `[C1: edital_residencia_02.pdf]` em `--accent` / `--accent-foreground` com borda `1px`.
  - Ao clicar, exibe o **Card de Citação** contendo: nome do documento (`title`/`source`), localizador (`page_or_time`, ex.: `p. 5` ou `00:12-00:45`), badge de modalidade (`PDF`, `OCR`, `Áudio`) e score (`0.68`) + **trecho literal recuperado** em bloco com barra lateral `var(--primary)` e fundo `var(--muted)`.

### 4.3. Componentes de Tela (Visões do MVP)

1. **Seletor de Visão (Hoje / Semana / Mês):**
   - **Hoje:** timeline detalhada por hora com foco imediato no próximo compromisso, sono protegido e janelas livres.
   - **Semana:** grade semanal destacando carga por dia, prioridades da semana e conflitos sobrepostos.
   - **Mês:** calendário macro destacando prazos críticos (provas, entregas, trancamento, metas de estudo).
2. **Painel de Cenário do Estudante (Prioridades & Conflitos):**
   - Lista ordenada de metas de estudo (`StudyGoal`) com prazo, prioridade (`1–5`) e minutos restantes.
   - Banner acionável quando houver `input_conflicts` (ex.: CLT vs. Aula de Econometria), deixando claro que o Vezo **não move compromissos fixos sozinho** e oferecendo envio direto ao chat.
3. **Chat Assistente Integrado:**
   - Mensagens com badges de citação clicáveis, bloco colapsável de lacunas/limitações (`gaps`/`limitations`), estado visual dedicado para **Abstenção Segura** e card de proposta de agenda com confirmação explícita.
4. **Seletor de Sessões Persistentes:** permite alternar entre sessões anteriores sem perder histórico nem agenda.

---

## 5. Acessibilidade e Qualidade Visual

- Contraste mínimo **WCAG AA** (`4.5:1` para texto normal, `3:1` para texto grande e controles) validado em ambos os modos (seção 3.4).
- Navegação completa por teclado e `focus-visible` (`2px solid var(--ring)`) preservado em todos os componentes Radix/`shadcn/ui`.
- Estados explícitos de carregamento (*skeleton* na agenda e indicador discreto de etapas no chat: *Pesquisando documentos → Planejando → Validando*), estado vazio orientativo e tratamento gracioso de falhas da API (`503` / offline).
- **Preview visual interativo:** abra [`docs/design_tokens_preview.html`](design_tokens_preview.html) no navegador para inspecionar todos os tokens (com alternância Claro/Escuro) e os 5 componentes mínimos renderizados.
