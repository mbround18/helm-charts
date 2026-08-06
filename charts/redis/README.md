# Redis

## Description

A Helm chart for deploying Redis on Kubernetes: persistent storage via a StatefulSet
volumeClaimTemplate (append-only file enabled), and secure defaults (non-root, no privilege
escalation, all capabilities dropped).

Authentication is disabled by default to mirror a simple single-tenant/local cache-and-queue
setup. This chart never accepts secret values through Helm values -- enabling `auth.enabled`
requires pointing `auth.existingSecret` at a Secret you create out-of-band:

```shell
kubectl -n ${NAMESPACE} create secret generic redis-password \
  --from-literal=REDIS_PASSWORD=<value>
```

```yaml
auth:
  enabled: true
  existingSecret: redis-password
```

## Quick Start

```bash
helm repo add mbround18 https://mbround18.github.io/helm-charts/
helm repo update
helm install redis mbround18/redis --namespace redis --create-namespace
```

## Configuration

| Parameter              | Description                                                                     | Default            |
| ---------------------- | ------------------------------------------------------------------------------- | ------------------ |
| image.repository       | Container image repository                                                      | `"redis"`          |
| image.tag              | Image tag/version                                                               | `"7-alpine"`       |
| auth.enabled           | Require a password (`--requirepass`)                                            | `false`            |
| auth.existingSecret    | Name of a pre-existing Secret holding the password (required when auth.enabled) | `""`               |
| auth.existingSecretKey | Key within that Secret                                                          | `"REDIS_PASSWORD"` |
| persistence.enabled    | Use a StatefulSet volumeClaimTemplate                                           | `true`             |
| persistence.size       | PVC size for append-only data                                                   | `"2Gi"`            |
| resources              | CPU/memory requests/limits                                                      | see `values.yaml`  |
| service.type           | Service type (ClusterIP/NodePort/LoadBalancer)                                  | `"ClusterIP"`      |
| service.port           | Service/container port                                                          | `6379`             |

For full configuration options, see [values.yaml](values.yaml).
