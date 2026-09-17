##### CONFIG #####
PROJECT ?= e-api
PACKAGE ?= src/e_api
MODULE  ?= e_api
PORT    ?= 8000
COMPOSE ?= compose.yml
ARGS     = $(filter-out $@,$(MAKECMDGOALS))

RESET   := \033[0m
BOLD    := \033[1m
GREEN   := \033[0;32m
CYAN    := \033[0;36m
GRAY    := \033[0;90m

SHELL := bash
.DEFAULT_GOAL := help
MAKEFLAGS += --no-print-directory
export PYTHONPATH := $(CURDIR)/src

##### TARGETS #####
.PHONY: help install sync lock lint type arch validate harden test cov benchmark docs docs-build check ci run up down build logs clean hooks init

help:
	@printf "$(BOLD)$(CYAN)$(PROJECT)$(RESET) $(GRAY)· uv · ruff · ty · tach · pytest · properdocs · docker$(RESET)\n\n"
	@awk 'BEGIN{FS=":.*##"} /^[a-z][a-zA-Z0-9_-]*:.*##/{printf "  $(GREEN)%-8s$(RESET) $(GRAY)%s$(RESET)\n",$$1,$$2}' $(MAKEFILE_LIST)

# — env —
install: ## full setup: sync deps + git hooks
	@uv sync
	@uv run prek install
	@printf "$(GREEN)✓ ready$(RESET)\n"

sync: ## sync all deps (main + dev)
	@uv sync

lock: ## refresh uv lockfile
	@uv lock

# — gates —
lint: ## ruff check + format
	@uv run ruff check --fix $(PACKAGE) tests
	@uv run ruff format $(PACKAGE) tests

type: ## ty type check
	@uv run ty check

arch: ## enforce import architecture (tach)
	@uv run tach check

validate: ## validate pyproject.toml against schema
	@uv run validate-pyproject pyproject.toml

harden: ## zizmor audit of GitHub Actions workflows
	@uv run zizmor --persona=regular .github/workflows

hooks: ## run all pre-commit hooks on every file (ruff, ty, tach, zizmor, gitleaks)
	@uv run prek run --all-files

# — tests —
test: ## run tests [args: forwarded]
	@uv run pytest tests $(TESTARGS) -n auto -q

cov: ## run tests with coverage gate (fail under 90%)
	@uv run pytest tests --cov --cov-report=term-missing

benchmark: ## run benchmarks only
	@uv run pytest tests -m benchmark --benchmark-only -q

# — docs —
docs: ## serve docs site live at :8000
	@uv run properdocs serve

docs-build: ## strict docs build to site/
	@uv run properdocs build --strict

# — aggregate —
check: lint type arch validate test ## fast local gate: lint + type + arch + validate + test
ci: lint type arch validate harden docs-build cov ## full pipeline: every gate CI runs, in one command

# — run —
run: ## run app locally [args: forwarded]
	@uv run python -m $(MODULE) $(ARGS)

up: ## docker compose up [args: services]
	@docker compose -f $(COMPOSE) up -d $(ARGS)
	@printf "$(GREEN)✓ up$(RESET) $(GRAY)http://localhost:$(PORT)$(RESET)\n"

down: ## docker compose down
	@docker compose -f $(COMPOSE) down

build: ## docker image build [args: services]
	@docker compose -f $(COMPOSE) build $(ARGS)

logs: ## tail docker logs [args: service]
	@docker compose -f $(COMPOSE) logs -f $(ARGS)

clean: ## remove caches + build artifacts
	@find . -type d \( -name __pycache__ -o -name .pytest_cache -o -name .ruff_cache \) -exec rm -rf {} + 2>/dev/null || true
	@rm -rf dist build *.egg-info .coverage .coverage.* htmlcov .ty_cache .benchmarks
	@printf "$(GREEN)✓ clean$(RESET)\n"

##### SCRIPTS #####
init: ## scaffold: rename template to a new project [args: name]
	@python3 scripts/init.py $(ARGS)

%:
	@:
