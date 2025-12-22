## Centralized chart Makefile helpers
# Usage: from a chart directory Makefile set optional overrides then include this file
# Example (in charts/audiobookshelf/Makefile):
#   CHART_DIR := $(CURDIR)
#   RELEASE_NAME ?= audiobookshelf
#   include $(abspath $(CURDIR)/../..)/config/Makefile

MAKEFILE_PATH := $(abspath $(lastword $(MAKEFILE_LIST)))
MAKEFILE_DIR  := $(patsubst %/,%,$(dir $(MAKEFILE_PATH)))
ROOT_DIR := $(abspath $(MAKEFILE_DIR)/..)
SCRIPT_DIR := $(abspath $(ROOT_DIR)/tools)

.PHONY: deploy build setup test dump

# sensible defaults — child Makefile may override before including
CHART_DIR ?= $(CURDIR)
RELEASE_NAME ?= $(notdir $(CHART_DIR))
BUILD_DIR ?= tmp

# determine namespace from kubectl or default to release name
KUBE_NS := $(shell kubectl config view --minify --output 'jsonpath={..namespace}' 2>/dev/null)
NAMESPACE ?= $(or $(KUBE_NS),$(RELEASE_NAME))

setup:
	@echo "Updating dependencies in $(CHART_DIR)..."
	@cd $(CHART_DIR) && helm dependency update .

build: setup
	@echo "Packaging chart..."
	@cd $(CHART_DIR) && rm -rf $(BUILD_DIR) && mkdir -p $(BUILD_DIR)
	@cd $(CHART_DIR) && helm package . -d $(BUILD_DIR)
	@echo "Packaged chart available in $(CHART_DIR)/$(BUILD_DIR)"

deploy: build
	@echo "Deploying $(RELEASE_NAME) to namespace: $(NAMESPACE)"
	@cd $(CHART_DIR) && helm upgrade --install $(RELEASE_NAME) $(BUILD_DIR)/*.tgz --namespace $(NAMESPACE) --create-namespace
	@echo "$(RELEASE_NAME) deployed successfully."

test: setup
	@echo "Testing chart templates..."
	@cd $(CHART_DIR) && \
	VALUES_FILES=$$(find . -maxdepth 1 -name 'values.*.yaml' -type f | sort); \
	if [ -z "$$VALUES_FILES" ]; then \
		echo "No values.*.yaml files found, testing with default values.yaml"; \
		helm template $(RELEASE_NAME) . --debug > /dev/null && echo "✓ Default values.yaml: OK"; \
	else \
		for values_file in $$VALUES_FILES; do \
			echo "Testing with $$values_file..."; \
			helm template $(RELEASE_NAME) . -f $$values_file --debug > /dev/null && echo "✓ $$values_file: OK" || (echo "✗ $$values_file: FAILED" && exit 1); \
		done; \
	fi; \
	echo "All template tests passed!"

dump: setup
	@echo "Dumping rendered manifests to $(CHART_DIR)/tmp/manifests..."
	@cd $(CHART_DIR) && rm -rf tmp/manifests && mkdir -p tmp/manifests
	@cd $(CHART_DIR) && helm template $(RELEASE_NAME) . --debug | uv run $(SCRIPT_DIR)/split_manifests.py - tmp/manifests
	@cd $(CHART_DIR) && echo "Wrote $$(ls tmp/manifests | wc -l) manifest files to tmp/manifests"
