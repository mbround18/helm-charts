.DEFAULT_GOAL := help

.PHONY: help lint dump test build update-readme upgrade

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

lint: ## Lint and format the code
	@npx -y prettier --write .
	@for chart in $(shell ls -d ./charts/*/); do helm lint $$chart; done
	@uv run ruff format .

dump: ## Dump all chart templates to ./tmp
	@rm -rf ./tmp
	@mkdir -p ./tmp
	@for chart in $(shell ls -d ./charts/*/); do \
		chart_name=$$(basename $$chart); \
		chart_type=$$(grep -E '^type:' $$chart/Chart.yaml | awk '{print $$2}' || echo 'application'); \
		if [ "$$chart_type" = "library" ]; then \
			echo "Skipping library chart: $$chart_name"; \
			continue; \
		fi; \
		mkdir -p ./tmp/$$chart_name; \
		helm dependency update $$chart; \
		helm template $$chart | csplit -s -z -f ./tmp/$$chart_name/manifest- - '/^---$$/' '{*}'; \
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
	@for chart in $(shell ls -d ./charts/*/); do \
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
	@for chart in $(shell ls -d ./charts/*/); do \
		echo "Upgrading chart: $$chart"; \
		uv run tools/upgrade.py $$chart; \
	done
