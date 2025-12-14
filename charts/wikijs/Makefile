.PHONY: deploy build setup test

# Configuration
RELEASE_NAME ?= wikijs
BUILD_DIR ?= tmp

# Determine the directory of this Makefile
DIR := $(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))

# Determine namespace:
# 1. NAMESPACE env var
# 2. Current kubernetes context namespace
# 3. Default to 'wikijs'
KUBE_NS := $(shell kubectl config view --minify --output 'jsonpath={..namespace}' 2>/dev/null)
NAMESPACE ?= $(or $(KUBE_NS),wikijs)

setup:
	@echo "Updating dependencies in $(DIR)..."
	@cd $(DIR) && helm dependency update .

build: setup
	@echo "Packaging chart..."
	@cd $(DIR) && rm -rf $(BUILD_DIR) && mkdir -p $(BUILD_DIR)
	@cd $(DIR) && helm package . -d $(BUILD_DIR)
	@echo "Packaged chart available in $(DIR)/$(BUILD_DIR)"

deploy: build
	@echo "Deploying $(RELEASE_NAME) to namespace: $(NAMESPACE)"
	@cd $(DIR) && helm upgrade --install $(RELEASE_NAME) $(BUILD_DIR)/*.tgz --namespace $(NAMESPACE) --create-namespace
	@echo "$(RELEASE_NAME) deployed successfully."

test: setup
	@echo "Testing chart templates..."
	@cd $(DIR) && \
	VALUES_FILES=$$(find . -maxdepth 1 -name 'values.*.yaml' -type f | sort); \
	if [ -z "$$VALUES_FILES" ]; then \
		echo "No values.*.yaml files found, testing with default values.yaml"; \
		helm template $(RELEASE_NAME) . --debug > /dev/null && echo "✓ Default values.yaml: OK"; \
	else \
		for values_file in $$VALUES_FILES; do \
			echo "Testing with $$values_file..."; \
			helm template $(RELEASE_NAME) . -f $$values_file --debug > /dev/null && echo "✓ $$values_file: OK" || (echo "✗ $$values_file: FAILED" && exit 1); \
		done; \
	fi
	@echo "All template tests passed!"