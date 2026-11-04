## Contexto da Entrega
- **Issue vinculada:** Closes #

## O que foi feito?
- 
- 
- 

## Como o revisor deve testar localmente?
1. Atualize suas branches: `git fetch origin`
2. Acesse a branch: `git checkout <nome-desta-branch>`
3. Execute os testes unitarios:
   ```bash
   pytest -v
   ```

## Checklist do Desenvolvedor
- [ ] O codigo passou sem alertas no linter local (`ruff check .`)
- [ ] O codigo esta formatado no padrao (`ruff format .`)
- [ ] Todos os testes unitarios passaram (`pytest -v`)
- [ ] Nao subi ficheiros locais desnecessarios (.env, dados ou caches)
