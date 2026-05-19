# changedetection.io Helm chart

This chart deploys [changedetection.io](https://changedetection.io/) with recommended defaults for production-style clusters, including persistent storage, non-root runtime, and support for browser-based fetchers (Playwright/Sockpuppet and Selenium).

## Features

- Persistent storage for datastore
- Non-root runtime and security context
- Support for browser fetcher sidecars (Sockpuppet/Playwright and Selenium)
- Istio VirtualService and standard Ingress support
- GitOps ready with `gitops-tools` annotations

## Quick install (Helm)

```bash
helm upgrade --install changedetection-io ./charts/changedetection-io --namespace changedetection-io --create-namespace
```

## Configuration

| Parameter | Description | Default |
| --------- | ----------- | ------- |
| `image.repository` | Container image repository | `ghcr.io/dgtlmoon/changedetection.io` |
| `image.tag` | Image tag/version | `0.55.3` |
| `persistence.enabled` | Enable persistent storage | `true` |
| `persistence.size` | Size of persistent volume | `10Gi` |
| `browser.sockpuppet.enabled` | Enable Sockpuppet (Playwright) sidecar | `true` |
| `browser.selenium.enabled` | Enable Selenium sidecar | `false` |
| `istio-ingress.enabled` | Enable Istio VirtualService | `false` |

## Usage Examples

### Minimal values (Argo inline)

```yaml
persistence:
  enabled: true
  size: 10Gi
browser:
  sockpuppet:
    enabled: true
```

### Enable standard Ingress

```yaml
ingress:
  enabled: true
  hosts:
    - host: changedetection.example.com
      paths:
        - path: /
          pathType: Prefix
```

### Using Istio Ingress

```yaml
istio-ingress:
  enabled: true
  virtualService:
    route:
      host: changedetection.example.com
```

---

For full configuration options, see [values.yaml](values.yaml).
