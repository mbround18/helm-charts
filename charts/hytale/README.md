# Hytale

Helm chart to deploy the Hytale dedicated server using the mbround18/hytale image.

## Ports

- Server: UDP 5520 (configurable via `endpoint.serverPort` and `SERVER_PORT`)
- Remote console: TCP 7000 (configurable via `endpoint.consolePort` and `REMOTE_CONSOLE_PORT`)

## Persistence

Mounts `/data` for downloads, logs, credentials, and server files.

## Notes

On first boot, the server prints a device login URL/code in the logs. Complete the login to authenticate.

### Non-root and filesystem permissions

The chart runs the container as a non-root user by default (UID/GID 1000) and sets `fsGroup` so Kubernetes will attempt to set group ownership on mounted volumes. Additionally, an optional init container (enabled by default) will chown `/data` to the non-root UID/GID if required.

## Quick install

Install directly with a few quick overrides:

```bash
# Install with inline values
helm install my-hytale ./charts/hytale \
  --set endpoint.serverPort=5520 \
  --set endpoint.consolePort=7000 \
  --set pvc.size=20Gi

# Or using a values file
cat > hytale-values.yaml <<'EOF'
replicaCount: 1
endpoint:
  serverPort: 5520
  consolePort: 7000
pvc:
  name: data
  size: 20Gi
securityContext:
  runAsUser: 1000
  runAsGroup: 1000
podSecurityContext:
  fsGroup: 1000
initChown:
  enabled: true
  image: busybox:1.36

# Optional: import env vars from a ConfigMap or Secret
# Use the same name as your ConfigMap/Secret. Both are optional and can be left blank.
envFrom:
  configMapName: "my-hytale-configmap"
  configMapOptional: false
  secretName: ""
  secretOptional: true
EOF

helm install -f hytale-values.yaml my-hytale ./charts/hytale
```

> Tip: The NodePort service will auto-assign ports unless you explicitly set `nodePort` values in the chart or pass them via `--set`.

## Configuration & Options

For the complete set of environment variables, CLI flags, networking, and hosting recipes, see the upstream [server-hosting guide](https://github.com/mbround18/hytale/blob/main/docs/guides/server-hosting.md).
