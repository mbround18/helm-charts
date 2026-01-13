# Palworld Helm Chart

A Helm chart for deploying a Palworld dedicated server on Kubernetes. This chart provides persistent storage, optional backups, and flexible service exposure for scalable game hosting.

## Features

- Persistent storage for world and save data
- Optional automated backups
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
helm install palworld mbround18/palworld --namespace palworld --create-namespace
```

## Configuration

| Parameter           | Description                          | Default           |
| ------------------- | ------------------------------------ | ----------------- |
| image.repository    | Container image repository           | "palworld/server" |
| image.tag           | Image tag/version                    | "latest"          |
| resources           | CPU/memory requests/limits           | See values.yaml   |
| service.type        | Service type (NodePort/LoadBalancer) | "NodePort"        |
| persistence.enabled | Enable persistent storage            | true              |
| persistence.size    | PVC size for world data              | "20Gi"            |
| backups.enabled     | Enable automated backups             | false             |

## Usage Examples

### Custom Resources

```yaml
resources:
  requests:
    cpu: 2
    memory: 4Gi
  limits:
    cpu: 4
    memory: 8Gi
```

### Enable Automated Backups

```yaml
backups:
  enabled: true
  schedule: "0 3 * * *"
```

## Troubleshooting

- Check pod logs: `kubectl logs -n palworld <pod>`
- Ensure PVC is bound: `kubectl get pvc -n palworld`
- Verify service type and external IP

---

For full configuration options, see [values.yaml](values.yaml).
