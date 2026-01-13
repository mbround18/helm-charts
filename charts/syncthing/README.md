# Syncthing Helm Chart

A Helm chart for deploying Syncthing on Kubernetes. This chart provides persistent storage, flexible service exposure, and easy configuration for secure file synchronization across devices.

## Features

- Persistent storage for Syncthing data
- Configurable resources and security context
- Flexible service types (NodePort, LoadBalancer)
- Easy configuration via values.yaml

## Prerequisites

- Kubernetes 1.19+
- Helm 3.2.0+
- PersistentVolume provisioner

## Quick Start

```bash
helm repo add mbround18 https://mbround18.github.io/helm-charts/
helm repo update
helm install syncthing mbround18/syncthing --namespace syncthing --create-namespace
```

## Configuration

| Parameter           | Description                          | Default               |
| ------------------- | ------------------------------------ | --------------------- |
| image.repository    | Container image repository           | "syncthing/syncthing" |
| image.tag           | Image tag/version                    | "latest"              |
| resources           | CPU/memory requests/limits           | See values.yaml       |
| service.type        | Service type (NodePort/LoadBalancer) | "NodePort"            |
| persistence.enabled | Enable persistent storage            | true                  |
| persistence.size    | PVC size for data                    | "10Gi"                |

## Usage Examples

### Custom Resources

```yaml
resources:
  requests:
    cpu: 1
    memory: 1Gi
  limits:
    cpu: 2
    memory: 2Gi
```

## Troubleshooting

- Check pod logs: `kubectl logs -n syncthing <pod>`
- Ensure PVC is bound: `kubectl get pvc -n syncthing`
- Verify service type and external IP

---

For full configuration options, see [values.yaml](values.yaml).
