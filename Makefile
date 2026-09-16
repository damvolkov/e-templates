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
.PHONY: help install sync lock lint type arch test check run up down build logs clean

help:
	@printf "$(BOLD)$(CYAN)$(PROJECT)$(RESET) $(GRAY)· uv · ruff · ty · tach · pytest · docker$(RESET)\n\n"
	@awk 'BEGIN{FS=":.*##"} /^[a-z][a-zA-Z0-9_-]*:.*##/{printf "  $(GREEN)%-8s$(RESET) $(GRAY)%s$(RESET)\n",$$1,$$2}' $(MAKEFILE_LIST)

install: ## full setup: sync deps + git hooks
	@uv sync
	@uv run prek install
	@printf "$(GREEN)✓ ready$(RESET)\n"

sync: ## sync all deps (main + dev)
	@uv sync

lock: ## refresh uv lockfile
	@uv lock

lint: ## ruff check + format
	@uv run ruff check --fix $(PACKAGE) tests
	@uv run ruff format $(PACKAGE) tests

type: ## ty type check
	@uv run ty check

arch: ## enforce import architecture (tach)
	@uv run tach check

test: ## run tests [make test TESTARGS=...]
	@uv run pytest tests $(TESTARGS) -n auto -q

benchmark: ## run benchmarks only
	@uv run pytest tests -m benchmark --benchmark-only -q

check: lint type arch test ## lint + type + arch + test

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

%:
	@:
