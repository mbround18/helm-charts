.DEFAULT_GOAL := help

CHART_DIRS := $(sort $(dir $(wildcard ./charts/*/Chart.yaml)))
JOBS ?= $(shell nproc 2>/dev/null || echo 4)
PYTEST_ARGS ?= charts
MANIFEST_PYTEST_ARGS ?= charts/tests/test_manifest_contracts.py
CHART_TASKS := uv run python -m tools.chart_tasks --jobs $(JOBS)

.PHONY: help lint lint-helm dump deps-update validate test build update-readme upgrade refresh prune-branches ci

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

lint: ## Lint and format the code
	@npx -y prettier --write .
	@$(CHART_TASKS) lint
	@uv run ruff format .

lint-helm:
	@$(CHART_TASKS) lint

dump: ## Dump all chart templates to ./tmp
	@$(CHART_TASKS) dump --output-dir ./tmp

deps-update:
	@find ./charts -maxdepth 2 -name "Chart.yaml" -execdir mkdir -p charts \;
	@$(CHART_TASKS) deps-update

validate: ## Validate Python syntax and rendered chart manifests via pytest
	@$(CHART_TASKS) validate --repo-root . --manifest-pytest-args $(MANIFEST_PYTEST_ARGS)

test: validate ## Run chart validation and pytest suite
	@echo "Running pytest ($(PYTEST_ARGS))"
	@uv run pytest $(PYTEST_ARGS)

update-readme:
	@uv run tools/update_readme_charts.py docs/README.md
	@$(MAKE) lint

build: deps-update ## Build all charts
	@$(CHART_TASKS) build --output-dir ./tmp

upgrade: ## Upgrade container image tags in all charts
	@uv run tools/upgrade.py $(CHART_DIRS)

refresh: ## Refresh dependency locks, image tags, and generated README content
	@$(MAKE) deps-update
	@$(MAKE) upgrade
	@$(MAKE) update-readme

prune-branches: ## Delete all local branches except main. Set REMOTE=1 to also delete from origin
	@git checkout main 2>/dev/null || true
	@echo "Pruning merged remote-tracking refs..."
	@git fetch --prune
	@local_branches=$$(git branch | grep -v '^\*\? *main$$' | sed 's/^[ *]*//' | tr '\n' ' '); \
	if [ -z "$$(echo $$local_branches | tr -d ' ')" ]; then \
		echo "Nothing to prune."; \
		exit 0; \
	fi; \
	echo "Deleting local branches: $$local_branches"; \
	echo $$local_branches | xargs git branch -D; \
	if [ "$${REMOTE:-0}" = "1" ]; then \
		remote_branches=$$(git branch -r | grep 'origin/' | grep -v 'origin/HEAD' | grep -v 'origin/main$$' | grep -v 'origin/gh-pages$$' | sed 's|origin/||' | sed 's/^[ ]*//' | tr '\n' ' '); \
		if [ -n "$$(echo $$remote_branches | tr -d ' ')" ]; then \
			echo "Deleting remote branches: $$remote_branches"; \
			echo $$remote_branches | xargs -I{} git push origin --delete {}; \
		else \
			echo "No remote branches to delete."; \
		fi; \
	fi


ci: ## Run all CI checks and build charts. This is the default target.
	@$(MAKE) refresh
	@$(MAKE) build
	@$(MAKE) test