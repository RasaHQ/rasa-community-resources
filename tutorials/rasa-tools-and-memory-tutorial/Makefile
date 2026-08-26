# ==============================================================================
# Sterling — tool scope and memory scope in Rasa Mantle
# ==============================================================================
GREEN  := $(shell tput -Txterm setaf 2 2>/dev/null)
YELLOW := $(shell tput -Txterm setaf 3 2>/dev/null)
RED    := $(shell tput -Txterm setaf 1 2>/dev/null)
DIM    := $(shell tput -Txterm dim 2>/dev/null)
RESET  := $(shell tput -Txterm sgr0 2>/dev/null)

UV := $(shell command -v uv 2>/dev/null)

.DEFAULT_GOAL := help
.PHONY: help check-uv env guard-env install validate train chat run scopes clean

help: ## Show this help message
	@echo ''
	@echo '$(YELLOW)Sterling — tool scope and memory scope$(RESET)'
	@echo ''
	@echo '  $(GREEN)make env$(RESET)        Create .env from .env.example'
	@echo '  $(GREEN)make install$(RESET)    Install dependencies (uv sync --prerelease=allow)'
	@echo '  $(GREEN)make train$(RESET)      Validate and train the agent'
	@echo '  $(GREEN)make chat$(RESET)       Talk to the agent in the Inspector'
	@echo '  $(GREEN)make validate$(RESET)   Validate the project without training'
	@echo '  $(GREEN)make scopes$(RESET)     Print which tools and memory are local vs global'
	@echo '  $(GREEN)make clean$(RESET)      Remove models and caches'
	@echo ''
	@echo '$(DIM)  Walkthrough: sign me in, my passphrase is bluebird$(RESET)'
	@echo '$(DIM)              what is the balance on 10029384$(RESET)'
	@echo '$(DIM)              send 25 pounds to Sam Rivera$(RESET)'
	@echo ''

check-uv:
	@if [ -z "$(UV)" ]; then \
		echo "$(RED)✗ uv not found.$(RESET)  curl -LsSf https://astral.sh/uv/install.sh | sh"; \
		exit 1; \
	fi

env: ## Create .env from .env.example if it does not exist
	@if [ -f .env ]; then echo "$(YELLOW).env already exists — leaving it alone.$(RESET)"; \
	else cp .env.example .env; echo "$(GREEN)✓ .env created — add RASA_LICENSE and OPENAI_API_KEY.$(RESET)"; fi

guard-env:
	@if [ ! -f .env ]; then echo "$(RED)✗ No .env — run: make env$(RESET)"; exit 1; fi

install: check-uv ## Install dependencies
	@$(UV) sync --prerelease=allow

validate: check-uv guard-env ## Validate the project without training
	@$(UV) run rasa validate-project 2>/dev/null || $(UV) run python -c "\
from rasa.calm_v2.validation import validate_project; validate_project('.'); print('ok')"

train: check-uv guard-env ## Validate and train
	@$(UV) run rasa train

chat: check-uv guard-env ## Talk to the agent
	@$(UV) run rasa inspect

run: check-uv guard-env ## Start the API server
	@$(UV) run rasa run --enable-api

scopes: ## Print the tool and memory scopes in this project
	@echo ''
	@echo '$(YELLOW)GLOBAL tools$(RESET) $(DIM)(project root; named in a skill import_tools)$(RESET)'
	@for f in tools/*.py; do \
		case "$$f" in */__init__.py) continue;; esac; \
		grep -hoE '^async def [a-z_]+' $$f | sed 's/async def /  /'; \
	done
	@echo ''
	@echo '$(YELLOW)LOCAL tools$(RESET) $(DIM)(skill folder; auto-discovered)$(RESET)'
	@for f in skills/*/tools.py; do \
		s=$$(dirname $$f); \
		grep -hoE '^async def [a-z_]+' $$f | sed "s|async def |  $$(basename $$s)/|"; \
	done
	@echo ''
	@echo '$(YELLOW)PROJECT memory$(RESET) $(DIM)(every skill reads and writes)$(RESET)'
	@grep -oE '^[a-z_]+:' memory.yml | sed 's/:$$//;s/^/  /'
	@echo ''
	@echo '$(YELLOW)SKILL memory$(RESET) $(DIM)(public = other skills may read; private = never)$(RESET)'
	@for f in skills/*/memory.yml; do \
		echo "  $$(basename $$(dirname $$f)):"; \
		$(UV) run python -c "import sys,yaml;d=yaml.safe_load(open('$$f'))or{};s=d.get('schema',{});\
[print('    public : '+k) for k in (s.get('public') or {})];\
[print('    private: '+k) for k in (s.get('private') or {})]" 2>/dev/null; \
	done
	@echo ''

clean: ## Remove models and caches
	@rm -rf models .rasa
	@find . -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true
	@echo "$(GREEN)✓ cleaned$(RESET)"
