# PVC Watcher Helm Chart

A Helm chart for deploying a PVC watcher utility on Kubernetes. This chart monitors PersistentVolumeClaims and can trigger cleanup or alerting actions for cluster storage management.

## Features

- Monitors PVCs for status and usage
- Configurable alerting and cleanup actions
- Lightweight deployment
- Easy configuration via values.yaml

## Prerequisites

- Kubernetes 1.19+
- Helm 3.2.0+

## Quick Start

```bash
helm repo add mbround18 https://mbround18.github.io/helm-charts/
helm repo update
helm install pvc-watcher mbround18/pvc-watcher --namespace pvc-watcher --create-namespace
```

## Configuration

| Parameter        | Description                  | Default         |
| ---------------- | ---------------------------- | --------------- |
| image.repository | Container image repository   | "pvc-watcher"   |
| image.tag        | Image tag/version            | "latest"        |
| resources        | CPU/memory requests/limits   | See values.yaml |
| alert.enabled    | Enable alerting              | false           |
| cleanup.enabled  | Enable automatic PVC cleanup | false           |

## Usage Examples

### Enable Alerting

```yaml
alert:
  enabled: true
  webhook: "https://hooks.example.com/alert"
```

### Enable Cleanup

```yaml
cleanup:
  enabled: true
  schedule: "0 4 * * *"
```

## Troubleshooting

- Check pod logs: `kubectl logs -n pvc-watcher <pod>`
- Verify alerting and cleanup configuration

---

For full configuration options, see [values.yaml](values.yaml).
