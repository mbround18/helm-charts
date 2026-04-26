---
applyTo: "charts/**/Chart.yaml,charts/**/values*.y*ml,charts/**/templates/**/*.yaml,charts/**/templates/**/*.tpl,charts/**/README.md,docs/argocd-gitops.md"
description: "Use when designing or modifying Helm charts, chart integrations, Argo CD metadata, or GitOps ordering. Enforces the repository GitOps wave model for chart design."
---

# Chart GitOps Design

Use the repository GitOps phase model when designing charts and chart integrations.

## Required Phase Order

- `foundation` = `0`: Secrets, PVCs, service accounts, bootstrap ConfigMaps, and other prerequisites
- `database` = `10`: Databases and other stateful data-layer workloads
- `supporting` = `20`: Supporting jobs or workloads that prepare dependencies for the main app
- `release` = `30`: The primary application Deployment or StatefulSet
- `ingress` = `40`: Services, Ingresses, VirtualServices, and other traffic-routing config

## Design Rules

- Do not invent custom wave values when one of the standard phases fits.
- For integrated charts, dependency resources must land in an earlier phase than the application that consumes them.
- If a chart already depends on `gitops-tools`, prefer `gitops-tools.argocd.annotations` with `phase: ...` over hard-coded numeric waves.
- If a chart does not use `gitops-tools`, keep numeric sync waves aligned to the same phase mapping.
- Services and ingress-related resources belong in `ingress`, not in `release`.
- Primary databases and data stores belong in `database`, not in `supporting`.
- Provisioning or password sync jobs belong in `supporting` when they depend on an earlier workload being up.

## Integration Expectations

- Database-backed apps should typically follow: `foundation` → `database` → `supporting` → `release` → `ingress`.
- Standalone apps without an external data layer should still separate foundational resources from the main release and routing resources.
- If a helper library changes under a `file://` dependency, run `make deps-update` before testing so vendored subcharts pick up the change.

## Validation Expectations

- Update chart tests and manifest contract assertions when sync-wave behavior changes.
- Run `make test` after chart design changes.
- If dependency metadata or vendored library behavior changed, run `make deps-update` before `make test`.

See `docs/argocd-gitops.md` for the full repository policy.
