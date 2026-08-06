# Mongo

## Description

A Helm chart for deploying MongoDB on Kubernetes: persistent storage via a StatefulSet
volumeClaimTemplate, and secure defaults (non-root, no privilege escalation, all capabilities
dropped).

Authentication is disabled by default to mirror a simple single-tenant/local setup. This chart
never accepts secret values through Helm values -- enabling `auth.enabled` requires pointing
`auth.existingSecret` at a Secret you create out-of-band:

```shell
kubectl -n ${NAMESPACE} create secret generic mongo-root-password \
  --from-literal=MONGO_INITDB_ROOT_PASSWORD=<value>
```

```yaml
auth:
  enabled: true
  existingSecret: mongo-root-password
```

## Quick Start

```bash
helm repo add mbround18 https://mbround18.github.io/helm-charts/
helm repo update
helm install mongo mbround18/mongo --namespace mongo --create-namespace
```

## Configuration

| Parameter              | Description                                                                          | Default                        |
| ---------------------- | ------------------------------------------------------------------------------------ | ------------------------------ |
| image.repository       | Container image repository                                                           | `"mongo"`                      |
| image.tag              | Image tag/version                                                                    | `"8"`                          |
| auth.enabled           | Require MONGO_INITDB_ROOT_USERNAME/PASSWORD                                          | `false`                        |
| auth.rootUsername      | Root username when auth is enabled                                                   | `"root"`                       |
| auth.existingSecret    | Name of a pre-existing Secret holding the root password (required when auth.enabled) | `""`                           |
| auth.existingSecretKey | Key within that Secret                                                               | `"MONGO_INITDB_ROOT_PASSWORD"` |
| mongodb.db             | Database created via MONGO_INITDB_DATABASE                                           | `"bubbles"`                    |
| persistence.enabled    | Use a StatefulSet volumeClaimTemplate                                                | `true`                         |
| persistence.size       | PVC size for database data                                                           | `"10Gi"`                       |
| resources              | CPU/memory requests/limits                                                           | see `values.yaml`              |
| service.type           | Service type (ClusterIP/NodePort/LoadBalancer)                                       | `"ClusterIP"`                  |
| service.port           | Service/container port                                                               | `27017`                        |

For full configuration options, see [values.yaml](values.yaml).
