# FoundryVTT Helm Chart

A Helm chart for deploying Foundry Virtual Tabletop (VTT) on Kubernetes. This chart provides persistent storage, backup automation, and flexible ingress for secure, scalable game hosting.

## Features

- Persistent storage for worlds, modules, and user data
- Automated backup via CronJob
- Configurable resources and security context
- Flexible ingress (Kubernetes Ingress, Istio VirtualService)
- Easy configuration via values.yaml

## Prerequisites

- Kubernetes 1.19+
- Helm 3.2.0+
- PersistentVolume provisioner
- Ingress controller (nginx, traefik, or Istio)

## Quick Start

```bash
helm repo add mbround18 https://mbround18.github.io/helm-charts/
helm repo update
helm install foundryvtt mbround18/foundryvtt --namespace foundryvtt --create-namespace
```

## Configuration

| Parameter           | Description                          | Default                 |
| ------------------- | ------------------------------------ | ----------------------- |
| image.repository    | Container image repository           | "foundryvtt/foundryvtt" |
| image.tag           | Image tag/version                    | "latest"                |
| resources           | CPU/memory requests/limits           | See values.yaml         |
| service.type        | Service type (NodePort/LoadBalancer) | "NodePort"              |
| persistence.enabled | Enable persistent storage            | true                    |
| persistence.size    | PVC size for data                    | "10Gi"                  |
| backup.enabled      | Nightly archive of the Data volume   | true                    |
| backup.schedule     | Cron schedule for the archive        | "0 1 * * *"             |
| backup.keep         | Archives to keep                     | 7                       |
| ingress.enabled     | Enable ingress resource              | true                    |

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

### Enable Automated Backups

```yaml
backup:
  enabled: true
  schedule: "0 1 * * *"
  keep: 7
```

Each run writes `Backups/chart/data-<UTC timestamp>.tar.gz` from the Data
volume and removes all but the newest `keep` archives. Config is not included.
The archive is taken while Foundry runs, so a world saved at that moment may be
caught mid-write; restore from an older archive if one is inconsistent.

### Enable Istio Ingress

```yaml
ingress:
  enabled: true
  istio: true
```

## Troubleshooting

- Check pod logs: `kubectl logs -n foundryvtt <pod>`
- Ensure PVC is bound: `kubectl get pvc -n foundryvtt`
- Verify ingress and external IP

---

For full configuration options, see [values.yaml](values.yaml).
