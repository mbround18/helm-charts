# Istio Ingress Subchart

A flexible Istio ingress subchart for managing Gateway and VirtualService resources with sensible defaults and comprehensive override capabilities.

## Features

- **Flexible Gateway Management**: Automatic or custom gateway configuration with pod selectors
- **Smart VirtualService Setup**: Auto-linking to local gateway or explicit gateway references
- **TLS/HTTPS Support**: Full TLS configuration with SIMPLE, MUTUAL, AUTO_PASSTHROUGH, and ISTIO_MUTUAL modes
- **External DNS Integration**: Built-in support for external-dns annotations
- **Complete Override Capability**: Override entire Gateway or VirtualService specs if needed
- **HTTP/TLS/TCP Routes**: Support for HTTP, TLS (SNI), and TCP routing
- **Cross-Namespace Support**: Export VirtualServices to other namespaces

## Usage

### Basic HTTP Ingress

```yaml
# In your parent chart's values.yaml
istio-ingress:
  enabled: true
  gateway:
    enabled: true
    selector:
      app: istio-ingressgateway
  virtualService:
    enabled: true
    hosts:
      - "myapp.example.com"
    http:
      - route:
          - destination:
              host: myapp.default.svc.cluster.local
              port:
                number: 8080
```

### HTTPS with TLS Certificate

```yaml
istio-ingress:
  enabled: true
  tls:
    enabled: true
    mode: SIMPLE
    credentialName: my-tls-secret  # Kubernetes secret with tls.crt and tls.key
  gateway:
    servers:
      - port:
          number: 443
          protocol: HTTPS
          name: https
        hosts:
          - "*.example.com"
  virtualService:
    hosts:
      - "myapp.example.com"
    http:
      - route:
          - destination:
              host: myapp.default.svc.cluster.local
              port:
                number: 8080
```

### With External DNS

```yaml
istio-ingress:
  enabled: true
  externalDns:
    enabled: true
    annotations:
      external-dns.alpha.kubernetes.io/hostname: "myapp.example.com"
  virtualService:
    hosts:
      - "myapp.example.com"
```

### Multiple HTTP Routes

```yaml
istio-ingress:
  virtualService:
    hosts:
      - "api.example.com"
    http:
      - name: "v2-routes"
        match:
          - uri:
              prefix: "/api/v2"
        route:
          - destination:
              host: api-v2.default.svc.cluster.local
              port:
                number: 8080
      - name: "v1-routes"
        route:
          - destination:
              host: api-v1.default.svc.cluster.local
              port:
                number: 8080
```

### TLS Passthrough (SNI-based routing)

```yaml
istio-ingress:
  gateway:
    servers:
      - port:
          number: 443
          protocol: TLS
          name: tls-passthrough
        hosts:
          - "*.example.com"
  tls:
    enabled: true
    mode: PASSTHROUGH
  virtualService:
    tls:
      - match:
          - sniHosts:
              - "api.example.com"
        route:
          - destination:
              host: api.default.svc.cluster.local
              port:
                number: 8443
      - match:
          - sniHosts:
              - "web.example.com"
        route:
          - destination:
              host: web.default.svc.cluster.local
              port:
                number: 8443
```

### Complete Override

If you need full control, use the override options:

```yaml
istio-ingress:
  enabled: true
  gatewayOverride:
    apiVersion: networking.istio.io/v1beta1
    kind: Gateway
    metadata:
      name: custom-gateway
    spec:
      selector:
        app: my-custom-gateway
      servers:
        - port:
            number: 80
            protocol: HTTP
            name: http
          hosts:
            - "*"
  
  virtualServiceOverride: {}  # Or specify custom VirtualService
```

## Default Values

See [values.yaml](values.yaml) for all available configuration options.

### Key Configuration Options

| Option | Description | Default |
|--------|-------------|---------|
| `enabled` | Enable the entire subchart | `true` |
| `gateway.enabled` | Enable Gateway creation | `true` |
| `gateway.selector` | Pod selector for ingress gateway | `app: istio-ingressgateway` |
| `virtualService.enabled` | Enable VirtualService creation | `true` |
| `virtualService.hosts` | Hosts for the VirtualService | `[""]` |
| `tls.enabled` | Enable TLS configuration | `false` |
| `tls.mode` | TLS mode (SIMPLE, MUTUAL, AUTO_PASSTHROUGH, ISTIO_MUTUAL) | `SIMPLE` |
| `tls.credentialName` | Kubernetes secret name with TLS certs | `""` |
| `externalDns.enabled` | Enable external-dns annotations | `false` |
| `helpers.useLocalGateway` | Auto-link VirtualService to local gateway | `true` |

## Notes

- By default, the VirtualService will automatically reference the local Gateway if `helpers.useLocalGateway` is true
- The Gateway and VirtualService names are auto-generated based on the release name unless explicitly specified
- TLS configuration is only applied to servers with `HTTPS`, `TLS`, or `HSTS` protocol
- External DNS annotations are added to both Gateway and VirtualService metadata
