# gitops-tools

Helm library chart with reusable helpers for GitOps-aware metadata.

## Helpers

- `gitops-tools.argocd.enabled`: detects whether Argo CD metadata should be emitted
- `gitops-tools.argocd.labels`: renders Argo CD labels when enabled
- `gitops-tools.argocd.syncWave`: resolves either a named phase or an explicit numeric wave
- `gitops-tools.argocd.annotations`: merges resource annotations with Argo CD metadata when enabled

## Standard Wave Order

Use these named phases instead of ad hoc numbers:

- `foundation` => `0`
- `database` => `10`
- `supporting` => `20`
- `release` => `30`
- `ingress` => `40`

`foundation` is for secrets, PVCs, service accounts, and bootstrap config. `database` is for data stores and other stateful data-layer workloads. `supporting` is for supporting jobs or workloads that prepare dependencies for the main app. `release` is for the primary application deployment or statefulset. `ingress` is for Services, Ingresses, VirtualServices, and other traffic-routing config.

## Usage

Add it as a file dependency:

```yaml
dependencies:
  - name: gitops-tools
    version: 0.1.0
    repository: https://mbround18.github.io/helm-charts
```

Then call helpers from a chart template or helper file:

```yaml
{{- include "gitops-tools.argocd.labels" (dict "context" .) }}
{{- include "gitops-tools.argocd.annotations" (dict "context" . "phase" "ingress" "annotations" .Values.service.annotations) }}
```
