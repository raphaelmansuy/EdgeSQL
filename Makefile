PY ?= .venv/bin/python
PIP ?= .venv/bin/pip
PORT ?= 8765
SITE_PORT ?= 8766
HOST ?= 127.0.0.1

.DEFAULT_GOAL := help
.PHONY: help venv install dev site test test-lib test-http test-docs test-e2e screenshots lint fmt check \
        build release-check publish-test publish clean

help: ## Show this list
	@grep -E '^[a-z][a-z0-9_-]*:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  \033[1m%-14s\033[0m %s\n", $$1, $$2}'

venv: ## Create the local virtual environment
	@test -d .venv || python3 -m venv .venv

install: venv ## Install the library and dev extras
	$(PIP) install -q --upgrade pip
	$(PIP) install -q -e ".[dev]"
	@$(PY) -m playwright install chromium

dev: venv ## Serve the report helper on 127.0.0.1 (PORT=8765 by default)
	@$(PY) -c "import fastapi, uvicorn, sqlglot" 2>/dev/null || $(MAKE) install
	@echo "Report helper: http://$(HOST):$(PORT)"
	PYTHONPATH=$(CURDIR) $(PY) -m uvicorn app:app --app-dir examples/report-helper \
		--host $(HOST) --port $(PORT) --reload

site: ## Serve the tutorial site on 127.0.0.1 (SITE_PORT=8766 by default)
	@echo "Tutorial site: http://$(HOST):$(SITE_PORT)"
	@$(PY) -m http.server $(SITE_PORT) --bind $(HOST) --directory docs

test: ## Run every test
	$(PY) -m pytest -q

test-lib: ## Run the library and official SQL suites
	$(PY) -m pytest -q tests/test_library.py tests/test_postgres_suite.py tests/test_databricks_suite.py

test-http: ## Run the HTTP status map
	$(PY) -m pytest -q tests/test_http.py

test-docs: ## Run the docs site checks
	$(PY) -m pytest -q tests/test_docs.py

test-e2e: ## Run the browser flow and refresh the screenshots
	$(PY) -m pytest -q tests/test_screen.py

screenshots: test-e2e ## Refresh the screenshots and list them
	@ls specs/01-first-spec/e2e/screenshots

lint: ## Check style, imports, and formatting
	$(PY) -m ruff check .
	$(PY) -m ruff format --check .

fmt: ## Apply formatting and safe lint fixes
	$(PY) -m ruff check --fix .
	$(PY) -m ruff format .

check: lint test ## Run lint and every test

build: ## Build the sdist and the wheel into dist/
	@$(PY) -c "import build" 2>/dev/null || $(MAKE) install
	rm -rf dist build
	$(PY) -m build
	@ls -la dist

release-check: build ## Validate the distribution metadata
	@$(PY) -c "import twine" 2>/dev/null || $(PIP) install -q twine
	$(PY) -m twine check dist/*
	@echo "Metadata is valid."

publish-test: release-check ## Upload to TestPyPI (needs TWINE_USERNAME and TWINE_PASSWORD)
	$(PY) -m twine upload --repository testpypi dist/*

publish: release-check ## Upload to PyPI (needs TWINE_USERNAME and TWINE_PASSWORD)
	$(PY) -m twine upload dist/*

clean: ## Remove caches and build output
	rm -rf .pytest_cache .ruff_cache build dist
	find . -name __pycache__ -type d -prune -not -path "./.venv/*" -exec rm -rf {} +
