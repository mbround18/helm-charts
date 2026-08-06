# Keygen

## Description

A Helm chart for deploying [Keygen](https://keygen.sh/docs/self-hosting/) -- a self-hosted
software licensing and distribution API -- along with its two required backing services,
PostgreSQL and Redis (bundled as the local `postgres` and `redis` charts in this repository).

The chart deploys:

- A **web** Deployment running `keygen/api web` (Puma), exposed via a Service (and optionally
  an Ingress).
- A **worker** Deployment running `keygen/api worker` (Sidekiq), enabled by default
  (`worker.enabled`).
- A pre-install/pre-upgrade **migration Job** running `keygen/api release` to apply database
  migrations before the web/worker Deployments roll out.

Keygen only reads its database and cache configuration from `DATABASE_URL`/`REDIS_URL`
connection strings, not discrete host/port/user/password env vars. Since the Postgres password
lives in a separately-managed Secret (created by the `postgres` subchart), the container command
assembles both URLs from discrete `DB_*`/`REDIS_*` env vars at startup before handing off to the
image's entrypoint (`/app/scripts/entrypoint.sh`) -- see `templates/_env.tpl`.

## Secrets

On first install this chart generates and stores Keygen's required application secrets
(`SECRET_KEY_BASE`, `ENCRYPTION_DETERMINISTIC_KEY`, `ENCRYPTION_PRIMARY_KEY`,
`ENCRYPTION_KEY_DERIVATION_SALT`) and a `KEYGEN_ACCOUNT_ID` UUID in a Secret named
`{fullname}-secrets` (override via `secrets.name`). Re-running `helm upgrade` reuses the existing
Secret instead of rotating it, so account data stays decryptable across upgrades. Set
`secrets.create=false` to bring your own pre-existing Secret with the same keys instead.

The Postgres and Redis passwords are managed by their respective subcharts; see
[postgres](../postgres/README.md) and [redis](../redis/README.md).

## Quick Start

```bash
helm repo add mbround18 https://mbround18.github.io/helm-charts/
helm repo update
helm install keygen mbround18/keygen \
  --namespace keygen --create-namespace \
  --set keygen.host=licensing.example.com \
  --set ingress.enabled=true \
  --set ingress.hosts[0].host=licensing.example.com
```

`keygen.host` must be a real, resolvable domain name -- Keygen refuses to boot with an IP
address here. Whatever reverse proxy/ingress controller terminates TLS in front of this Service
must forward `X-Forwarded-Proto`, `X-Forwarded-For`, and `X-Forwarded-Host`.

## Enterprise Edition

Set `keygen.edition=EE` and `license.enabled=true` with `license.secretName` pointing at a Secret
containing your license file (key `license.secretKey`, default `ee.lic`) to mount it at
`/etc/keygen/ee.lic`.

## Configuration

| Parameter                 | Description                                                  | Default           |
| ------------------------- | ------------------------------------------------------------ | ----------------- |
| image.repository          | Container image repository                                   | `"keygen/api"`    |
| image.tag                 | Image tag/version                                            | `"latest"`        |
| keygen.host               | Public domain name (required, never an IP)                   | `"keygen.local"`  |
| keygen.edition            | `CE` or `EE`                                                 | `"CE"`            |
| keygen.mode               | `singleplayer` or `multiplayer`                              | `"singleplayer"`  |
| keygen.accountId          | UUID used in singleplayer mode; auto-generated if empty      | `""`              |
| secrets.create            | Auto-generate SECRET_KEY_BASE/ENCRYPTION_*/KEYGEN_ACCOUNT_ID | `true`            |
| worker.enabled            | Deploy the Sidekiq worker Deployment                         | `true`            |
| worker.sidekiqConcurrency | Sidekiq thread concurrency                                   | `10`              |
| migrations.enabled        | Run `keygen/api release` as a pre-install/upgrade hook Job   | `true`            |
| license.enabled           | Mount an EE license file at `/etc/keygen`                    | `false`           |
| postgres.enabled          | Deploy the bundled `postgres` subchart                       | `true`            |
| redis.enabled             | Deploy the bundled `redis` subchart                          | `true`            |
| ingress.enabled           | Create a Kubernetes Ingress                                  | `false`           |
| service.port              | Service/container port                                       | `3000`            |
| resources                 | Web/migration CPU/memory requests/limits                     | see `values.yaml` |
| worker.resources          | Worker CPU/memory requests/limits                            | see `values.yaml` |

For full configuration options, see [values.yaml](values.yaml). For the full list of environment
variables Keygen supports (object storage, email, SSO, rate limiting, etc.), see the
[self-hosting docs](https://keygen.sh/docs/self-hosting/).
