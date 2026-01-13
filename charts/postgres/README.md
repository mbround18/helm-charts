# PostgreSQL Helm Chart

A Helm chart for deploying PostgreSQL on Kubernetes. This chart provides persistent storage, secure password management, and flexible service exposure for production-grade database hosting.

## Features

- Persistent storage for database data
- Secure password and superuser secret management
- Configurable resources and security context
- Flexible service types (ClusterIP, NodePort, LoadBalancer)
- Easy configuration via values.yaml

## Prerequisites

- Kubernetes 1.19+
- Helm 3.2.0+
- PersistentVolume provisioner

## Quick Start

```bash
helm repo add mbround18 https://mbround18.github.io/helm-charts/
helm repo update
helm install postgres mbround18/postgres --namespace postgres --create-namespace
```

## Configuration

| Parameter           | Description                                    | Default         |
| ------------------- | ---------------------------------------------- | --------------- |
| image.repository    | Container image repository                     | "postgres"      |
| image.tag           | Image tag/version                              | "latest"        |
| resources           | CPU/memory requests/limits                     | See values.yaml |
| service.type        | Service type (ClusterIP/NodePort/LoadBalancer) | "ClusterIP"     |
| persistence.enabled | Enable persistent storage                      | true            |
| persistence.size    | PVC size for database data                     | "10Gi"          |
| superuser.enabled   | Enable superuser account                       | true            |

## Usage Examples

### Custom Resources

```yaml
resources:
  requests:
    cpu: 1
    memory: 2Gi
  limits:
    cpu: 2
    memory: 4Gi
```

### Enable Superuser

```yaml
superuser:
  enabled: true
  password: "your-superuser-password"
```

## Troubleshooting

- Check pod logs: `kubectl logs -n postgres <pod>`
- Ensure PVC is bound: `kubectl get pvc -n postgres`
- Verify service type and external IP

---

For full configuration options, see [values.yaml](values.yaml).
