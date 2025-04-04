.PHONY: lint dump

lint:
	@npx -y prettier --write .
	@for chart in $(shell ls -d ./charts/*/); do helm lint $$chart; done

dump:
	@rm -rf ./tmp
	@mkdir -p ./tmp
	@for chart in $(shell ls -d ./charts/*/); do \
		chart_name=$$(basename $$chart); \
		mkdir -p ./tmp/$$chart_name; \
		helm template $$chart | csplit -z -f ./tmp/$$chart_name/manifest- - '/^---$$/' '{*}'; \
		for file in ./tmp/$$chart_name/manifest-*; do mv $$file $$file.yaml; done; \
		rm -f ./tmp/$$chart_name/manifest.yaml; \
	done
