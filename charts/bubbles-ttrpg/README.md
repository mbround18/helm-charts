# Bubble System

## Description

Helm chart for the [Bubbles game system](https://github.com/mbround18/bubbles-game-system) app: a single-image
deployment (Rust/actix-web backend serving the built React frontend from one process/port) built and pushed via
`docker buildx bake --push` from the app repo's `docker-bake.hcl`. Bundles a [mongo](../mongo) subchart by default.

## Installation

1. Add the helm repo: `helm repo add mbround18 https://mbround18.github.io/helm-charts/`
2. Update your helm repos: `helm repo update`
3. Create a values file: `helm show values mbround18/bubble-system > values.yaml`
4. If `mbround18/bubble-system` is a private image, create the pull secret referenced by
   `imagePullSecrets` (defaults to `docker-credentials`):
   ```shell
   kubectl -n ${NAMESPACE} create secret docker-registry docker-credentials \
     --docker-username=<username> --docker-password=<token>
   ```
5. This chart never accepts secret values through Helm values -- create a Secret out-of-band for
   `DISCORD_CLIENT_SECRET`/`SESSION_SECRET` and point `secretEnv.<VAR>.secretName` at it:
   ```shell
   kubectl -n ${NAMESPACE} create secret generic bubble-system-secrets \
     --from-literal=DISCORD_CLIENT_SECRET=<value> --from-literal=SESSION_SECRET=<value>
   ```
   ```yaml
   secretEnv:
     DISCORD_CLIENT_SECRET:
       secretName: bubble-system-secrets
     SESSION_SECRET:
       secretName: bubble-system-secrets
   ```
   `MONGODB_URI` is wired to the bundled `mongo` subchart automatically; set
   `secretEnv.MONGODB_URI.secretName` the same way to point at an external Mongo instead.
6. Install the chart: `helm -n ${NAMESPACE} install bubble-system mbround18/bubble-system -f values.yaml`

### Testing

#### Install Testing

```shell
helm -n ${NAMESPACE} install bubble-system mbround18/bubble-system -f values.yaml --dry-run --debug
```

#### Testing its Running

```shell
helm -n ${NAMESPACE} test bubble-system
```

## Values

| Key                             | Type   | Default                            | Description                                                                                                                    |
| ------------------------------- | ------ | ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| affinity                        | object | `{}`                               |                                                                                                                                |
| autoscaling.enabled             | bool   | `false`                            |                                                                                                                                |
| env                             | object | see `values.yaml`                  | Non-sensitive app config, rendered as plain container env vars                                                                 |
| fullnameOverride                | string | `""`                               |                                                                                                                                |
| image.pullPolicy                | string | `"IfNotPresent"`                   |                                                                                                                                |
| image.repository                | string | `"mbround18/bubble-system"`        |                                                                                                                                |
| image.tag                       | string | `"latest"`                         |                                                                                                                                |
| imagePullSecrets                | list   | `[{"name": "docker-credentials"}]` | Name of a pre-existing `kubernetes.io/dockerconfigjson` Secret                                                                 |
| ingress.enabled                 | bool   | `false`                            |                                                                                                                                |
| mongo.enabled                   | bool   | `true`                             | Bundles the `mongo` subchart and wires `MONGODB_URI` to it automatically                                                       |
| nameOverride                    | string | `""`                               |                                                                                                                                |
| nodeSelector                    | object | `{}`                               |                                                                                                                                |
| podAnnotations                  | object | `{}`                               |                                                                                                                                |
| podSecurityContext.runAsNonRoot | bool   | `true`                             |                                                                                                                                |
| replicaCount                    | int    | `1`                                |                                                                                                                                |
| resources                       | object | `{}`                               |                                                                                                                                |
| secretEnv                       | object | see `values.yaml`                  | For each sensitive var: name/key of a pre-existing Secret to read via `secretKeyRef`. No secret values are ever accepted here. |
| securityContext                 | object | see `values.yaml`                  | `runAsNonRoot`, `allowPrivilegeEscalation: false`, `capabilities.drop: [ALL]`                                                  |
| service.port                    | int    | `8080`                             |                                                                                                                                |
| service.type                    | string | `"ClusterIP"`                      |                                                                                                                                |
| serviceAccount.create           | bool   | `true`                             |                                                                                                                                |
| tolerations                     | list   | `[]`                               |                                                                                                                                |
