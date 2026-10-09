PYTHON ?= .venv/bin/python
PIP ?= .venv/bin/pip

.PHONY: install test lint audit fixtures web-install web-test web-build validate-langflow

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
	cd frontend && npm install

web-test:
	cd frontend && npm test -- --run

web-build:
	cd frontend && npm run build

validate-langflow:
	$(PYTHON) scripts/validate_langflow.py
