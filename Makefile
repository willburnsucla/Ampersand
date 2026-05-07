.PHONY: help install db-up db-down migrate codegen dev dev-mock \
        test test-backend test-frontend lint format

BACKEND_DIR  := backend
FRONTEND_DIR := frontend
SHARED_DIR   := shared

# ── Help ──────────────────────────────────────────────────────────────────────
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── Install ───────────────────────────────────────────────────────────────────
install: ## Install all dependencies (backend + frontend)
	cd $(BACKEND_DIR) && uv sync
	cd $(FRONTEND_DIR) && npm install

# ── Database ──────────────────────────────────────────────────────────────────
db-up: ## Start Postgres+pgvector via Docker Compose
	docker compose up -d db
	@echo "Waiting for DB to be healthy..."
	@until docker compose exec db pg_isready -U ampersand > /dev/null 2>&1; do sleep 1; done
	@echo "DB is ready."

db-down: ## Stop and remove DB container (data volume persists)
	docker compose down

db-destroy: ## Stop DB and DELETE data volume
	docker compose down -v

# ── Migrations ────────────────────────────────────────────────────────────────
migrate: ## Run Alembic migrations (requires DB running)
	cd $(BACKEND_DIR) && uv run alembic upgrade head

migrate-new: ## Create a new Alembic migration (usage: make migrate-new MSG="description")
	cd $(BACKEND_DIR) && uv run alembic revision --autogenerate -m "$(MSG)"

migrate-down: ## Downgrade one migration
	cd $(BACKEND_DIR) && uv run alembic downgrade -1

# ── Codegen ───────────────────────────────────────────────────────────────────
codegen: ## Regenerate Pydantic models + TS types from shared JSON schemas
	@echo "→ Generating Pydantic v2 models..."
	mkdir -p $(BACKEND_DIR)/app/domain/generated
	cd $(SHARED_DIR) && uv run --with datamodel-code-generator \
		datamodel-codegen \
			--input schemas \
			--input-file-type jsonschema \
			--output ../$(BACKEND_DIR)/app/domain/generated \
			--output-model-type pydantic_v2.BaseModel \
			--use-annotated \
			--field-constraints
	@echo "→ Generating TypeScript types..."
	mkdir -p $(FRONTEND_DIR)/lib/types/generated
	cd $(SHARED_DIR) && npx --yes json-schema-to-typescript \
		--input schemas \
		--output ../$(FRONTEND_DIR)/lib/types/generated \
		--no-additionalProperties
	@echo "Codegen complete."

# ── Dev servers ───────────────────────────────────────────────────────────────
dev-mock: ## Start mock backend (no DB needed) + Next.js dev server
	@echo "Starting mock backend on :8000 ..."
	cd $(BACKEND_DIR) && AMPERSAND_BACKEND_MODE=mock \
		uv run uvicorn app.main:app --reload --port 8000 &
	@echo "Starting Next.js dev server on :3000 ..."
	cd $(FRONTEND_DIR) && npm run dev

dev: db-up migrate ## Start real backend + Next.js dev server (requires .env)
	@echo "Starting real backend on :8000 ..."
	cd $(BACKEND_DIR) && AMPERSAND_BACKEND_MODE=real \
		uv run uvicorn app.main:app --reload --port 8000 &
	@echo "Starting Next.js dev server on :3000 ..."
	cd $(FRONTEND_DIR) && npm run dev

# ── Tests ─────────────────────────────────────────────────────────────────────
test-backend: ## Run pytest
	cd $(BACKEND_DIR) && uv run pytest tests/ -v

test-frontend: ## Run Next.js tests
	cd $(FRONTEND_DIR) && npm test

test: test-backend test-frontend ## Run all tests

# ── Lint / Format ─────────────────────────────────────────────────────────────
lint: ## Lint backend (ruff) + frontend (eslint)
	cd $(BACKEND_DIR) && uv run ruff check app/ tests/
	cd $(FRONTEND_DIR) && npm run lint

format: ## Format backend (ruff format) + frontend (prettier)
	cd $(BACKEND_DIR) && uv run ruff format app/ tests/
	cd $(FRONTEND_DIR) && npx prettier --write .
