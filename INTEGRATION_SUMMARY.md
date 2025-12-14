# Meilisearch Chart Integration Summary

## ✅ What's Working Together

### 1. **Flexible Ingress System**

- **Kubernetes Ingress** (nginx, traefik, etc.)
- **Istio Ingress** via istio-ingress subchart
- Both support automatic UI path routing

### 2. **Optional UI Sidecar**

- Runs alongside Meilisearch in same Pod
- Configurable base path (default: `/manage`)
- Health checks included
- Separate service for routing

### 3. **Dynamic Route Generation**

- API routes always included
- UI routes added only when `ui.enabled: true`
- Works for both Kubernetes and Istio ingress
- No YAML duplication via template helpers

### 4. **Smart Defaults**

- Master key from Kubernetes Secret
- Optional API key provisioning
- Persistent storage configured
- CORS-ready

## 📋 How It Works

### Standard Kubernetes Ingress Flow

```
User Request (https://meilisearch.example.com)
    ↓
Ingress Controller (Nginx/Traefik)
    ├─ Path: / → meilisearch service:7700 (API)
    └─ Path: /manage → meilisearch-ui service:24900 (UI)
```

### Istio Ingress Flow

```
User Request (meilisearch.example.com)
    ↓
Istio Gateway (ingressgateway)
    ↓
VirtualService (dynamically generated routes)
    ├─ Route: meilisearch-api → meilisearch service:7700
    └─ Route: meilisearch-ui → meilisearch-ui service:24900
         (only if ui.enabled=true)
```

## 🎯 Key Features

### No Duplication

- `_helpers.tpl`: Reusable helper templates
  - `meilisearch.istioHttpRoutes`: Generates Istio routes
  - `meilisearch.ingressPaths`: Generates K8s paths
- `00-merge-istio-routes.yaml`: Merges routes into istio-ingress values

### Conditional UI Support

```yaml
ui:
  enabled: true # Deploy UI sidecar
  ingress:
    enabled: true # For K8s Ingress only
  basePath: "/manage" # Customizable path

istio-ingress:
  enabled: true # Auto-includes UI routes
```

### Multiple Deployment Patterns

**Pattern 1: API Only**

```yaml
ui:
  enabled: false
ingress:
  enabled: true
istio-ingress:
  enabled: false
```

**Pattern 2: API + UI with Kubernetes Ingress**

```yaml
ui:
  enabled: true
  ingress:
    enabled: true
ingress:
  enabled: true
istio-ingress:
  enabled: false
```

**Pattern 3: API + UI with Istio**

```yaml
ui:
  enabled: true
istio-ingress:
  enabled: true
ingress:
  enabled: false
```

## 📦 File Structure

```
charts/meilisearch/
├── Chart.yaml                      # Dependencies: istio-ingress
├── values.yaml                     # All configuration
├── README.md                       # Comprehensive docs
└── templates/
    ├── 00-merge-istio-routes.yaml # 🔑 Dynamic route generation
    ├── _helpers.tpl               # 🔑 Reusable helpers
    ├── statefulset.yaml           # Meilisearch + optional UI
    ├── service.yaml               # API service
    ├── service-ui.yaml            # Optional UI service
    ├── ingress.yaml               # K8s Ingress (uses helpers)
    ├── provisioning-job.yaml      # API key generation
    ├── pvc.yaml                   # Persistent storage
    └── ...                        # Other support templates
```

## 🚀 Quick Deploy Examples

### Deploy with UI + Istio

```bash
helm install meilisearch ./charts/meilisearch \
  --set ui.enabled=true \
  --set istio-ingress.enabled=true
```

### Deploy with UI + Nginx Ingress

```bash
helm install meilisearch ./charts/meilisearch \
  --set ui.enabled=true \
  --set ingress.enabled=true \
  --set ingress.className=nginx
```

### Deploy API-only

```bash
helm install meilisearch ./charts/meilisearch
```

## 🔗 Integration Points

- **istio-ingress subchart**: Used when `istio-ingress.enabled=true`
- **kubernetes Ingress API**: Used when `ingress.enabled=true`
- **Service routing**: Automatic FQDN with namespace support
- **Health checks**: Both containers have liveness/readiness probes

## ✨ Highlights

✅ **No Config Duplication** - Helpers handle routing for both ingress types
✅ **UI Optional** - Single switch to add/remove UI
✅ **Flexible Paths** - Customize UI basePath
✅ **Smart Defaults** - Works out-of-the-box
✅ **Istio Ready** - Full subchart integration
✅ **Namespace Aware** - Proper FQDN for cross-namespace routing
✅ **Health Checks** - Both API and UI have probes
✅ **API Provisioning** - Optional automatic key generation

---

Built with ❤️ for seamless Meilisearch + UI deployment on Kubernetes
