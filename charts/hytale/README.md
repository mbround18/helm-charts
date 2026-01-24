# Hytale Helm Chart

A Helm chart for deploying a Hytale dedicated server on Kubernetes using the `mbround18/hytale` image. The chart ships with persistent storage, sensible security defaults, and flexible service exposure for game hosting.

## Features

- Persistent `/data` volume for downloads, logs, credentials, and server files
- Non-root security defaults with optional ownership fix-up init container
- Configurable server and remote console ports
- Optional `envFrom` wiring for ConfigMaps/Secrets

## Prerequisites

- Kubernetes 1.19+
- Helm 3.2.0+
- PersistentVolume provisioner
- NodePort or LoadBalancer support for external access (if exposing the server)

## Ports

- Server: UDP 5520 (configurable via `endpoint.serverPort` and `SERVER_PORT`)
- Remote console: TCP 7000 (configurable via `endpoint.consolePort` and `REMOTE_CONSOLE_PORT`)

## Quick Start

```bash
helm repo add mbround18 https://mbround18.github.io/helm-charts/
helm repo update
helm install hytale mbround18/hytale --namespace hytale --create-namespace
```

## Configuration

| Parameter                  | Description                                    | Default            |
| -------------------------- | ---------------------------------------------- | ------------------ |
| image.repository           | Container image repository                     | "mbround18/hytale" |
| image.tag                  | Image tag/version                              | "latest"           |
| endpoint.serverPort        | Game server UDP port                           | 5520               |
| endpoint.consolePort       | Remote console TCP port                        | 7000               |
| pvc.size                   | PVC size for `/data`                           | "20Gi"             |
| service.type               | Service type (NodePort/LoadBalancer/ClusterIP) | "NodePort"         |
| service.create             | Create external service                        | true               |
| podSecurityContext.fsGroup | Filesystem group for volume permissions        | 1000               |
| securityContext.runAsUser  | Container UID                                  | 1000               |
| initChown.enabled          | Init container to `chown` `/data`              | true               |

## Usage Examples

### Custom Ports and PVC Size

```yaml
endpoint:
  serverPort: 5520
  consolePort: 7000
pvc:
  size: 20Gi
```

### Run with ClusterIP Only

```yaml
service:
  type: ClusterIP
```

### Disable External Service

```yaml
service:
  create: false
```

### Import Environment Variables from ConfigMap/Secret

```yaml
envFrom:
  configMapName: "my-hytale-configmap"
  configMapOptional: false
  secretName: "my-hytale-secret"
  secretOptional: true
```

## Environment Variables & Server Options

For the complete reference of environment variables, CLI flags, networking options, and hosting recipes, see the upstream [server-hosting guide](https://github.com/mbround18/hytale/blob/main/docs/guides/server-hosting.md).

## Notes

On first boot, the server prints a device login URL/code in the logs. Complete the login to authenticate.

The chart runs the container as a non-root user by default (UID/GID 1000) and sets `fsGroup` so Kubernetes will attempt to set group ownership on mounted volumes. An optional init container (enabled by default) will `chown` `/data` to the non-root UID/GID if required.

## Argo CD Note

When using NodePort, it is recommended to ignore dynamic `nodePort` values in your Argo CD Application manifest:

```yaml
ignoreDifferences:
  - group: ""
    kind: Service
    jqPathExpressions:
      - .spec.ports[].nodePort
```

---

For full configuration options, see [charts/hytale/values.yaml](charts/hytale/values.yaml).
