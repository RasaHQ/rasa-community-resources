# ==============================================================================
# Ora — a Rasa Mantle agent on HubSpot CRM
# ==============================================================================
GREEN  := $(shell tput -Txterm setaf 2 2>/dev/null)
YELLOW := $(shell tput -Txterm setaf 3 2>/dev/null)
RED    := $(shell tput -Txterm setaf 1 2>/dev/null)
DIM    := $(shell tput -Txterm dim 2>/dev/null)
RESET  := $(shell tput -Txterm sgr0 2>/dev/null)

UV     := $(shell command -v uv 2>/dev/null)
PYTHON ?= python3

.DEFAULT_GOAL := help
.PHONY: help check-uv env guard-env install mock train chat run crm-check clean \
        mcp-server mcp-prove mcp-swap mcp-restore mcp-status

help: ## Show this help message
	@echo ''
	@echo '$(YELLOW)Ora — a Mantle agent on HubSpot CRM$(RESET)'
	@echo ''
	@echo '  $(GREEN)make env$(RESET)        Create .env from .env.example'
	@echo '  $(GREEN)make install$(RESET)    Install dependencies (uv sync --prerelease=allow)'
	@echo '  $(GREEN)make mock$(RESET)       Run the mock CRM on :8787 (second terminal)'
	@echo '  $(GREEN)make train$(RESET)      Validate and train the agent'
	@echo '  $(GREEN)make chat$(RESET)       Talk to the agent in the Inspector'
	@echo '  $(GREEN)make crm-check$(RESET)  Call the CRM directly and print what comes back'
	@echo '  $(GREEN)make clean$(RESET)      Remove models and caches'
	@echo ''
	@echo '$(YELLOW)The MCP chapter — same skills, different transport$(RESET)'
	@echo ''
	@echo '  $(GREEN)make mcp-prove$(RESET)   Prove the swap. No licence, no key, no account.'
	@echo '  $(GREEN)make mcp-swap$(RESET)    Move the project onto MCP (REST files kept as .rest)'
	@echo '  $(GREEN)make mcp-restore$(RESET) Move it back to REST'
	@echo '  $(GREEN)make mcp-status$(RESET)  Say which transport is live right now'
	@echo '  $(GREEN)make mcp-server$(RESET)  Run the MCP CRM server on :8931 (second terminal)'
	@echo ''
	@echo '$(DIM)  No HubSpot account needed: leave HUBSPOT_BASE_URL pointing at the$(RESET)'
	@echo '$(DIM)  mock and run "make mock" alongside "make chat".$(RESET)'
	@echo ''
	@echo '$(DIM)  Walkthrough: hi, it'"'"'s dana.okafor@example.com$(RESET)'
	@echo '$(DIM)               what tickets do I have open?$(RESET)'
	@echo '$(DIM)               log that I called about the VAT rate$(RESET)'
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

mock: ## Run the mock HubSpot CRM (no account needed)
	@$(PYTHON) scripts/mock_hubspot.py

train: check-uv guard-env ## Validate and train
	@$(UV) run rasa train

chat: check-uv guard-env ## Talk to the agent
	@$(UV) run rasa inspect

run: check-uv guard-env ## Start the API server
	@$(UV) run rasa run --enable-api

EMAIL ?=
crm-check: check-uv guard-env ## Check the token and report what it can do
	@EMAIL="$(EMAIL)" $(UV) run python scripts/crm_check.py

clean: ## Remove models and caches
	@rm -rf models .rasa
	@find . -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true
	@echo "$(GREEN)✓ cleaned$(RESET)"

# ==============================================================================
# The MCP chapter
# ==============================================================================
# `mcp-swap` is reversible on purpose. The REST project stays on disk as the
# baseline the swap is measured against — deleting it would destroy the lesson.

mcp-server: ## Run the MCP CRM server (second terminal, needs make mock too)
	@$(PYTHON) scripts/mcp_crm_server.py

mcp-prove: check-uv ## Prove the transport swap — no licence, no key, no account
	@$(UV) run python scripts/prove_mcp_swap.py

mcp-status: ## Report which transport the project is configured for
	@if grep -q '^mcp_servers:' integrations.yml 2>/dev/null; then \
		echo "$(GREEN)MCP$(RESET)  — integrations.yml declares mcp_servers:"; \
		grep -h 'mcp/' skills/*/skill.md | sed 's/^/  /'; \
	else \
		echo "$(YELLOW)REST$(RESET) — tools/crm.py and skills/*/tools.py"; \
	fi

mcp-swap: ## Point the three skills at the MCP server (reversible)
	@if [ -f integrations.yml.rest ]; then \
		echo "$(YELLOW)Already swapped — run: make mcp-restore$(RESET)"; exit 1; fi
	@cp integrations.yml integrations.yml.rest
	@cp mcp_variant/integrations.yml integrations.yml
	@for skill in check_tickets identify_customer log_interaction; do \
		cp skills/$$skill/skill.md skills/$$skill/skill.md.rest; \
		cp mcp_variant/skills/$$skill/skill.md skills/$$skill/skill.md; \
	done
	@for skill in check_tickets log_interaction; do \
		mv skills/$$skill/tools.py skills/$$skill/tools.py.rest; \
	done
	@mv tools/crm.py tools/crm.py.rest
	@echo "$(GREEN)✓ swapped to MCP.$(RESET)  Start: make mock, make mcp-server, then make train"
	@echo "$(DIM)  The REST files are still here as .rest — make mcp-restore puts them back.$(RESET)"

mcp-restore: ## Put the REST transport back
	@if [ ! -f integrations.yml.rest ]; then \
		echo "$(YELLOW)Not swapped — nothing to restore.$(RESET)"; exit 0; fi
	@mv integrations.yml.rest integrations.yml
	@for skill in check_tickets identify_customer log_interaction; do \
		mv skills/$$skill/skill.md.rest skills/$$skill/skill.md; \
	done
	@for skill in check_tickets log_interaction; do \
		mv skills/$$skill/tools.py.rest skills/$$skill/tools.py; \
	done
	@mv tools/crm.py.rest tools/crm.py
	@echo "$(GREEN)✓ restored to REST.$(RESET)"
