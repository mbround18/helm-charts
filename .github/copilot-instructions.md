# Copilot Instructions for Helm Charts Repository

## Repository Overview

This is a multi-chart Helm repository hosting **12+ application charts** for Kubernetes deployment. The repo publishes charts to GitHub Pages and includes game servers (Palworld, Valheim, Enshrouded), infrastructure tools (Meilisearch, PostgreSQL, Istio Ingress), and custom applications (Vein, Wiki.js).

**Key workflow**: Charts are templated → dumped to YAML manifests → validated → packaged for distribution.

## Architecture Patterns

### Chart Structure

Each chart follows the standard Helm layout:

```
charts/{chart-name}/
  Chart.yaml           # Metadata (version, appVersion, type)
  values.yaml          # Default values
  values.secret.yml    # (optional) Secret values for CI/CD
  templates/           # Kubernetes manifests
    _helpers.tpl       # Reusable template functions
    deployment.yaml    # Pod/Workload definitions
    service.yaml       # Service exposure
    ingress.yaml       # (optional) Ingress routing
```

**Important**: `Chart.yaml` contains `type: application` (default) or `type: library` for dependency charts. Library charts are **skipped during build/dump** (see Makefile lines 20, 42).

### Multi-Pattern Ingress: Kubernetes Ingress vs. Istio

The **Meilisearch chart** exemplifies sophisticated pattern handling two ingress systems:

- **Kubernetes Ingress** (nginx/traefik): Routes via path prefixes (`/`, `/manage`)
- **Istio VirtualService**: Routes via HTTP route rules matching logic

**Pattern mechanism** (see meilisearch \_helpers.tpl template):

- `meilisearch.istioHttpRoutes`: Generates Istio routes dynamically
- `meilisearch.ingressPaths`: Generates K8s Ingress paths dynamically
- Both **conditionally include UI routes** if `ui.enabled: true`

**Takeaway for modifications**: Don't duplicate route definitions—use helpers to generate both formats from single values.

### Conditional Component Deployment

Many charts include optional sidecar containers or services:

- **Meilisearch UI sidecar**: `ui.enabled` controls whether sidecar pod is deployed + creates separate UI service
- **Palworld backups**: `backups.enabled` adds backup-cron container
- **Postgres init scripts**: Managed via ConfigMap + init Job pattern

When adding optional components, follow this pattern:

1. Add `{component}.enabled` boolean to `values.yaml`
2. Use `{{- if .Values.{component}.enabled }}` wrapper in templates
3. Create dedicated service (if exposed) with naming convention `{release}-{component}`

## Development Workflows

### Make Targets (Primary Commands)

| Command      | Purpose                               | Output                                                             |
| ------------ | ------------------------------------- | ------------------------------------------------------------------ |
| `make lint`  | Prettier formatting + Helm validation | Fixes formatting in-place; fails on chart syntax errors            |
| `make dump`  | Template all charts to YAML           | Creates `tmp/{chart-name}/manifest-00.yaml`, etc. (split by `---`) |
| `make test`  | Dump + validate templated YAML        | Runs validate_yaml.py on all manifests                             |
| `make build` | Package charts for distribution       | Creates `tmp/{chart-name}-{version}.tgz`                           |

**Workflow chain**: `make lint` → edit charts → `make dump` → `make test` → `make build`

### YAML Validation

Custom Python validator (tools/validate_yaml.py):

- Uses `yaml.safe_load_all()` to handle multi-document YAML files
- Runs on templated manifests (not templates themselves)
- Exit code 2 = no files found (didn't run `make dump`), code 1 = syntax errors

**When adding new charts**: Always run `make test` after template changes—don't rely on `helm lint` alone.

### Helm Dependencies

Charts with subcharts (e.g., `charts/meilisearch/charts/`) require `helm dependency update` before templating. The Makefile **automatically runs** `helm dependency update` in `dump` and `build` targets. Subcharts are listed in `Chart.yaml`:

```yaml
dependencies:
  - name: redis
    version: "17.x.x"
    repository: https://charts.bitnami.com/bitnami
```

## Project-Specific Conventions

### Secret Management

- **values.secret.yml**: Git-ignored secrets file for sensitive values (credentials, API keys)
- Never commit secrets; populate via Helm secrets plugin or CI/CD secrets
- See charts/palworld/values.secret.yml, charts/enshrouded/values.secret.yml

### Naming Conventions

- Release names use hyphens: `{{ include "meilisearch.fullname" . }}` → `my-release-meilisearch`
- Service names follow pattern: `{fullname}`, `{fullname}-ui`, `{fullname}-api` (see Meilisearch)
- Label format: `app.kubernetes.io/name`, `app.kubernetes.io/instance` (Kubernetes standard)

### Version Management

- **Chart version**: Incremented in `Chart.yaml` for chart changes (not app changes)
- **appVersion**: Reflects the application version (e.g., `appVersion: latest` or specific tag)
- Use `version_checker.py` (if implemented) to detect version updates

### Security Hardening Pattern

Visible in charts/vein/values.yaml:

```yaml
podSecurityContext:
  runAsNonRoot: true
  runAsUser: 1000
  seccompProfile:
    type: RuntimeDefault
securityContext:
  allowPrivilegeEscalation: false
  capabilities:
    drop: [ALL]
```

When adding container specs, include security contexts—don't accept default privileged behavior.

## Cross-Component Patterns

### Meilisearch Ingress Merging

The **00-merge-istio-routes.yaml** template merges Meilisearch routes into the Istio Ingress chart's values dynamically. This prevents duplication and keeps routing logic synchronized. Similar patterns may appear in other charts—check for `Chart.yaml` dependency sections.

### Storage Classes

Charts support optional `storageClassName` parameter (e.g., `palworld`, `postgres`, `enshrouded`). When modifying PVC templates, respect the `storageClassName` variable; don't hardcode.

### Stateful Services

Multi-node applications (PostgreSQL, Meilisearch) use **StatefulSets**, not Deployments. Preserve pod naming guarantees (`meilisearch-0`, `postgres-0`) in service discovery and init scripts.

## Common Gotchas

1. **Library charts in build**: If `Chart.yaml` has `type: library`, it's skipped by `make dump` and `make build`—intended behavior for dependency-only charts.
2. **Template debugging**: Run `helm template {chart}` directly to debug templating issues without running `make dump`.
3. **Whitespace in templates**: Helm template indentation is significant. Use `{{- }}` to strip whitespace; misalignment breaks YAML.
4. **Secret sync jobs**: Some charts (postgres) include Jobs that sync passwords post-deployment—verify Job completion before debugging pod startup issues.

## Tools & Dependencies

- **Helm 3**: Required for templating and packaging
- **Python 3.14+**: For YAML validation (pyproject.toml requirement)
- **PyYAML**: YAML parsing in validation script
- **Prettier**: Code formatting (via npx)
- **uv**: Package runner for Python tools (handles pyproject.toml)

Install with: `helm`, `python3`, `npm` (or `npx`), then `pip install -r requirements` or let `uv` handle it.

---

**Last updated**: December 2025 | For questions, open an issue in the repository.
