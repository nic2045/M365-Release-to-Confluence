.PHONY: help dev install lint format check test run dry-run products clean

PY ?= python3
CLI = $(PY) -m m365_confluence.cli
SOURCE ?= roadmap
LIMIT ?= 5

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

dev: install  ## Set up the dev environment (editable install with all extras)

install:  ## Install the package with all extras
	$(PY) -m pip install -e ".[all]"

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

clean:  ## Remove local state/changelog and caches
	rm -f m365_state.json m365_changelog.json
	rm -rf .pytest_cache .ruff_cache **/__pycache__
