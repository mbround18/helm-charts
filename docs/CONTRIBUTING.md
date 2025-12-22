## Contributing

Thank you for wanting to contribute! See the repository `README.md` for general contribution workflow and guidelines. This file contains project-specific developer notes.

### Centralized Makefile for Charts

We maintain a centralized Makefile helper at `config/Makefile` to avoid duplicating the same Makefile across charts. When creating a new chart, add a tiny wrapper `Makefile` in the chart root that sets per-chart variables and includes the centralized file.

Example `charts/<chart>/Makefile` wrapper:

```makefile
# Chart-specific overrides
CHART_DIR := $(CURDIR)
RELEASE_NAME ?= your-chart-name
BUILD_DIR ?= tmp

# include centralized targets from repo root
include $(abspath $(CURDIR)/../..)/config/Makefile
```

Notes:

- The centralized `config/Makefile` exposes targets: `setup`, `build`, `deploy`, `test`, and `dump`.
- From a chart directory you can run `make test`, `make dump`, `make build`, etc., and they will use the centralized behavior.
- The included Makefile detects its own path with `$(lastword $(MAKEFILE_LIST))` so it works reliably when included from subdirectories.

If you want me to automatically convert existing chart Makefiles to this wrapper pattern, say which charts to update and I'll apply the changes.
