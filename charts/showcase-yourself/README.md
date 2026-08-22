# Showcase Yourself

## Description

Helm chart for [showcase-yourself](https://github.com/mbround18/showcase-yourself): a React/Vite portfolio
frontend and an Actix backend, deployed as two separate Deployments/Services (`mbround18/showcase-yourself-frontend`
and `mbround18/showcase-yourself-backend`). The backend owns Mongo, sessions, CSRF, and a generic OIDC auth flow
gating an owner-only admin portal for contact submissions. Bundles a [mongo](../mongo) subchart by default. The
app repo's own `ingress/` (a local nginx reverse proxy for `docker compose`) is not published as an image or used
here -- this chart's own `Ingress` resource does that job in-cluster instead.

## Installation

1. Add the helm repo: `helm repo add mbround18 https://mbround18.github.io/helm-charts/`
2. Update your helm repos: `helm repo update`
3. Create a values file: `helm show values mbround18/showcase-yourself > values.yaml`
4. If `mbround18/showcase-yourself-*` are private images, create the pull secret referenced by
   `imagePullSecrets` (defaults to `docker-credentials`):
   ```shell
   kubectl -n ${NAMESPACE} create secret docker-registry docker-credentials \
     --docker-username=<username> --docker-password=<token>
   ```
5. Set `backend.env.OWNER_EMAIL_ADDRESS`, `OIDC_ISSUER_URL`, `OIDC_CLIENT_ID`, `OIDC_REDIRECT_URL`, and
   `FRONTEND_URL` -- sign-in doesn't work without them. See `values.yaml` for what each does; the backend speaks
   generic OIDC, so any compliant provider works, config-only.
6. This chart never accepts secret values through Helm values -- create a Secret out-of-band for
   `OIDC_CLIENT_SECRET`/`SESSION_SECRET` and point `backend.secretEnv.<VAR>.secretName` at it:
   ```shell
   kubectl -n ${NAMESPACE} create secret generic showcase-yourself-secrets \
     --from-literal=OIDC_CLIENT_SECRET=<value> --from-literal=SESSION_SECRET=<value>
   ```
   ```yaml
   backend:
     secretEnv:
       OIDC_CLIENT_SECRET:
         secretName: showcase-yourself-secrets
       SESSION_SECRET:
         secretName: showcase-yourself-secrets
   ```
   `DATABASE_URL` is wired to the bundled `mongo` subchart automatically; set
   `backend.secretEnv.DATABASE_URL.secretName` the same way to point at an external Mongo instead.
7. Install the chart: `helm -n ${NAMESPACE} install showcase mbround18/showcase-yourself -f values.yaml`

### Testing

#### Install Testing

```shell
helm -n ${NAMESPACE} install showcase mbround18/showcase-yourself -f values.yaml --dry-run --debug
```

#### Testing its Running

```shell
helm -n ${NAMESPACE} test showcase
```

## Values

| Key                             | Type   | Default                                  | Description                                                                                                                    |
| ------------------------------- | ------ | ---------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| affinity                        | object | `{}`                                     |                                                                                                                                |
| backend.env                     | object | see `values.yaml`                        | Non-sensitive app config, rendered as plain container env vars                                                                 |
| backend.image.repository        | string | `"mbround18/showcase-yourself-backend"`  |                                                                                                                                |
| backend.image.tag               | string | `"latest"`                               |                                                                                                                                |
| backend.replicaCount            | int    | `1`                                      |                                                                                                                                |
| backend.secretEnv               | object | see `values.yaml`                        | For each sensitive var: name/key of a pre-existing Secret to read via `secretKeyRef`. No secret values are ever accepted here. |
| backend.service.port            | int    | `8080`                                   |                                                                                                                                |
| frontend.image.repository       | string | `"mbround18/showcase-yourself-frontend"` |                                                                                                                                |
| frontend.image.tag              | string | `"latest"`                               |                                                                                                                                |
| frontend.replicaCount           | int    | `1`                                      |                                                                                                                                |
| frontend.service.port           | int    | `8080`                                   |                                                                                                                                |
| fullnameOverride                | string | `""`                                     |                                                                                                                                |
| imagePullSecrets                | list   | `[{"name": "docker-credentials"}]`       | Name of a pre-existing `kubernetes.io/dockerconfigjson` Secret                                                                 |
| ingress.enabled                 | bool   | `false`                                  | Single Ingress path-routing `/` to the frontend and `/api` to the backend                                                      |
| mongo.enabled                   | bool   | `true`                                   | Bundles the `mongo` subchart and wires `DATABASE_URL` to it automatically                                                      |
| nameOverride                    | string | `""`                                     |                                                                                                                                |
| nodeSelector                    | object | `{}`                                     |                                                                                                                                |
| podSecurityContext.runAsNonRoot | bool   | `true`                                   |                                                                                                                                |
| securityContext                 | object | see `values.yaml`                        | `runAsNonRoot`, `allowPrivilegeEscalation: false`, `capabilities.drop: [ALL]`                                                  |
| serviceAccount.create           | bool   | `true`                                   |                                                                                                                                |
| tolerations                     | list   | `[]`                                     |                                                                                                                                |
