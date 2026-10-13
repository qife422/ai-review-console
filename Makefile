PYTHON ?= .venv/bin/python
PIP ?= .venv/bin/pip
COMPOSE_PROJECT ?= ai-review-console-upgrade
COMPOSE = docker compose -p $(COMPOSE_PROJECT)

.PHONY: install test lint audit fixtures web-install web-test web-build validate-langflow migrate stack

install:
	$(PIP) install -r requirements.lock
	$(PIP) install -e '.[dev]'

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check review_core api tests scripts

audit:
	$(PYTHON) -m pip_audit --requirement requirements.lock
	cd frontend && npm audit --omit=dev

fixtures:
	$(PYTHON) scripts/generate_fixtures.py

web-install:
	cd frontend && npm ci

web-test:
	cd frontend && npm test -- --run

web-build:
	cd frontend && npm run build

validate-langflow:
	$(PYTHON) scripts/validate_langflow.py

migrate:
	$(PYTHON) -m api.app.migrations

stack:
	$(COMPOSE) build
	$(COMPOSE) up -d postgres langflow
	$(COMPOSE) run --no-deps storage-init
	$(COMPOSE) run migrate
	$(COMPOSE) run flow-init
	$(COMPOSE) up -d --no-deps api worker web
