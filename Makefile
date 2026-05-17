# fin-rag dev/ops targets
COMPOSE := docker compose -f infra/docker-compose.yml --env-file infra/.env

.PHONY: help up up-local down logs ps build rebuild migrate shell-api shell-db psql backup debug test fmt lint

help:
	@echo "Targets:"
	@echo "  up          start pilot stack (LLM_PROVIDER=openai mode, no GPU container)"
	@echo "  up-local    start pilot stack with vLLM GPU profile"
	@echo "  down        stop and remove containers"
	@echo "  logs        tail all logs"
	@echo "  debug       split-tail logs of every service"
	@echo "  build       build images"
	@echo "  rebuild     no-cache rebuild"
	@echo "  migrate     run alembic upgrade head against the running db"
	@echo "  psql        open a psql shell against the db"
	@echo "  backup      run pg + minio backup scripts"
	@echo "  test        run api + app test suites"

up:
	$(COMPOSE) up -d

up-local:
	$(COMPOSE) --profile local up -d

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f --tail=100

debug:
	@command -v tmux >/dev/null || (echo "tmux required for split tail"; exit 1)
	tmux new-session -d -s finrag "$(COMPOSE) logs -f --tail=200 app" \;\
		split-window -h "$(COMPOSE) logs -f --tail=200 api" \;\
		split-window -v "$(COMPOSE) logs -f --tail=200 worker" \;\
		select-pane -t 0 \;\
		split-window -v "$(COMPOSE) logs -f --tail=200 db" \;\
		select-pane -t 2 \;\
		split-window -v "$(COMPOSE) logs -f --tail=200 store" \;\
		attach

build:
	$(COMPOSE) build

rebuild:
	$(COMPOSE) build --no-cache

ps:
	$(COMPOSE) ps

migrate:
	$(COMPOSE) exec api alembic upgrade head

shell-api:
	$(COMPOSE) exec api bash

shell-db:
	$(COMPOSE) exec db bash

psql:
	$(COMPOSE) exec db psql -U $${POSTGRES_USER:-finrag} -d $${POSTGRES_DB:-finrag}

backup:
	bash infra/scripts/backup-pg.sh
	bash infra/scripts/backup-minio.sh

test:
	$(COMPOSE) exec api pytest -q
	npm test --prefix .

fmt:
	$(COMPOSE) exec api ruff format .
	npm run lint --prefix .

lint:
	$(COMPOSE) exec api ruff check .
	npm run lint --prefix .
