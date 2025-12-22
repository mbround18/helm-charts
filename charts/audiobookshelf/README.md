# Audiobookshelf Helm chart

This chart deploys Audiobookshelf with recommended defaults for production-style clusters (PVC-backed config, metadata and audiobooks storage, non-root runtime, Istio VirtualService support).

## Quick install (Helm)

```bash
helm upgrade --install audiobookshelf ./charts/audiobookshelf --namespace audiobookshelf --create-namespace
```

Minimal values (example):

```yaml
# minimal audiobookshelf values for Argo inline injection
image:
  repository: ghcr.io/advplyr/audiobookshelf
  tag: latest

persistence:
  config:
    enabled: true
  metadata:
    enabled: true
  audiobooks:
    enabled: true
    # set storageClassName for ReadWriteMany where required

securityContext:
  runAsUser: 1000
  runAsGroup: 1000
  fsGroup: 1000

secrets:
  jwt:
    create: true
    name: audiobookshelf-jwt

istio:
  enabled: true
  hosts:
    - audiobookshelf.example.com

resources:
  requests:
    cpu: "100m"
    memory: "256Mi"
```

## Argo CD

For GitOps consumption we recommend embedding a small, minimal values set directly into the Argo `Application` rather than storing a separate values file in this repo. Below is a minimal example you can paste into the Argo `Application` under `source.helm.values`.

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: audiobookshelf
spec:
  project: default
  destination:
    server: https://kubernetes.default.svc
    namespace: audiobookshelf
  source:
    repoURL: "https://github.com/your-org/helm-charts"
    targetRevision: HEAD
    path: charts/audiobookshelf
    helm:
      values: |-
        image:
          repository: ghcr.io/advplyr/audiobookshelf
          tag: latest
        persistence:
          config:
            enabled: true
          metadata:
            enabled: true
          audiobooks:
            enabled: true
        securityContext:
          runAsUser: 1000
          runAsGroup: 1000
          fsGroup: 1000
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

- **Secrets**: For GitOps-managed clusters prefer SealedSecrets, ExternalSecrets, or `argocd-vault-plugin` instead of committing plaintext secrets to Git.

- **PVCs**: Ensure Argo is allowed to create PVCs in the target namespace. If you require `ReadWriteMany`, set the `storageClassName` for `persistence.audiobooks` to an appropriate class.

- **Healthchecks**: The chart configures liveness/readiness probes against `/healthcheck`; adjust the probe path or timing via chart values if needed.

For more details and configuration options see `values.yaml`.
