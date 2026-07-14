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

### Agones Mode

Set `agones.enabled: true` to run this chart as an [Agones](https://agones.dev) `GameServer` instead of a StatefulSet + NodePort Service. Agones must already be installed on the cluster (this chart does not install its CRDs). PVCs for world/save data and backups are created the same way in both modes.

```yaml
agones:
  enabled: true
  portPolicy: Dynamic # Dynamic | Static | Passthrough
  scheduling: Packed # Packed | Distributed
```

> **Caveat:** the `mbround18/palworld-docker` image has no Agones SDK integration built in, so nothing inside the container calls the SDK's `Ready()`/`Health()` RPCs. The `GameServer` will stay in `Scheduling`/`RequestReady` and never become allocatable unless you add a sidecar or wrapper that watches the game port and then calls the local SDK to mark it ready. `agones.health.disabled` defaults to `true` so Agones doesn't kill the pod for never reporting health in the meantime.

## Troubleshooting

- Check pod logs: `kubectl logs -n palworld <pod>`
- Ensure PVC is bound: `kubectl get pvc -n palworld`
- Verify service type and external IP

---

For full configuration options, see [values.yaml](values.yaml).
