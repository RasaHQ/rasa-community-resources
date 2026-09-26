# ==============================================================================
# LangGraph's customer-support bot, rebuilt in Rasa Mantle
# ==============================================================================
GREEN  := $(shell tput -Txterm setaf 2 2>/dev/null)
YELLOW := $(shell tput -Txterm setaf 3 2>/dev/null)
RED    := $(shell tput -Txterm setaf 1 2>/dev/null)
DIM    := $(shell tput -Txterm dim 2>/dev/null)
RESET  := $(shell tput -Txterm sgr0 2>/dev/null)

UV     := $(shell command -v uv 2>/dev/null)
PYTHON ?= python3

.DEFAULT_GOAL := help
.PHONY: help check-uv env guard-env install db db-check train chat run scopes clean

help: ## Show this help message
	@echo ''
	@echo '$(YELLOW)Swiss Airlines assistant — LangGraph'"'"'s bot in Mantle$(RESET)'
	@echo ''
	@echo '  $(GREEN)make env$(RESET)        Create .env from .env.example'
	@echo '  $(GREEN)make install$(RESET)    Install dependencies (uv sync --prerelease=allow)'
	@echo '  $(GREEN)make db$(RESET)         Build travel.sqlite from the committed fixture'
	@echo '  $(GREEN)make db-check$(RESET)   Query the database directly, without the agent'
	@echo '  $(GREEN)make train$(RESET)      Validate and train the agent'
	@echo '  $(GREEN)make chat$(RESET)       Talk to the agent in the Inspector'
	@echo '  $(GREEN)make scopes$(RESET)     Print every tool and memory field with its scope'
	@echo '  $(GREEN)make clean$(RESET)      Remove models, caches and the built database'
	@echo ''
	@echo '$(DIM)  No 109 MB download: the fixture is 50 KB of SQL in data/.$(RESET)'
	@echo '$(DIM)  Walkthrough: what flights do I have booked?$(RESET)'
	@echo '$(DIM)               I need a hotel in Basel$(RESET)'
	@echo ''

check-uv:
	@if [ -z "$(UV)" ]; then \
		echo "$(RED)✗ uv not found.$(RESET)  curl -LsSf https://astral.sh/uv/install.sh | sh"; exit 1; \
	fi

env: ## Create .env from .env.example if it does not exist
	@if [ -f .env ]; then echo "$(YELLOW).env already exists — leaving it alone.$(RESET)"; \
	else cp .env.example .env; echo "$(GREEN)✓ .env created — add RASA_LICENSE and OPENAI_API_KEY.$(RESET)"; fi

guard-env:
	@if [ ! -f .env ]; then echo "$(RED)✗ No .env — run: make env$(RESET)"; exit 1; fi

install: check-uv ## Install dependencies
	@$(UV) sync --prerelease=allow

db: ## Build travel.sqlite from the committed fixture
	@$(PYTHON) scripts/build_db.py

db-check: ## Query the database directly, bypassing the agent
	@$(PYTHON) scripts/db_check.py

train: check-uv guard-env db ## Validate and train
	@$(UV) run rasa train

chat: check-uv guard-env ## Talk to the agent
	@$(UV) run rasa inspect

run: check-uv guard-env ## Start the API server
	@$(UV) run rasa run --enable-api

scopes: ## Print the tool and memory scopes in this project
	@echo ''
	@echo '$(YELLOW)GLOBAL tools$(RESET) $(DIM)(project root; named in a skill import_tools)$(RESET)'
	@for f in tools/*.py; do case "$$f" in */__init__.py) continue;; esac; \
	  grep -hoE '^async def [a-z_]+' $$f | sed 's/async def /  /'; done
	@echo ''
	@echo '$(YELLOW)LOCAL tools$(RESET) $(DIM)(skill folder; auto-discovered)$(RESET)'
	@for f in skills/*/tools.py; do [ -f "$$f" ] || continue; \
	  grep -hoE '^async def [a-z_]+' $$f | sed "s|async def |  $$(basename $$(dirname $$f))/|"; done
	@echo ''
	@echo '$(YELLOW)PROJECT memory$(RESET) $(DIM)(every skill reads and writes)$(RESET)'
	@grep -oE '^[a-z_]+:' memory.yml | sed 's/:$$//;s/^/  /'
	@echo ''

clean: ## Remove models, caches and the built database
	@rm -rf models .rasa travel.sqlite
	@find . -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true
	@echo "$(GREEN)✓ cleaned$(RESET)"
