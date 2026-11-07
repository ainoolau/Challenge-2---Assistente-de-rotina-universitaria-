### Como Rodar o Banco Vetorial Localmente

A infraestrutura dos serviços de apoio (Qdrant e MLflow) é orquestrada via Docker Compose na pasta `infra/`.

#### Pré-requisitos
- Docker Engine (>= 24.0) instalado e ativo
- Docker Compose v2 instalado (`docker compose version`)

---

#### 1. Subir os serviços em background
Execute a partir da raiz do projeto:
```bash
docker compose -f infra/docker-compose.yml up -d