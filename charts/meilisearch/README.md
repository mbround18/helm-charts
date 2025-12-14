# Meilisearch Helm Chart

A comprehensive Helm chart for deploying Meilisearch with optional UI, multiple ingress options, and API key provisioning.

## Features

- **Meilisearch Server**: Full-featured search engine deployment
- **Optional UI Sidecar**: Deploy [riccoxie/meilisearch-ui](https://github.com/eyeix/meilisearch-ui) alongside Meilisearch
- **Flexible Ingress**: Support for both standard Kubernetes Ingress and Istio ingress
- **API Key Provisioning**: Automatic Meilisearch API key generation and storage
- **Health Checks**: Liveness and readiness probes for both Meilisearch and UI
- **Persistent Storage**: Configurable PVC for data persistence

## Quick Start

### Basic Deployment

```bash
helm install meilisearch ./charts/meilisearch \
  --set auth.masterKeySecret=my-master-key
```

### With UI Enabled

```bash
helm install meilisearch ./charts/meilisearch \
  --set ui.enabled=true \
  --set ingress.enabled=true \
  --set ingress.className=nginx
```

### With Istio Ingress

```bash
helm install meilisearch ./charts/meilisearch \
  --set ui.enabled=true \
  --set istio-ingress.enabled=true
```

## Configuration

### Core Settings

| Parameter             | Description                  | Default                |
| --------------------- | ---------------------------- | ---------------------- |
| `image.repository`    | Meilisearch image            | `getmeili/meilisearch` |
| `image.tag`           | Image tag                    | `v1.11.1`              |
| `resources`           | Pod resource requests/limits | `{}`                   |
| `persistence.enabled` | Enable persistent storage    | `true`                 |
| `persistence.size`    | PVC size                     | `10Gi`                 |

### UI Configuration

| Parameter             | Description                    | Default                   |
| --------------------- | ------------------------------ | ------------------------- |
| `ui.enabled`          | Deploy UI sidecar              | `false`                   |
| `ui.image.repository` | UI image                       | `riccoxie/meilisearch-ui` |
| `ui.image.tag`        | UI image tag                   | `latest`                  |
| `ui.basePath`         | UI URL path                    | `/manage`                 |
| `ui.port`             | UI container port              | `24900`                   |
| `ui.ingress.enabled`  | Include UI in standard Ingress | `false`                   |
| `ui.resources`        | UI resource requests/limits    | `{}`                      |

### Kubernetes Ingress

Enable standard Kubernetes Ingress (not Istio):

```yaml
ingress:
  enabled: true
  className: nginx # or other ingress controller
  domain: "meilisearch.example.com"
  tls:
    enabled: true
    secretName: meilisearch-tls
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod

ui:
  enabled: true
  ingress:
    enabled: true # Include UI in ingress
```

**Result:**

- API accessible at: `https://meilisearch.example.com/`
- UI accessible at: `https://meilisearch.example.com/manage`

### Istio Ingress

Enable Istio ingress (automatically includes UI routes):

```yaml
ui:
  enabled: true
  basePath: "/manage"

istio-ingress:
  enabled: true
  virtualService:
    hosts:
      - "meilisearch.example.com"
  gateway:
    selector:
      istio: ingress

    servers:
      - port:
          number: 80
          protocol: HTTP
          name: http
        hosts:
          - "*"
```

**Result:**

- API route: `meilisearch.example.com/` → `meilisearch:7700`
- UI route: `meilisearch.example.com/manage` → `meilisearch-ui:24900`

Routes are dynamically generated based on `ui.enabled` in [templates/00-merge-istio-routes.yaml](templates/00-merge-istio-routes.yaml).

### API Key Provisioning

Auto-generate and store Meilisearch API keys:

```yaml
provisioning:
  enabled: true
  indexSecret: meilisearch-api-key
  apiKeyDescription: "Wiki.js API Key"
  apiKeyActions: ["*"]
  apiKeyIndexes: ["*"]
```

The provisioning job creates a Kubernetes Secret containing the generated API key.

### Master Key Configuration

Set the Meilisearch master key via a secret:

```bash
kubectl create secret generic meilisearch-master-key --from-literal=master-key=your-secure-key
```

Or pass at install time:

```bash
helm install meilisearch ./charts/meilisearch \
  --set auth.masterKeySecret=meilisearch-master-key
```

## Usage Examples

### Example 1: Meilisearch + UI with Nginx Ingress

```yaml
# values.yaml
image:
  tag: v1.11.1

ui:
  enabled: true
  basePath: "/admin"

service:
  type: ClusterIP
  port: 7700

ingress:
  enabled: true
  className: nginx
  domain: "search.example.com"
  tls:
    enabled: true
    secretName: search-tls

provisioning:
  enabled: true
  indexSecret: search-api-key

auth:
  masterKeySecret: meilisearch-master-key
```

### Example 2: Meilisearch with Istio

```yaml
ui:
  enabled: true
  basePath: "/manage"

istio-ingress:
  enabled: true
  virtualService:
    hosts:
      - "search.example.com"
  gateway:
    selector:
      istio: ingress

provisioning:
  enabled: true
```

### Example 3: Meilisearch Only (No UI, No Ingress)

```yaml
ui:
  enabled: false

ingress:
  enabled: false

istio-ingress:
  enabled: false

provisioning:
  enabled: false
```

## Architecture

### Services

- **meilisearch**: Main API service (port 7700)
- **meilisearch-ui**: Optional UI service (port 24900)

### Ingress Options

| Option             | Standard Ingress             | Istio Ingress  |
| ------------------ | ---------------------------- | -------------- |
| Path-based routing | ✅                           | ✅             |
| UI support         | ✅ (if `ui.ingress.enabled`) | ✅ (automatic) |
| TLS termination    | ✅                           | ✅             |
| SNI routing        | ❌                           | ✅             |

### Dynamic Configuration

The chart uses template helpers to avoid duplication:

- **`meilisearch.istioHttpRoutes`**: Generates HTTP routes with optional UI
- **`meilisearch.ingressPaths`**: Generates Ingress paths with optional UI
- **`00-merge-istio-routes.yaml`**: Merges UI routes into istio-ingress at render time

## Troubleshooting

### UI not accessible via Ingress

Make sure both flags are enabled:

```yaml
ui:
  enabled: true
  ingress:
    enabled: true # Required for standard Ingress
```

For Istio, just enable `ui.enabled` and `istio-ingress.enabled`.

### Istio routes not applied

Check that the routes were merged:

```bash
kubectl get virtualservice <release>-vs -o yaml | grep meilisearch-ui
```

### Master key not found

Ensure the secret exists:

```bash
kubectl get secret meilisearch-master-key
```

### API key provisioning fails

Check the provisioning job logs:

```bash
kubectl logs -f job/<release>-meilisearch-provisioning
```

## License

Apache License 2.0
