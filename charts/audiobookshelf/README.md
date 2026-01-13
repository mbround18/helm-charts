# Audiobookshelf Helm chart

This chart deploys Audiobookshelf with recommended defaults for production-style clusters (PVC-backed config, metadata and audiobooks storage, non-root runtime, Istio VirtualService support).

## Features

- Persistent storage for config, metadata, and audiobooks
- Non-root runtime and security context
- Istio VirtualService and standard Ingress support
- Easy configuration via values.yaml

## Quick install (Helm)

```bash
helm upgrade --install audiobookshelf ./charts/audiobookshelf --namespace audiobookshelf --create-namespace
```

## Configuration

| Parameter                      | Description                 | Default                          |
| ------------------------------ | --------------------------- | -------------------------------- |
| image.repository               | Container image repository  | "ghcr.io/advplyr/audiobookshelf" |
| image.tag                      | Image tag/version           | "latest"                         |
| persistence.config.enabled     | Enable config PVC           | true                             |
| persistence.metadata.enabled   | Enable metadata PVC         | true                             |
| persistence.audiobooks.enabled | Enable audiobooks PVC       | true                             |
| securityContext.runAsUser      | User ID for container       | 1000                             |
| istio.enabled                  | Enable Istio VirtualService | true                             |

## Usage Examples

### Minimal values (Argo inline)

```yaml
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
secrets:
  jwt:
    create: true
    name: audiobookshelf-jwt
istio:
  enabled: true
```

### Enable standard Ingress

```yaml
ingress:
  enabled: true
  hosts:
    - audiobooks.example.com
```

---

For full configuration options, see [values.yaml](values.yaml).

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
