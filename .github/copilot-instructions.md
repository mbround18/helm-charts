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

| Command            | Purpose                                      | Output                                                              |
| ------------------ | -------------------------------------------- | ------------------------------------------------------------------- |
| `make lint`        | Prettier formatting + Helm validation        | Fixes formatting in-place; fails on chart syntax errors             |
| `make dump`        | Template all charts to YAML                  | Creates `tmp/{chart-name}/manifest-00.yaml`, etc. (split by `---`)  |
| `make validate`    | Python syntax + manifest contract validation | Runs Python compile checks and pytest-based manifest validation     |
| `make test`        | Full repository validation                   | Runs `make validate` and then the full pytest suite                 |
| `make deps-update` | Refresh chart dependencies                   | Updates Helm dependencies and rewrites committed `Chart.lock` files |
| `make refresh`     | Refresh generated repo state                 | Updates lockfiles, image tags, and generated README content         |
| `make build`       | Package charts for distribution              | Creates `tmp/{chart-name}-{version}.tgz`                            |

**Workflow chain**: `make lint` → edit charts → `make dump` → `make test` → `make build`

### YAML Validation

Rendered manifest validation now runs under pytest in `charts/tests/test_manifest_contracts.py`, so it benefits from the repository's parallel pytest configuration.

Snapshot-style golden file assertions are intentionally not part of the workflow. Prefer contract-style assertions over rendered manifests so upgrades do not require bulk snapshot rewrites.

**When adding new charts**: Always run `make test` after template changes. Do not rely on `helm lint` alone.

### Helm Dependencies

Charts with subcharts or local library dependencies must commit `Chart.lock`. Normal `make dump`, `make test`, and `make build` use lockfile-driven `helm dependency build --skip-refresh`. Use `make deps-update` only when you intentionally refresh dependency versions or need to re-vendor updated local library charts. Subcharts are listed in `Chart.yaml`:

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

### Resource Ordering with Helm Hooks and Argo Sync Waves

**Critical for multi-dependent resources**: Always implement resource ordering to ensure prerequisites exist before dependents.

**Pattern**: Use the repository's Argo CD sync-wave phase model for GitOps ordering, and add Helm hooks only when a resource must run in a Helm lifecycle phase.

1. **Helm Hooks** (in template metadata annotations):

   ```yaml
   annotations:
     helm.sh/hook: pre-install,pre-upgrade # When to execute
     helm.sh/hook-weight: "-10" # Order within hook phase (-10 first, +10 last)
     helm.sh/resource-policy: keep # Preserve on uninstall
   ```

2. **Argo Sync Waves** (for GitOps ordering):
   ```yaml
   annotations:
     argocd.argoproj.io/sync-wave: "30"
   ```

**Standard phase model**:

- `foundation` = `0`: Secrets, PVCs, service accounts, bootstrap ConfigMaps, and other prerequisites
- `database` = `10`: Databases and other stateful data-layer workloads
- `supporting` = `20`: Supporting jobs or workloads that prepare dependencies for the main app
- `release` = `30`: The primary application Deployment or StatefulSet
- `ingress` = `40`: Services, Ingresses, VirtualServices, and other traffic-routing config

**Chart design rules**:

1. If a chart already depends on `gitops-tools`, use `gitops-tools.argocd.annotations` with a named `phase` instead of hard-coded wave numbers.
2. If a chart does not yet use `gitops-tools`, keep numeric sync waves aligned to the same five phases.
3. Do not invent one-off wave values like `33` when one of the standard phases already applies.
4. For integrated charts, place dependency resources earlier than the main release workload. Example: database `10` → provisioning job `20` → application `30` → service/ingress `40`.
5. If you change a local library helper used via `file://` dependencies, run `make deps-update` so consuming charts vendor the new helper before testing.

**Implementation pattern** (example: PostgreSQL + Meilisearch + application release):

- **foundation 0**: passwords, keys, PVCs, service accounts, bootstrap ConfigMaps
- **database 10**: `postgres-statefulset.yaml`, `meilisearch-statefulset.yaml`
- **supporting 20**: `provisioning-job.yaml`, `password-sync-job.yaml`
- **release 30**: `wikijs` / `vaultwarden` / `vein` primary workload
- **ingress 40**: Services, Ingresses, VirtualServices, route config

**When to add**: Every Secret, PVC, ConfigMap, Job, Deployment, StatefulSet, Service, Ingress, or VirtualService that participates in dependency ordering. **Always add sync-wave metadata intentionally**; do not leave ordering to default wave `0` unless the resource is truly foundational.

**See**: `docs/argocd-gitops.md` for the repository policy and examples.

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
