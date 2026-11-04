# Assistente de Rotina e Gestao de Tempo

Assistente inteligente para universitarios em multijornada (faculdade, trabalho, projetos e estudo autonomo).

## Stack Principal
- Python 3.11
- FastAPI
- MLflow
- Pytest & Ruff

---

## Guia de Bolso Git para a Equipa

### 1. Atualizar a maquina antes de comecar
```bash
git checkout develop
git pull origin develop
```

### 2. Criar a branch de trabalho
```bash
git checkout -b feat/nome-da-tarefa
```

### 3. Validar e gravar as alteracoes
```bash
ruff format .
ruff check .
pytest -v
git add .
git commit -m "feat: descricao curta da alteracao"
```

### 4. Enviar a branch e abrir o PR
```bash
git push -u origin feat/nome-da-tarefa
```
- Aceder ao GitHub e abrir o Pull Request com destino a branch `develop`.

### 5. Como rever o PR de um colega
```bash
git fetch origin
git checkout feat/branch-do-colega
pytest -v
```
- Apos testar, aprovar na interface do GitHub em "Files changed" -> "Review changes" -> "Approve".
