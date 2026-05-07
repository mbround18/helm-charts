# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

A multi-chart Helm repository hosting 15+ application charts for Kubernetes deployment. Charts are published to GitHub Pages at `https://mbround18.github.io/helm-charts`. The toolchain is Python-based (managed with `uv`) and runs via `make`.

**Workflow chain**: `make lint` → edit charts → `make dump` → `make test` → `make build`

## Common Commands

```bash
make lint          # Prettier formatting + helm lint + ruff format (fixes in-place)
make dump          # Template all charts → tmp/{chart}/manifest-*.yaml
make validate      # Python syntax check + manifest contract pytest suite
make test          # validate + full pytest suite (runs make validate first)
make build         # Package charts → tmp/{chart}-{version}.tgz
make deps-update   # Refresh Chart.lock files (only when changing dependency versions)
make refresh       # deps-update + upgrade image tags + update README
```

Run a single chart's tests:
```bash
uv run pytest charts/forgejo/tests/ -v
```

Run a single test file:
```bash
uv run pytest charts/tests/test_manifest_contracts.py -v
```

Render a chart for debugging without the full pipeline:
```bash
helm template release-name charts/forgejo
```

## Architecture

### Chart Layout

Each chart under `charts/{name}/` follows standard Helm structure with `Chart.yaml`, `values.yaml`, `templates/`, and `tests/`. Library charts (`type: library` in `Chart.yaml`) are skipped by `make dump` and `make build`—this is intentional.

### Testing

- `conftest.py` (root): Builds Helm dependencies asynchronously before the test session starts using `helm dependency build --skip-refresh`.
- `charts/test_helpers.py`: Shared fixtures for rendering charts (`render_chart_documents`) and iterating workloads.
- `charts/tests/test_manifest_contracts.py`: Contract-style assertions on rendered manifests. Prefer contract assertions over snapshot-style golden files.
- Tests run in parallel via `pytest-xdist` (`-n=auto`).

### Helm Dependencies

Charts with subcharts commit `Chart.lock`. Normal `make dump/test/build` use lockfile-driven `helm dependency build --skip-refresh`. Run `make deps-update` only when intentionally changing dependency versions. If a local `file://` library dependency changes, run `make deps-update` so consuming charts vendor the update before testing.

### Python Tooling (`tools/`)

| Script | Purpose |
|---|---|
| `chart_tasks.py` | CLI driver for `make` targets (lint, dump, build, validate, deps-update) |
| `upgrade.py` | Bumps container image tags across all charts |
| `manager.py` | Version management and release automation |
| `update_readme_charts.py` | Regenerates docs/README.md chart table |
| `validate_yaml.py` | YAML syntax validation |
| `version_checker.py` | Detects upstream version updates |

## GitOps Sync-Wave Model

Every resource must be assigned to one of five Argo CD sync-wave phases. Do not invent custom wave numbers.

| Phase | Wave | Resources |
|---|---|---|
| `foundation` | `0` | Secrets, PVCs, ServiceAccounts, bootstrap ConfigMaps |
| `database` | `10` | StatefulSets for databases and data stores |
| `supporting` | `20` | Jobs that run after a dependency is up (e.g. password sync) |
| `release` | `30` | Primary application Deployment or StatefulSet |
| `ingress` | `40` | Services, Ingresses, VirtualServices |

Charts that depend on `gitops-tools` should use the helper instead of hard-coding numbers:

```yaml
{{- include "gitops-tools.argocd.annotations" (dict "context" . "phase" "release") }}
```

Charts without `gitops-tools` must still use the same numeric values. See `docs/argocd-gitops.md` for full policy.

## Conventions

**Conditional components**: Add `{component}.enabled` boolean to `values.yaml`, wrap templates with `{{- if .Values.{component}.enabled }}`, and name derived services `{fullname}-{component}`.

**Security contexts**: All container specs must include `podSecurityContext` and `securityContext` with `runAsNonRoot: true`, `allowPrivilegeEscalation: false`, and `capabilities.drop: [ALL]`.

**StatefulSets vs Deployments**: Multi-replica or data-layer services use StatefulSets (preserves pod naming like `postgres-0`). Stateless apps use Deployments.

**Secret management**: Sensitive values go in `values.secret.yml` (git-ignored). Never commit secrets.

**Whitespace in templates**: Use `{{- }}` to strip leading whitespace. Misalignment breaks YAML parsing.
