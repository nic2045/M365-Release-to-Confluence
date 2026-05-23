.PHONY: help dev install lint format check test run dry-run products review publish-review ui clean

PY ?= python3
CLI = $(PY) -m m365_confluence.cli
UI = $(PY) -m m365_confluence.ui.app
SOURCE ?= roadmap
LIMIT ?= 5

# Use uv if available (faster), otherwise fall back to pip.
UV := $(shell command -v uv 2>/dev/null)
INSTALL := $(if $(UV),uv pip install,$(PY) -m pip install)

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

dev:  ## Install dev + all extras (uses uv if installed)
	$(INSTALL) -e ".[dev]"

install:  ## Install runtime with all extras (uses uv if installed)
	$(INSTALL) -e ".[all]"

lint:  ## Run ruff lint
	ruff check .

format:  ## Auto-format with ruff
	ruff format .

check:  ## Lint + format check + tests (what CI runs)
	ruff check .
	ruff format --check .
	$(PY) -m pytest -q

test:  ## Run the test suite
	$(PY) -m pytest -q

dry-run:  ## Preview without writing to Confluence (SOURCE=, LIMIT= overridable)
	$(CLI) --source $(SOURCE) --limit $(LIMIT) --dry-run -v

products:  ## List the products found in the source(s)
	$(CLI) --source $(SOURCE) --list-products

run:  ## Real run: publish to Confluence (SOURCE= overridable)
	$(CLI) --source $(SOURCE)

review:  ## Produce editable drafts (review.json) without publishing
	$(CLI) --source $(SOURCE) --review-out review.json -v

publish-review:  ## Publish edited drafts from review.json to Confluence
	$(CLI) --from-review review.json

ui:  ## Launch the review/edit web UI (http://127.0.0.1:8765)
	$(UI) --review-file review.json

clean:  ## Remove local state/changelog and caches
	rm -f m365_state.json m365_changelog.json
	rm -rf .pytest_cache .ruff_cache **/__pycache__
