---
name: charts
description: >
  Install and configure Helm charts from the mbround18 helm-chart repository
  (https://mbround18.github.io/helm-charts). Covers audiobookshelf, changedetection-io,
  enshrouded, forgejo, foundryvtt, fvtt-dndbeyond-companion, grafana, helm-hub, hytale,
  istio-ingress, keycloak, meilisearch, openobserve, opentelemetry-collector, palworld,
  postgres, pvc-watcher, syncthing, valheim, vaultwarden, vein, wikijs. Use when the user
  asks to install, configure, upgrade, or troubleshoot any of these charts via Helm CLI,
  ArgoCD, or FluxCD.
license: MIT
compatibility: Requires helm >=3.12, kubectl, and optionally argocd-cli or flux-cli
metadata:
  author: mbround18
  repo: https://github.com/mbround18/helm-charts
  generated-by: scripts/generate-charts-skill.py
allowed-tools: Bash(helm:*) Bash(kubectl:*) Bash(flux:*) Bash(argocd:*) Read
---

# mbround18 Helm Charts Skill

Full chart metadata, values references, and CRD schemas live in the `references/` and
`assets/` directories — load them as needed rather than guessing.

- All chart data (names, versions, values keys): [references/charts.json](references/charts.json)
- Live CRD schemas (ArgoCD, FluxCD, Istio): [references/crds.json](references/crds.json)
- Install templates: [assets/](assets/)

## Helm Repository

```bash
helm repo add mbround18 https://mbround18.github.io/helm-charts
helm repo update
```

Charts are published as `mbround18/<chart-name>`. Library charts (`game-tools`,
`gitops-tools`) are not installable directly — they are subcharts only.

## Installation Methods

### 1. Helm CLI

```bash
helm install <release-name> mbround18/<chart-name> \
  --namespace <namespace> \
  --create-namespace \
  --version <version> \
  -f values.yaml
```

Key flags:
- `--set key=value` for one-off overrides
- `--wait` to block until all resources are ready
- `--timeout 10m` for charts with heavy init (forgejo, wikijs)
- `helm upgrade --install` for idempotent apply

### 2. ArgoCD

Use the template at [assets/argocd-application.yaml](assets/argocd-application.yaml).
The cluster has `applications.argoproj.io` CRD. Full spec shape is in
[references/crds.json](references/crds.json) under `argocd-application`.

Key fields:
```yaml
spec:
  source:
    repoURL: https://mbround18.github.io/helm-charts
    chart: <chart-name>
    targetRevision: <version>          # e.g. 0.1.11
    helm:
      valuesObject: {}                 # inline values (preferred over values string)
  destination:
    server: https://kubernetes.default.svc
    namespace: <namespace>
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
```

#### Sync Waves

All charts use ArgoCD sync waves. Do not invent new wave numbers:

| Phase       | Wave | Resource types                              |
|-------------|------|---------------------------------------------|
| foundation  | 0    | Secrets, PVCs, ServiceAccounts, ConfigMaps  |
| database    | 10   | Database StatefulSets                        |
| supporting  | 20   | Post-dependency Jobs                         |
| release     | 30   | Primary application Deployment/StatefulSet   |
| ingress     | 40   | Services, Ingresses, VirtualServices         |

Charts that depend on `gitops-tools` apply waves automatically via the
`gitops-tools.argocd.annotations` helper. If you need a custom Application
that wraps multiple charts, keep the wave ordering intact.

### 3. FluxCD

Use the template at [assets/fluxcd-helmrelease.yaml](assets/fluxcd-helmrelease.yaml).
The cluster has `helmreleases.helm.toolkit.fluxcd.io` v2 and
`helmrepositories.source.toolkit.fluxcd.io` v1. Full spec shapes in
[references/crds.json](references/crds.json).

Step 1 — add the Helm repository (once per cluster/namespace):
```yaml
apiVersion: source.toolkit.fluxcd.io/v1
kind: HelmRepository
metadata:
  name: mbround18
  namespace: flux-system
spec:
  interval: 1h
  url: https://mbround18.github.io/helm-charts
```

Step 2 — create a HelmRelease:
```yaml
apiVersion: helm.toolkit.fluxcd.io/v2
kind: HelmRelease
metadata:
  name: <release-name>
  namespace: <namespace>
spec:
  interval: 10m
  chart:
    spec:
      chart: <chart-name>
      version: "<version>"
      sourceRef:
        kind: HelmRepository
        name: mbround18
        namespace: flux-system
  values: {}
```

## Chart-Specific Notes

### postgres
Standalone PostgreSQL with secret management. Used as a subchart by `forgejo`,
`wikijs`, and `helm-hub`. Exposes `auth.password` and `auth.superuserPassword`;
when `secrets.password.create: true` these are stored in a Kubernetes Secret.
HA mode (`ha.enabled`) deploys a replica set — leave disabled unless you have a
compatible storage class.

### forgejo
Depends on `postgres` (aliased as `postgresql`) and `gitops-tools`. Requires an
`ExternalSecret` (or manual secret) with keys: `databasePassword`, `runnerToken`,
`githubToken`, `forgejoToken`. Set `config.server.root_url` and
`config.server.domain` before installing.

### istio-ingress
Subchart only — not installable standalone. Controls Istio `Gateway` and
`VirtualService` resources. Enable via `istio-ingress.enabled: true` in the parent
chart. `tls.credentialName` defaults to `cloudflare-client-tls`.

### wikijs
Bundles `postgres` and optionally `meilisearch`. Set `global.secret.annotations`
for external-secrets integration. The wiki DB defaults to `wikijs`/`wikijs`.

### Game servers (valheim, enshrouded, palworld, vein, hytale)
All use `game-tools` library for consistent StatefulSet rendering. Pass
server-specific env vars via the `environment` list. Storage class selection via
`storageClassName`. Backups are opt-in (`backups.enabled: true`).

### vaultwarden
Runs as UID 65534 (nobody). `persistence.enabled: true` is required — data loss
occurs without it. Strategy is `Recreate` to avoid two replicas mounting the same
PVC.

## Common Troubleshooting

```bash
# Render locally to inspect manifests
helm template release-name mbround18/<chart> -f values.yaml

# Check what's failing in ArgoCD
argocd app get <app-name> --show-operation

# Force FluxCD reconciliation
flux reconcile helmrelease <name> -n <namespace>

# Inspect generated secrets
kubectl get secret <name> -o jsonpath='{.data}' | base64 -d
```

## Upgrading Charts

```bash
helm repo update mbround18
helm upgrade <release> mbround18/<chart> -f values.yaml --version <new-version>
```

For ArgoCD: update `targetRevision` and sync. For FluxCD: update `version` field
and let the controller reconcile (interval-driven) or force it with `flux reconcile`.
