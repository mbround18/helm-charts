.DEFAULT_GOAL := help

CHART_DIRS := $(sort $(dir $(wildcard ./charts/*/Chart.yaml)))

.PHONY: help lint dump test build update-readme upgrade

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

lint: ## Lint and format the code
	@npx -y prettier --write .
	@set -e; for chart in $(CHART_DIRS); do helm lint $$chart; done
	@uv run ruff format .

dump: ## Dump all chart templates to ./tmp
	@rm -rf ./tmp
	@mkdir -p ./tmp
	@set -e; for chart in $(CHART_DIRS); do \
		chart_name=$$(basename $$chart); \
		chart_type=$$(grep -E '^type:' $$chart/Chart.yaml | awk '{print $$2}' || echo 'application'); \
		if [ "$$chart_type" = "library" ]; then \
			echo "Skipping library chart: $$chart_name"; \
			continue; \
		fi; \
		mkdir -p ./tmp/$$chart_name; \
		helm dependency update $$chart; \
		rendered_manifest=$$(mktemp); \
		helm template $$chart > $$rendered_manifest; \
		csplit -s -z -f ./tmp/$$chart_name/manifest- $$rendered_manifest '/^---$$/' '{*}'; \
		rm -f $$rendered_manifest; \
		for file in ./tmp/$$chart_name/manifest-*; do mv $$file $$file.yaml 2>/dev/null || true; done; \
		rm -f ./tmp/$$chart_name/manifest.yaml; \
	done

test: dump ## Test the charts
	@echo "Checking Python syntax..."
	@find . -name "*.py" -not -path "./.venv/*" -not -path "./.*" | xargs -I {} python3 -m py_compile {}
	@echo "Validating templated YAML with Python (uv)"
	@uv run tools/validate_yaml.py ./tmp

update-readme: ## Update the README with the latest chart information
	@uv run tools/update_readme_charts.py docs/README.md
	@make lint

build: ## Build all charts
	@mkdir -p ./tmp
	@set -e; for chart in $(CHART_DIRS); do \
		chart_name=$$(basename $$chart); \
		chart_type=$$(grep -E '^type:' $$chart/Chart.yaml | awk '{print $$2}' || echo 'application'); \
		if [ "$$chart_type" = "library" ]; then \
			echo "Skipping library chart: $$chart_name"; \
			continue; \
		fi; \
		echo "Building $$chart_name..."; \
		helm dependency update $$chart; \
		helm package $$chart -d ./tmp; \
	done
	@echo "Packaged charts available in ./tmp"

upgrade: ## Upgrade container image tags in all charts
	@uv run tools/upgrade.py $(CHART_DIRS)
