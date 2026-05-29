# Helm Hub Helm chart

This chart deploys [Helm Hub](https://github.com/mbround18/helm-hub) - a modern helm chart repository with a beautiful UI and robust API.

## Features

- **Database**: Integrated PostgreSQL statefulset for persistent metadata.
- **Shared Storage**: Support for `ReadWriteMany` persistence to share chart data across multiple replicas.
- **GitOps Ready**: Built with `gitops-tools` for ArgoCD sync-wave orchestration.
- **Traffic Management**: Native support for Istio `VirtualService` and standard Kubernetes `Ingress`.
- **Metrics**: Prometheus-ready metrics endpoint on port 9090.

## Quick install (Helm)

```bash
helm upgrade --install helm-hub ./charts/helm-hub --namespace helm-hub --create-namespace
```

## Configuration

| Parameter                | Description               | Default              |
| ------------------------ | ------------------------- | -------------------- |
| `image.repository`       | Main application image    | `mbround18/helm-hub` |
| `image.tag`              | Image version             | `latest`             |
| `persistence.enabled`    | Enable chart storage PVC  | `true`               |
| `persistence.accessMode` | Storage access mode       | `ReadWriteMany`      |
| `persistence.size`       | Storage size              | `10Gi`               |
| `postgres.enabled`       | Enable internal database  | `true`               |
| `metrics.enabled`        | Expose Prometheus metrics | `true`               |

## Usage Examples

### Shared Persistence (ReadWriteMany)

For production deployments where you want multiple replicas, ensure your `storageClassName` supports `ReadWriteMany`:

```yaml
replicaCount: 3
persistence:
  storageClassName: "longhorn"
  accessMode: ReadWriteMany
```

### External Postgres

If you have an existing Postgres instance:

```yaml
postgres:
  enabled: false
database:
  host: "postgres.external.com"
  port: 5432
  name: "helmhub"
  user: "helmhub"
  password: "secure-password"
```

---

For full configuration options, see [values.yaml](values.yaml).
