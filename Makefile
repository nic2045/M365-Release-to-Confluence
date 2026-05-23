.PHONY: help dev install lint format check test run dry-run products pick review publish-review ui timeline clean

PY ?= python3
CLI = $(PY) -m m365_confluence.cli
UI = $(PY) -m m365_confluence.ui.app
SOURCE ?= roadmap
LIMIT ?= 5
FORCE ?=
FORCE_FLAG := $(if $(FORCE),--force,)
AXIS ?= quarter
# Pass any extra CLI flags through, e.g. ARGS="--product Teams --quarter 'Q3 2026' --major-only"
ARGS ?=

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

dry-run:  ## Preview, no Confluence write (SOURCE=, LIMIT=, ARGS="--product Teams ...")
	$(CLI) --source $(SOURCE) --limit $(LIMIT) --dry-run -v $(ARGS)

products:  ## List products in the source(s) (SOURCE= overridable)
	$(CLI) --source $(SOURCE) --list-products

pick:  ## Interactively pick products, then process (SOURCE=, LIMIT=, ARGS= overridable)
	$(CLI) --source $(SOURCE) --limit $(LIMIT) --pick-products $(ARGS)

run:  ## Real run: publish to Confluence (SOURCE=, ARGS= for filters)
	$(CLI) --source $(SOURCE) $(ARGS)

review:  ## Editable drafts (review.json), no publish (LIMIT=, FORCE=1, ARGS= for filters)
	$(CLI) --source $(SOURCE) --limit $(LIMIT) $(FORCE_FLAG) --review-out review.json -v $(ARGS)

publish-review:  ## Publish edited drafts from review.json to Confluence
	$(CLI) --from-review review.json

ui:  ## Launch the review/edit web UI (http://127.0.0.1:8765)
	$(UI) --review-file review.json

timeline:  ## Generate roadmap.drawio from state (AXIS=quarter|month, ARGS="--publish")
	$(PY) -m m365_confluence.timeline_cli --axis $(AXIS) $(ARGS)

clean:  ## Remove local state/changelog and caches
	rm -f m365_state.json m365_changelog.json
	rm -rf .pytest_cache .ruff_cache **/__pycache__
