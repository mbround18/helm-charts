# Infisical Helm Chart

Deploy Infisical with optional Redis and Postgres.

## Features

- App StatefulSet with hardened defaults (non-root, seccomp, read-only root fs with tmp)
- Optional Redis and Postgres (toggle via values)
- Istio Gateway/VirtualService with external-dns annotations

## Operator onboarding (required)

You need the Infisical Secrets Operator installed to sync secrets and access the API.

### Option A: Helm CLI

```bash
# Add the Infisical Helm repo
helm repo add infisical https://dl.cloudsmith.io/public/infisical/helm-charts/helm/charts/
helm repo update

# Install the operator
helm install infisical-secrets-operator infisical/secrets-operator \
  --namespace infisical-operator-system --create-namespace \
  --version 0.10.9 \
  --set installCRDs=true

# Configure the operator to use your Infisical API endpoint (example)
kubectl apply -n infisical-operator-system -f - <<'YAML'
apiVersion: v1
kind: ConfigMap
metadata:
  name: infisical-config
data:
  hostAPI: https://you-domain.tld/api
YAML
```

### Option B: Flux (example)

If you use Flux, create a HelmRepository and HelmRelease similar to:

```yaml
apiVersion: source.toolkit.fluxcd.io/v1
kind: HelmRepository
metadata:
  name: infisical
  namespace: infisical-operator-system
spec:
  interval: 10m
  url: https://dl.cloudsmith.io/public/infisical/helm-charts/helm/charts/
---
apiVersion: helm.toolkit.fluxcd.io/v2
kind: HelmRelease
metadata:
  name: infisical-secrets-operator
  namespace: infisical-operator-system
spec:
  interval: 10m
  chart:
    spec:
      chart: secrets-operator
      version: 0.10.9
      sourceRef:
        kind: HelmRepository
        name: infisical
        namespace: infisical-operator-system
  install:
    createNamespace: false
    crds: Create
  upgrade:
    crds: Create
  values:
    installCRDs: true
```

## Quickstart

```bash
helm install infisical ./charts/infisical \
  --namespace infisical --create-namespace \
  --set istio.host=kv.boop.ninja
```

Alternatively, have the chart create the Namespace:

```bash
helm install infisical ./charts/infisical \
  --namespace infisical \
  --set namespace.create=true \
  --set namespace.name=infisical \
  --set istio.host=kv.boop.ninja
```

## Key Values

- image.repository/tag: Infisical image
- service.port/type: Service settings
- env.host/nodeEnv/nodeOptions/ddTraceEnabled: Basic app env
- secrets.dbConnectionSecret/dbConnectionKey: DB connection URI
- secrets.envFromSecret: Secret reference for environment
- redis.enabled: Enable embedded Redis (with password Secret)
- postgres.enabled: Enable embedded Postgres (PVC via storageClassName/storageSize)
- istio.enabled/host/gateway: Istio exposure and TLS
- ingress.enabled/className/annotations/hosts/tls: Kubernetes Ingress (non-Istio)
- serviceAccount.create/name/annotations/automount: Pod identity settings
- rbac.create/rules: Optional Role/RoleBinding
- redis.external.*: Configure external Redis when embedded is disabled
- postgres.external.*: Configure external Postgres when embedded is disabled
- namespace.create/name/labels/annotations: Optional Namespace creation by the chart

See `values.yaml` for all options.
