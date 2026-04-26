.DEFAULT_GOAL := help

CHART_DIRS := $(sort $(dir $(wildcard ./charts/*/Chart.yaml)))
JOBS ?= $(shell nproc 2>/dev/null || echo 4)
PYTEST_ARGS ?= charts
MANIFEST_PYTEST_ARGS ?= charts/tests/test_manifest_contracts.py

.PHONY: help lint lint-helm dump deps-update validate test test-update build update-readme upgrade

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

lint: ## Lint and format the code
	@npx -y prettier --write .
	@$(MAKE) lint-helm
	@uv run ruff format .

lint-helm: ## Build vendored chart dependencies and run helm lint for every chart
	@printf '%s\n' $(CHART_DIRS) | xargs -P $(JOBS) -I {} sh -eu -c '\
		chart="{}"; \
		chart_name=$$(basename "$$chart"); \
		chart_type=$$(grep -E "^type:" "$$chart/Chart.yaml" | awk "{print \$$2}" || echo application); \
		if [ "$$chart_type" != "library" ] && grep -Eq "^dependencies:" "$$chart/Chart.yaml"; then \
			if [ ! -f "$$chart/Chart.lock" ]; then \
				echo "Missing $$chart/Chart.lock. Run make deps-update." >&2; \
				exit 1; \
			fi; \
			helm dependency build --skip-refresh "$$chart" >/dev/null; \
		fi; \
		printf "Linting %s\n" "$$chart_name"; \
		helm lint "$$chart" >/dev/null'

dump: ## Dump all chart templates to ./tmp
	@rm -rf ./tmp
	@mkdir -p ./tmp
	@printf '%s\n' $(CHART_DIRS) | xargs -P $(JOBS) -I {} sh -eu -c '\
		chart="{}"; \
		chart_name=$$(basename "$$chart"); \
		chart_type=$$(grep -E "^type:" "$$chart/Chart.yaml" | awk "{print \$$2}" || echo application); \
		if [ "$$chart_type" = "library" ]; then \
			echo "Skipping library chart: $$chart_name"; \
			exit 0; \
		fi; \
		echo "Dumping $$chart_name..."; \
		mkdir -p "./tmp/$$chart_name"; \
		if grep -Eq "^dependencies:" "$$chart/Chart.yaml"; then \
			if [ ! -f "$$chart/Chart.lock" ]; then \
				echo "Missing $$chart/Chart.lock. Run make deps-update." >&2; \
				exit 1; \
			fi; \
			helm dependency build --skip-refresh "$$chart"; \
		fi; \
		rendered_manifest=$$(mktemp); \
		helm template "$$chart" > "$$rendered_manifest"; \
		csplit -s -z -f "./tmp/$$chart_name/manifest-" "$$rendered_manifest" "/^---$$/" "{*}"; \
		rm -f "$$rendered_manifest"; \
		for file in "./tmp/$$chart_name"/manifest-*; do mv "$$file" "$$file.yaml" 2>/dev/null || true; done; \
		rm -f "./tmp/$$chart_name/manifest.yaml"'

deps-update: ## Refresh chart dependencies and lockfiles for charts that declare dependencies
	@printf '%s\n' $(CHART_DIRS) | xargs -P 1 -I {} sh -eu -c '\
		chart="{}"; \
		chart_name=$$(basename "$$chart"); \
		chart_type=$$(grep -E "^type:" "$$chart/Chart.yaml" | awk "{print \$$2}" || echo application); \
		if [ "$$chart_type" = "library" ]; then \
			exit 0; \
		fi; \
		if ! grep -Eq "^dependencies:" "$$chart/Chart.yaml"; then \
			exit 0; \
		fi; \
		echo "Updating dependencies for $$chart_name..."; \
		helm dependency update "$$chart"'

validate: ## Validate Python syntax and rendered chart manifests via pytest
	@echo "Checking Python syntax..."
	@find . -name "*.py" -not -path "./.venv/*" -not -path "./.*" -print0 | xargs -0 -n 50 -P $(JOBS) python3 -m py_compile
	@echo "Validating rendered manifests with pytest ($(MANIFEST_PYTEST_ARGS))"
	@uv run pytest $(MANIFEST_PYTEST_ARGS)

test: validate ## Run chart validation and pytest suite
	@echo "Running pytest ($(PYTEST_ARGS))"
	@uv run pytest $(PYTEST_ARGS)

test-update: ## Update snapshot tests, then re-run pytest to verify
	@echo "Updating pytest snapshots ($(PYTEST_ARGS))"
	@uv run pytest $(PYTEST_ARGS) --snapshot-update || true
	@echo "Re-running pytest after snapshot refresh ($(PYTEST_ARGS))"
	@uv run pytest $(PYTEST_ARGS)

update-readme: ## Update the README with the latest chart information
	@uv run tools/update_readme_charts.py docs/README.md
	@make lint

build: ## Build all charts
	@mkdir -p ./tmp
	@printf '%s\n' $(CHART_DIRS) | xargs -P $(JOBS) -I {} sh -eu -c '\
		chart="{}"; \
		chart_name=$$(basename "$$chart"); \
		chart_type=$$(grep -E "^type:" "$$chart/Chart.yaml" | awk "{print \$$2}" || echo application); \
		if [ "$$chart_type" = "library" ]; then \
			echo "Skipping library chart: $$chart_name"; \
			exit 0; \
		fi; \
		echo "Building $$chart_name..."; \
		if grep -Eq "^dependencies:" "$$chart/Chart.yaml"; then \
			if [ ! -f "$$chart/Chart.lock" ]; then \
				echo "Missing $$chart/Chart.lock. Run make deps-update." >&2; \
				exit 1; \
			fi; \
			helm dependency build --skip-refresh "$$chart"; \
		fi; \
		helm package "$$chart" -d ./tmp'
	@echo "Packaged charts available in ./tmp"

upgrade: ## Upgrade container image tags in all charts
	@uv run tools/upgrade.py $(CHART_DIRS)
