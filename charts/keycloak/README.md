# Keycloak Helm Chart

This chart deploys Keycloak with secure defaults, persistent data storage, Istio-ready ingress options, and GitOps-aware Argo CD ordering.

## Design Highlights

- Uses the upstream Keycloak image: `quay.io/keycloak/keycloak`
- Starts in production mode by default with `start --optimized`
- Runs a rootless init container (`kc.sh build`) to prepare optimized startup inside the pod
- Enables health and metrics endpoints by default
- Enforces rootless runtime defaults, seccomp `RuntimeDefault`, dropped capabilities, and read-only root filesystem with `/tmp` scratch volume
- Supports external PostgreSQL credentials via existing Kubernetes Secrets
- Supports optional realm import via ConfigMap + `--import-realm`
- Supports optional Istio ingress via the `istio-ingress` dependency
- Uses `gitops-tools` helpers for Argo CD labels and sync-wave annotations

## Quick Start

```bash
helm dependency build charts/keycloak
helm upgrade --install keycloak charts/keycloak --namespace keycloak --create-namespace
```

By default, the chart expects an existing DB password secret named `keycloak-db` with a key named `password`.

Example:

```bash
kubectl -n keycloak create secret generic keycloak-db --from-literal=password='super-secret-db-password'
```

## Runtime Notes

The chart follows current Keycloak container guidance:

- Admin bootstrap credentials are supplied using `KC_BOOTSTRAP_ADMIN_USERNAME` and `KC_BOOTSTRAP_ADMIN_PASSWORD`
- Database connection is configured with `KC_DB_*` variables
- Main process uses `/opt/keycloak/bin/kc.sh`
- Realm import can be enabled by mounting files to `/opt/keycloak/data/import` and adding `--import-realm`

## Important Values

- `keycloak.production`: Toggle `start` vs `start-dev`
- `keycloak.buildInit.enabled`: Enable the rootless init container that runs `kc.sh build` before startup
- `keycloak.optimizedStart`: Force `--optimized` when `keycloak.buildInit.enabled=false`
- `bootstrapAdmin.*`: Manage admin bootstrap secret creation or reuse
- `database.*`: Configure external DB host/user/password secret
- `persistence.*`: Reuse an existing claim or create/manage one in-chart
- `ingress.*`: Optional Kubernetes Ingress resource
- `argoCd.*`: Auto/forced Argo CD metadata behavior through `gitops-tools`
