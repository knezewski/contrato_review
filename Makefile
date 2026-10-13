# Contrato Review — common tasks. Run `make help` for the list.

PY        ?= .venv/bin/python
PYTHON    ?= python3.11
UV        ?= uv
HOST      ?= 127.0.0.1
PORT      ?= 8000
LAWS      ?= data/laws
CHROMA    ?= data/chroma

# The embedding model is cached locally after the first download.
export HF_HUB_OFFLINE ?= 0

.DEFAULT_GOAL := help
.PHONY: help venv install fixtures index index-reset check run run-dev \
        test test-unit test-contract test-integration test-all coverage \
        lint format check-format clean distclean

help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z_-]+:.*##/ {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# ---------------------------------------------------------------- setup

venv: ## Create the project virtualenv in .venv (Python 3.11)
	$(UV) venv --python $(PYTHON) .venv

install: ## Install runtime and dev dependencies into .venv
	@test -x $(PY) || $(MAKE) venv
	$(UV) pip install --python $(PY) -r requirements.txt -r requirements-dev.txt

fixtures: ## Regenerate synthetic contract fixtures in tests/fixtures/
	$(PY) tests/fixtures/make_fixtures.py

# ---------------------------------------------------------------- knowledge base

index: ## Build the norm index from data/laws (adds to an existing index)
	$(PY) -m src.kb.index build --laws $(LAWS)

index-reset: ## Rebuild the norm index from scratch (deletes data/chroma)
	rm -rf $(CHROMA)
	$(PY) -m src.kb.index build --laws $(LAWS) --reset

check: ## Run the index check query (prints the norms found and their scores)
	$(PY) -m src.kb.index check

# ---------------------------------------------------------------- run

run: ## Start the API server (uvicorn) on HOST:PORT (default 127.0.0.1:8000)
	$(PY) -m uvicorn src.api.app:app --host $(HOST) --port $(PORT)

run-dev: ## Start the API server with auto-reload for development
	$(PY) -m uvicorn src.api.app:app --reload --host $(HOST) --port $(PORT)

# ---------------------------------------------------------------- tests

test: test-unit test-contract ## Run unit and contract tests (same set as CI)

test-unit: ## Run unit tests (fakes only)
	$(PY) -m pytest tests/unit -q

test-contract: ## Run HTTP contract tests (needs the embedding model)
	$(PY) -m pytest tests/contract -q

test-integration: ## Run integration tests on the real index (needs the embedding model)
	$(PY) -m pytest tests/integration -m integration -q

test-all: ## Run every test, including the ones marked integration
	$(PY) -m pytest tests -m "" -q

coverage: ## Run unit and contract tests with coverage (writes coverage.xml)
	$(PY) -m pytest tests/unit tests/contract --cov=src --cov-branch \
		--cov-report=term-missing --cov-report=xml

# ---------------------------------------------------------------- quality

lint: ## Run ruff lint checks
	$(PY) -m ruff check src tests

format: ## Format sources with ruff
	$(PY) -m ruff format src tests

check-format: ## Check formatting without changing files
	$(PY) -m ruff format --check src tests

# ---------------------------------------------------------------- cleanup

clean: ## Remove caches and coverage output (keeps the index and reports)
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache coverage.xml .coverage htmlcov

distclean: clean ## Also remove the virtualenv, the norm index and stored reports
	rm -rf .venv $(CHROMA) data/reports.db
