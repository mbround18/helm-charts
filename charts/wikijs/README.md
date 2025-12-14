# Wiki.js Helm Chart

Deploy Wiki.js with optional Meilisearch and Postgres dependencies, plus first-class Istio ingress support via the `istio-ingress` subchart.

## Features

- Wiki.js 2.5.x deployment with HA probe defaults
- Optional Meilisearch dependency (off by default) with module copy/init
- Bundled Postgres subchart with persistence and SCRAM auth
- Istio ingress powered by `istio-ingress` subchart; K8s Ingress supported separately
- Init containers to wait for Postgres (and Meilisearch when enabled)

## Quickstart

```bash
# From repo root
helm dependency update charts/wikijs
helm install wikijs charts/wikijs \
  --set ingress.enabled=true \
  --set ingress.hosts[0]=wiki.example.com
```

## Values

Key toggles (see values.yaml for full list):

- `ingress.enabled`: enable Kubernetes Ingress (non-Istio)
- `ingress.hosts[]`: hostnames for the Ingress
- `istio-ingress.enabled`: enable Istio Gateway/VirtualService via subchart
- `istio-ingress.virtualService.hosts[]`: hosts for Istio
- `service.port`: Wiki.js service port (default 3000)
- `resources`: Pod requests/limits for Wiki.js

### Meilisearch (optional)

Meilisearch is wired as a dependency but disabled by default. Uncomment or set `meilisearch.enabled=true` to bundle it. Wiki.js init copies the Meilisearch search module and waits for readiness.

Example:

```yaml
meilisearch:
  enabled: true
  auth:
    masterKeySecret: meilisearch-master-key
  provisioning:
    enabled: true
    indexSecret: meilisearch-wikijs-data
istio-ingress:
  enabled: true
  virtualService:
    hosts: ["wiki.example.com"]
```

If you already run Meilisearch elsewhere, keep `meilisearch.enabled=false` and override `MEILISEARCH_URL` via extra env (edit templates to suit your external endpoint).

### Postgres

The bundled Postgres subchart is on by default.

- `postgres.enabled`: keep true unless using an external DB
- `postgres.persistence.*`: PVC size/class controls
- `postgres.postgresql.passwordSecret`: secret containing `POSTGRES_PASSWORD`

If using an external DB, set `postgres.enabled=false` and override DB env via values or a ConfigMap/Secret; ensure the `wait-for-database` init still points to your host/port/user/db.

### Istio vs. Kubernetes Ingress

- **Kubernetes Ingress**: `ingress.enabled=true`; uses `templates/ingress.yaml`
- **Istio**: `istio-ingress.enabled=true`; routes are assembled in `templates/00-merge-istio-routes.yaml` and rendered by the `istio-ingress` subchart. No duplicate YAML needed.

## Important Notes

- Init containers install the Meilisearch module and wait on dependencies; ensure referenced secrets exist (`meilisearch.auth.masterKeySecret`, `meilisearch.provisioning.indexSecret`, `postgres.postgresql.passwordSecret`).
- Persistence: Wiki.js uses in-Pod storage for app data; DB and search persistence are managed by their subcharts.
- If enabling TLS on Istio, configure `istio-ingress.tls.*` per the subchart.

## Testing

From repo root:

```bash
make test   # dumps + validates all charts
helm template wikijs charts/wikijs  # render only this chart
```

## Examples

### 1) Kubernetes Ingress + bundled Postgres (no Meilisearch)

```yaml
ingress:
  enabled: true
  hosts:
    - wiki.example.com
postgres:
  enabled: true
meilisearch:
  enabled: false
```

### 2) Istio + Meilisearch + TLS on Gateway

```yaml
meilisearch:
  enabled: true
  auth:
    masterKeySecret: meilisearch-master-key
  provisioning:
    enabled: true
    indexSecret: meilisearch-wikijs-data

istio-ingress:
  enabled: true
  virtualService:
    hosts:
      - wiki.example.com
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
      - port:
          number: 443
          protocol: HTTPS
          name: https
        hosts:
          - "*"
        tls:
          mode: SIMPLE
          credentialName: wikijs-tls
```

### 3) External Postgres + External Meilisearch

```yaml
postgres:
  enabled: false
meilisearch:
  enabled: false

# Provide env overrides via extraEnv (patch templates if needed):
# env:
#   - name: DB_HOST
#     value: external-db.example.com
#   - name: MEILISEARCH_URL
#     value: https://search.example.com
```
