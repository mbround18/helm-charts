# Enshrouded Helm Chart

A Helm chart for deploying an Enshrouded dedicated server on Kubernetes. This chart uses the official Enshrouded server image to provide persistent, scalable, and customizable game hosting.

## Features

- Persistent storage for world and save data
- Automatic backups (optional)
- Configurable resources and security context
- Flexible service types (NodePort, LoadBalancer)
- Easy configuration via values.yaml

## Prerequisites

- Kubernetes 1.19+
- Helm 3.2.0+
- PersistentVolume provisioner
- LoadBalancer or NodePort support for external access

## Quick Start

```bash
helm repo add mbround18 https://mbround18.github.io/helm-charts/
helm repo update
helm install enshrouded mbround18/enshrouded --namespace enshrouded --create-namespace
-------------------+
```

## Configuration

| Parameter           | Description                          | Default             |
| ------------------- | ------------------------------------ | ------------------- |
| image.repository    | Container image repository           | "enshrouded/server" |
| image.tag           | Image tag/version                    | "latest"            |
| resources           | CPU/memory requests/limits           | See values.yaml     |
| service.type        | Service type (NodePort/LoadBalancer) | "NodePort"          |
| persistence.enabled | Enable persistent storage            | true                |
| persistence.size    | PVC size for world data              | "20Gi"              |
| backups.enabled     | Enable automatic backups             | false               |

## Usage Examples

### Custom Resources

```yaml
limits:
  cpu: 4
  memory: 8Gi
```

enabled: true

```

## Troubleshooting
- Check pod logs: `kubectl logs -n enshrouded <pod>`
- Ensure PVC is bound: `kubectl get pvc -n enshrouded`
- Verify service type and external IP

---
For full configuration options, see [values.yaml](values.yaml).
```
