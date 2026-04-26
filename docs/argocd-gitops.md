# Argo CD GitOps Wave Order

This repository uses a single Argo CD sync-wave contract so dependent charts land in a predictable order during sync.

## Wave Model

| Phase        | Wave | Use for                                                                        |
| ------------ | ---: | ------------------------------------------------------------------------------ |
| `foundation` |  `0` | Secrets, PVCs, service accounts, bootstrap ConfigMaps, and other prerequisites |
| `database`   | `10` | Databases and other stateful data-layer workloads                              |
| `supporting` | `20` | Supporting jobs or workloads that prepare dependencies for the main app        |
| `release`    | `30` | The primary application Deployment or StatefulSet                              |
| `ingress`    | `40` | Services, Ingresses, VirtualServices, and other traffic-routing config         |

This ordering matches how integrated charts in this repo depend on each other:

- foundation objects must exist before workloads can start
- database workloads must be available before dependent release apps initialize
- supporting jobs run after their dependency is up but before the main release depends on their output
- release workloads come after their dependencies
- ingress and traffic-routing config apply last

## Helper Usage

Charts that depend on `gitops-tools` should use named phases instead of hard-coded numbers:

```yaml
{{- include "gitops-tools.argocd.annotations" (dict "context" . "phase" "foundation" "annotations" .Values.serviceAccount.annotations) }}
{{- include "gitops-tools.argocd.annotations" (dict "context" . "phase" "release") }}
{{- include "gitops-tools.argocd.annotations" (dict "context" . "phase" "ingress" "annotations" .Values.service.annotations) }}
```

If a chart does not yet use `gitops-tools`, keep the same numeric wave values so the phase contract still holds.

## Current Conventions

- `postgres` StatefulSet is `database` and its password sync job is `supporting`
- `meilisearch` StatefulSet is `database`, its provisioning ConfigMap is `foundation`, and its provisioning job is `supporting`
- `wikijs`, `vaultwarden`, and `vein` primary workloads are `release`
- Services, Ingresses, and VirtualServices for release charts are `ingress`

## Operational Notes

- Use `make deps-update` only when changing dependency versions or refreshing `Chart.lock`
- Normal `make dump`, `make test`, and `make build` use committed lockfiles and do not refresh Helm repos
- When adding a new chart integration, assign the resource to one of the five phases above instead of inventing a new wave number
