# Nextcloud Helm chart

Deploys Nextcloud (`nextcloud:production-apache`) with a bundled MySQL 9 database, matching the
raw-manifest deployment this chart is intended to replace 1:1 so it can be migrated in-place onto
Argo CD without losing data.

## Why the resource names are hardcoded

The `nextcloud` and `mysql` StatefulSets (and their `volumeClaimTemplates`) are named exactly
`nextcloud` and `mysql` rather than derived from the Helm release name. Kubernetes binds a
StatefulSet's generated PVC (`<template>-<statefulset>-<ordinal>`) to any existing PVC of the same
name in the namespace, so keeping these names identical to the previous raw manifests means the
existing Longhorn volumes (`nextcloud-storage-nextcloud-0`, `mysql-storage-mysql-0`) are reused
instead of orphaned.

## Quick install (Helm)

```bash
helm upgrade --install nextcloud ./charts/nextcloud --namespace nextcloud
```

## Secrets

This chart does not create `mysql-secret` or `nextcloud-secret` — they must already exist in the
target namespace (as they did under the previous deployment). Configure their names via
`secrets.mysql.name` / `secrets.nextcloud.name` if they differ.

Expected keys:

- `mysql-secret`: `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_ROOT_PASSWORD`
- `nextcloud-secret`: `NEXTCLOUD_ADMIN_PASSWORD`

## Argo CD

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: nextcloud
  namespace: argocd
spec:
  project: default
  source:
    repoURL: git@github.com:mbround18/helm-charts.git
    path: charts/nextcloud
    targetRevision: main
    helm:
      valueFiles:
        - values.argo.yaml
  destination:
    server: https://kubernetes.default.svc
    namespace: nextcloud
  syncPolicy:
    automated:
      selfHeal: true
    syncOptions:
      - CreateNamespace=false
```

`CreateNamespace=false` and no `prune: true` are intentional for the first sync — the namespace and
PVCs already exist from the previous deployment; verify the diff before enabling prune.

For full configuration options see [values.yaml](values.yaml).
