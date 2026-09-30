##### CONFIG #####
SYSTEMS  ?= systems/core systems/api
TOOL     ?= management
ARGS      = $(filter-out $@,$(MAKECMDGOALS))

RESET   := \033[0m
BOLD    := \033[1m
GREEN   := \033[0;32m
CYAN    := \033[0;36m
GRAY    := \033[0;90m

SHELL := bash
.DEFAULT_GOAL := help
MAKEFLAGS += --no-print-directory

##### TARGETS #####
.PHONY: help install update drift manage check clean

help:
	@printf "$(BOLD)$(CYAN)e-templates$(RESET) $(GRAY)· systems of boilerplates + management tool$(RESET)\n\n"
	@awk 'BEGIN{FS=":.*##"} /^[a-z][a-zA-Z0-9_-]*:.*##/{printf "  $(GREEN)%-9s$(RESET) $(GRAY)%s$(RESET)\n",$$1,$$2}' $(MAKEFILE_LIST)

install: ## sync every project (systems + tool)
	@for p in $(SYSTEMS) $(TOOL); do uv sync --project $$p; done
	@printf "$(GREEN)✓ all projects synced$(RESET)\n"

update: ## re-materialize systems/api from its sources (core/ops + common)
	@$(MAKE) -C systems/api core common
	@$(MAKE) -C systems/api core-check common-check

drift: ## report materialized drift across the whole ecosystem
	@uv run --project $(TOOL) python -m e_management drift

manage: ## open the Textual boilerplate wizard
	@uv run --project $(TOOL) python -m e_management

check: ## run the fast gate of every project
	@for p in $(SYSTEMS) $(TOOL); do printf "$(BOLD)$(p)$(RESET)\n"; $(MAKE) -C $$p check || exit 1; done

clean: ## clean caches and artifacts everywhere
	@for p in $(SYSTEMS) $(TOOL); do $(MAKE) -C $$p clean; done
	@find . -type d \( -name __pycache__ -o -name .pytest_cache -o -name .ruff_cache \) -exec rm -rf {} + 2>/dev/null || true
	@printf "$(GREEN)✓ clean$(RESET)\n"

%:
	@:
