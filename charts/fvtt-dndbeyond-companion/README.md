# FoundryVTT - D&D Beyond - Companion

## Description

Installs the companion for the module [D&D Beyond Rolls Module](https://github.com/mbround18/foundry-dnd-beyond-rolls-module)

## Installation

1. Install the module through the Foundry VTT Module Manager
2. Add the helm repo: `helm repo add mbround18 https://mbround18.github.io/helm-charts/`
3. Update your helm repos: `helm repo update`
4. Create a values file: `helm show values mbround18/fvtt-dndbeyond-companion > values.yaml`
5. Edit the values file to your liking
6. Install the chart: `helm -n ${NAMESPACE} install beyond-companion mbround18/fvtt-dndbeyond-companion -f values.yaml`
7. Configure the module with the URL from the helm values file

### Testing

#### Install Testing

```shell
helm -n ${NAMESPACE} install beyond-companion mbround18/fvtt-dndbeyond-companion -f values.yaml --dry-run --debug
```

#### Testing its Running

```shell
helm -n ${NAMESPACE} test beyond-companion
```

## Values

| Key                                | Type   | Default                                | Description |
| ---------------------------------- | ------ | -------------------------------------- | ----------- |
| affinity                           | object | `{}`                                   |             |
| fullnameOverride                   | string | `""`                                   |             |
| image.pullPolicy                   | string | `"IfNotPresent"`                       |             |
| image.repository                   | string | `"mbround18/fvtt-dndbeyond-companion"` |             |
| image.tag                          | string | `"latest"`                             |             |
| imagePullSecrets                   | list   | `[]`                                   |             |
| ingress.annotations                | object | `{}`                                   |             |
| ingress.enabled                    | bool   | `false`                                |             |
| ingress.hosts[0].host              | string | `"chart-example.local"`                |             |
| ingress.hosts[0].paths[0].path     | string | `"/"`                                  |             |
| ingress.hosts[0].paths[0].pathType | string | `"ImplementationSpecific"`             |             |
| ingress.tls                        | list   | `[]`                                   |             |
| nameOverride                       | string | `""`                                   |             |
| nodeSelector                       | object | `{}`                                   |             |
| podAnnotations                     | object | `{}`                                   |             |
| podSecurityContext                 | object | `{}`                                   |             |
| replicaCount                       | int    | `1`                                    |             |
| resources                          | object | `{}`                                   |             |
| securityContext                    | object | `{}`                                   |             |
| service.port                       | int    | `3000`                                 |             |
| service.type                       | string | `"ClusterIP"`                          |             |
| serviceAccount.annotations         | object | `{}`                                   |             |
| serviceAccount.create              | bool   | `true`                                 |             |
| serviceAccount.name                | string | `nil`                                  |             |
| tolerations                        | list   | `[]`                                   |             |
