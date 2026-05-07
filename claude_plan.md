# Production Readiness Roadmap

> **Note on CRD Alignment (Pillar 3):** The live cluster context was not provided. Items marked `[needs kubectl get crds]` require live cluster confirmation. To complete that section, share the output of:
> ```bash
> kubectl get crds -o custom-columns="NAME:.metadata.name,GROUP:.spec.group,VERSION:.spec.versions[0].name" | sort
> kubectl version --short
> ```

---

## Critical Fixes (Do These First)

### CRIT-1: Postgres init containers download `kubectl` from the internet at pod start

**Files:** `charts/postgres/templates/statefulset.yaml:34`, `charts/postgres/templates/password-sync-job.yaml:42`

Both containers run `curl -LO https://storage.googleapis.com/kubernetes-release/release/v1.29.2/bin/linux/amd64/kubectl` at startup. This is a supply-chain risk, a hard network dependency in a potentially air-gapped cluster, and pins a stale kubectl version (1.29.2 against what may be a 1.30+ server). Replace both with `bitnami/kubectl`:

```yaml
# Before (anti-pattern)
initContainers:
  - name: ensure-postgres-password-secret
    image: alpine:3.22
    command: ["sh", "-c", "apk add curl && curl -LO ...kubectl..."]

# After
initContainers:
  - name: ensure-postgres-password-secret
    image: bitnami/kubectl:1.32
    command: ["sh", "-c", "until kubectl get secret ..."]
```

The `password-sync-job` also runs `kubectl exec -i postgres-0 -- psql` which is fragile (pod name is hardcoded) and breaks in HA mode. Replace with a psql client container connecting via the Service DNS name instead.

---

### CRIT-2: `resources: {}` on 12 production workloads

Every chart without defined resources gets scheduled with no resource contract. The scheduler places them anywhere, they can consume unbounded RAM, and OOM kills produce silent failures with no budget for VPA/HPA to act on.

**Charts with `resources: {}`:** `audiobookshelf`, `enshrouded`, `forgejo`, `fvtt-dndbeyond-companion`, `keycloak`, `meilisearch`, `palworld`, `postgres`, `syncthing`, `valheim`, `vaultwarden`, `wikijs`.

Minimum baseline per workload class:

```yaml
# Web/API services (forgejo, vaultwarden, keycloak, wikijs)
resources:
  requests:
    cpu: 100m
    memory: 256Mi
  limits:
    memory: 1Gi          # no CPU limit — avoid throttling

# Databases (postgres, meilisearch)
resources:
  requests:
    cpu: 250m
    memory: 512Mi
  limits:
    memory: 2Gi

# Game servers (enshrouded, palworld, valheim)
resources:
  requests:
    cpu: 1000m
    memory: 2Gi
  limits:
    memory: 8Gi
```

---

### CRIT-3: Game server charts run as root with empty security contexts

**Files:** `charts/enshrouded/values.yaml`, `charts/palworld/values.yaml`, `charts/valheim/values.yaml`

```yaml
podSecurityContext: {}
securityContext: {}
```

All three Steam-based servers run as UID 1000 inside their images — there is no reason to leave these unconstrained at the K8s level. The values.yaml comments even show the correct values but leave them commented out. Uncomment and set:

```yaml
podSecurityContext:
  fsGroup: 1000
  fsGroupChangePolicy: OnRootMismatch

securityContext:
  runAsNonRoot: true
  runAsUser: 1000
  runAsGroup: 1000
  allowPrivilegeEscalation: false
  capabilities:
    drop: [ALL]
```

---

### CRIT-4: Hardcoded namespace in `meilisearch` helpers

**File:** `charts/meilisearch/templates/_helpers.tpl:60,70`

```
host: meilisearch.default.svc.cluster.local
```

This hardcodes the `default` namespace. If meilisearch is deployed to any other namespace (including as a subchart of `wikijs`), service discovery silently resolves to the wrong address or returns DNS NXDOMAIN. Fix:

```
host: {{ printf "%s.%s.svc.cluster.local" (include "meilisearch.fullname" .) .Release.Namespace }}
```

---

### CRIT-5: `pvc-watcher` has a broken template directory

**File:** `charts/pvc-watcher/templates/service-acccount` (a directory, not a `.yaml` file; also a typo)

`helm template` silently skips directories under `templates/`, so no ServiceAccount is generated for this chart. Rename to `serviceaccount.yaml` and add the template content.

---

### CRIT-6: `postgres` StatefulSet uses hardcoded labels, not release-scoped helpers

**File:** `charts/postgres/templates/statefulset.yaml`

```yaml
metadata:
  name: postgres        # hardcoded
  labels:
    app: postgres       # hardcoded, non-standard
```

Two postgres releases in the same namespace would collide, and ArgoCD diff tracking breaks because the resource name doesn't correlate to the Helm release. The chart has no `_helpers.tpl` at all. Add one and use `{{ include "postgres.fullname" . }}` throughout.

---

## Pillar 1: Library & Subchart Extraction

### Current State

`gitops-tools` handles ArgoCD wave annotations. `game-tools` provides a NodePort service template used only by `vein`. The `_helpers.tpl` in every chart contains the same 6 functions copy-pasted with only the chart name substituted — approximately **900 lines of pure duplication** across 15 charts.

### What to Extract into `gitops-tools`

The library is already a dependency of nearly every chart. Expand it to eliminate the boilerplate via a `_common.tpl` addition:

```
gitops-tools.common.name           → {{ default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
gitops-tools.common.fullname       → standard release-name/chart-name fusion logic
gitops-tools.common.chart          → chart name+version label value
gitops-tools.common.labels         → helm.sh/chart + selectorLabels + version + managed-by + argocd labels
gitops-tools.common.selectorLabels → app.kubernetes.io/name + instance
gitops-tools.common.serviceAccountName → standard SA name resolution
```

Usage in consuming charts shrinks `_helpers.tpl` to 3 lines:

```yaml
{{- define "forgejo.fullname" -}}{{- include "gitops-tools.common.fullname" . -}}{{- end -}}
{{- define "forgejo.labels"   -}}{{- include "gitops-tools.common.labels"   . -}}{{- end -}}
{{- define "forgejo.selectorLabels" -}}{{- include "gitops-tools.common.selectorLabels" . -}}{{- end -}}
```

### Backup Sidecar Partial

`audiobookshelf`, `enshrouded`, `palworld`, `foundryvtt` all define an identical backup-cron sidecar container block. Extract to:

```
gitops-tools.backup.sidecar  → renders the mbround18/backup-cron container spec from a standardized values block
```

Standard values shape (adopt across all charts):

```yaml
backups:
  enabled: false
  image: mbround18/backup-cron:v1.0.0
  schedule: "0 3 * * *"
  retainNDays: "7"
  retainNFiles: "10"
  inputPath: ""       # chart sets this per workload
  outputPath: "/backups"
```

### What to Expand in `game-tools`

`game-tools` is currently used only by `vein`. `enshrouded`, `palworld`, `valheim`, `hytale` all share the same patterns (steam-based image, UDP/TCP NodePort, single PVC for save data, backup sidecar) but don't use it. Add to `game-tools`:

```
game-tools.pvc.savedata          → single-PVC pattern for game save data
game-tools.securityContext.steam → standard steam UID 1000 security context block
game-tools.probe.gameserver      → TCP socket liveness probe on named game port
```

Then add `game-tools` as a dependency to `enshrouded`, `palworld`, `valheim`, `hytale`.

### Repository Strategy: Keep the Private Helm Repo

The `file://` references in `grafana`, `keycloak`, and `openobserve` are a local development convenience but should not be the published form — they work for `make test` locally but fail in any environment that installs the chart from the remote repo. The convention should be:

- `file://` refs are acceptable in unreleased/in-progress charts during development
- Before merging, convert to version-pinned remote refs (`https://mbround18.github.io/helm-charts`)
- `make deps-update` is the gate that enforces this before tests run

---

## Pillar 2: Feature-Flagging & Environment Isolation

### Current Problem: Three Conflicting Ingress Models

| Chart | Plain Ingress | Standalone VS/GW templates | `istio-ingress` subchart | Conflict risk |
|---|---|---|---|---|
| `foundryvtt` | yes | yes (guarded) | yes (condition) | Low — has mutual-exclusion guard |
| `meilisearch` | yes | yes (via merge helper) | yes (condition) | Medium — merge helper runs regardless |
| `vaultwarden` | yes | yes (**always rendered**) | no | **High — both always rendered** |
| `wikijs` | yes | yes (via merge helper) | yes (condition) | Medium |

`vaultwarden` is the immediate problem: `virtualservice.yaml` has no `if` guard, so deploying to a cluster without Istio either fails (missing CRD) or creates a broken resource.

Storage class has the same problem: `enshrouded`, `palworld`, `hytale` default to `longhorn` inside the template itself (not in `values.yaml`), making overrides non-obvious.

### Proposed Feature-Flag Schema

Add a top-level `cluster` block to every chart's `values.yaml`:

```yaml
# ── Cluster capability flags ─────────────────────────────────────────
# Set these to match what is installed in your cluster.
cluster:
  istio:
    enabled: false          # renders VirtualService/Gateway, suppresses plain Ingress
  longhorn:
    enabled: false          # sets PVC storageClassName to longhorn
    staticVolumes: false    # uses longhorn-static for pre-provisioned PVs
  externalSecrets:
    enabled: false          # renders ExternalSecret instead of K8s Secret
    secretStore: ""         # name of the ClusterSecretStore
    secretStoreKind: ClusterSecretStore

# ── Ingress (only active when cluster.istio.enabled=false) ───────────
ingress:
  enabled: false
  className: nginx
  annotations: {}
  hosts: []
  tls: []

# ── Istio ingress (only active when cluster.istio.enabled=true) ──────
istio-ingress:
  enabled: false            # set to true via cluster.istio.enabled in ArgoCD values
  virtualService:
    hosts: []
```

Guard all inline VirtualService/Gateway templates:

```yaml
{{- if index .Values "cluster" "istio" "enabled" }}
```

For storage classes, replace hardcoded defaults in templates with:

```yaml
storageClassName: {{ .Values.cluster.longhorn.enabled | ternary "longhorn" (.Values.persistence.storageClassName | default "") }}
```

### Environment Profile Files

Create a `values/` directory per chart for the three tiers:

```
charts/forgejo/
  values.yaml           # base — no cluster-specific settings
  values/
    dev.yaml            # cluster.istio.enabled=false, resources reduced
    staging.yaml        # cluster.istio.enabled=true, resources at 75%
    prod.yaml           # cluster.istio.enabled=true, cluster.longhorn.enabled=true,
                        # externalSecrets.enabled=true, full resource limits
```

ArgoCD Application then uses:

```yaml
helm:
  valueFiles:
    - values.yaml
    - values/prod.yaml
```

---

## Pillar 3: K8s Optimization & CRD Alignment

*(Items marked `[needs kubectl get crds]` require live cluster confirmation)*

### Istio: Gateway/VS Present — Security Layer Missing

The `istio-ingress` subchart is well-designed. What's absent is the layer that makes Istio worth running:

**`DestinationRule` — not present in any chart.** Without it, connections to services use passthrough with no circuit-breaking, no outlier detection, and no connection pool limits. Minimum for stateful services:

```yaml
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: {{ include "forgejo.fullname" . }}
spec:
  host: {{ include "forgejo.fullname" . }}.{{ .Release.Namespace }}.svc.cluster.local
  trafficPolicy:
    connectionPool:
      http:
        h2UpgradePolicy: UPGRADE
    outlierDetection:
      consecutiveGatewayErrors: 5
      interval: 10s
      baseEjectionTime: 30s
```

Add `destinationrule.yaml` to: `forgejo`, `vaultwarden`, `keycloak`, `meilisearch`, `wikijs`, `openobserve`.

**`PeerAuthentication` — not present. `[needs kubectl get crds]`** If the mesh runs in `PERMISSIVE` mode (Istio default), services that should only accept mesh traffic still accept cleartext. Add per-workload PeerAuthentication:

```yaml
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: {{ include "X.fullname" . }}
spec:
  selector:
    matchLabels:
      {{- include "X.selectorLabels" . | nindent 6 }}
  mtls:
    mode: STRICT
```

**`AuthorizationPolicy`** — only `grafana` has one. `forgejo`, `vaultwarden`, and `keycloak` are high-value targets that should restrict ingress to known sources.

### Longhorn: PVCs Under-utilizing the Feature Set `[needs kubectl get crds]`

If `longhorn.io/v1beta2` CRDs are present, add annotations to PVC templates:

```yaml
annotations:
  {{- if .Values.cluster.longhorn.enabled }}
  longhorn.io/number-of-replicas: "2"     # 3 for prod
  longhorn.io/data-locality: "best-effort"
  {{- end }}
```

`vaultwarden` uses `storageClassName: longhorn-static` (pre-provisioned volume). If the PV is deleted, the PVC hangs in `Pending` forever — a data-loss scenario for a password manager. Switch to dynamic provisioning with a `VolumeSnapshotClass`-backed backup, or document the manual recovery procedure.

### ServiceMonitor Coverage Gap `[needs kubectl get crds]`

`openobserve`, `opentelemetry-collector`, and `grafana` have `ServiceMonitor`. Missing from:

| Chart | Metrics endpoint |
|---|---|
| `postgres` | `postgres_exporter` sidecar needed |
| `meilisearch` | `/metrics` built-in |
| `keycloak` | port `management` (9000), `KC_METRICS_ENABLED=true` already set |
| `forgejo` | `/metrics` built-in |

### ExternalSecret CRD `[needs kubectl get crds]`

`forgejo` and `openobserve` have `ExternalSecret` templates. `keycloak`, `postgres`, `meilisearch`, `syncthing`, and `vaultwarden` generate `Secret` resources from plaintext values. If `external-secrets.io/v1beta1` is installed, all secret-generating charts should offer the `externalSecrets.enabled` path. The pattern is already proven in `forgejo` — replicate it.

---

## Pillar 4: Reliability & Security

### Full Chart Audit Matrix

| Chart | Resources | HPA | PDB | Health Probes | SecurityContext | NetworkPolicy |
|---|---|---|---|---|---|---|
| `audiobookshelf` | empty | no | no | yes | partial (no runAsNonRoot) | no |
| `enshrouded` | empty | no | no | **no** | **empty** | no |
| `forgejo` | empty | yes (disabled) | no | yes | yes | no |
| `foundryvtt` | set | no | yes (disabled) | yes | yes | no |
| `fvtt-dndbeyond-companion` | empty | no | no | no | no | no |
| `hytale` | partial (no requests) | no | no | yes | yes | no |
| `keycloak` | empty | no | no | yes | yes | no |
| `meilisearch` | empty | no | no | yes | no | no |
| `openobserve` | partial (limits only) | no | no | yes | **empty** | no |
| `opentelemetry-collector` | **set** | no | no | **yes** | **yes** | **yes** |
| `palworld` | empty | no | no | **no** | **empty** | no |
| `postgres` | empty | n/a | no | yes | root init container | no |
| `pvc-watcher` | set (requests) | no | no | no | no | no |
| `syncthing` | empty | no | no | yes | partial | no |
| `valheim` | empty | no | no | **no** | **empty** | no |
| `vaultwarden` | empty | no | no | yes | yes | no |
| `vein` | set | no | no | yes | yes | no |
| `wikijs` | empty | no | no | yes | no | no |

`opentelemetry-collector` is the only chart with all pillars satisfied. Use it as the internal template.

### PDB: Add to All Stateful/Critical Services

Only `foundryvtt` has a PDB (disabled by default). Add to `postgres`, `meilisearch`, `forgejo`, `vaultwarden`, `keycloak`, `openobserve`:

```yaml
{{- if .Values.pdb.enabled }}
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: {{ include "X.fullname" . }}
spec:
  minAvailable: {{ .Values.pdb.minAvailable | default 1 }}
  selector:
    matchLabels:
      {{- include "X.selectorLabels" . | nindent 6 }}
{{- end }}
```

Default values addition for each chart:

```yaml
pdb:
  enabled: false
  minAvailable: 1
```

### Health Probes: Game Servers

`enshrouded`, `palworld`, `valheim` have no probes. Use TCP socket probes on the game port:

```yaml
livenessProbe:
  tcpSocket:
    port: game
  initialDelaySeconds: 120    # steam games take time to init
  periodSeconds: 30
  failureThreshold: 3
readinessProbe:
  tcpSocket:
    port: game
  initialDelaySeconds: 90
  periodSeconds: 10
```

### `postgres` Password-Sync Job Uses `serviceAccountName: default`

**File:** `charts/postgres/templates/password-sync-job.yaml`

The default service account should not have `kubectl exec` privileges. The job relies on whatever RBAC happens to be bound to `default`. Give it the explicit named SA that `secret-rbac.yaml` already creates:

```yaml
serviceAccountName: {{ include "postgres.serviceAccountName" . }}
```

### `audiobookshelf` Container-Level Security Context Missing

`podSecurityContext` sets `fsGroup: 1000` correctly, but the container-level `securityContext` block is absent from the statefulset template — only `podSecurityContext` is referenced. Add to `charts/audiobookshelf/templates/statefulset.yaml`:

```yaml
securityContext:
  runAsNonRoot: true
  runAsUser: 1000
  runAsGroup: 1000
  allowPrivilegeEscalation: false
  capabilities:
    drop: [ALL]
```

---

## Prioritized Execution Plan

### Week 1 — Stop the Bleeding (Critical Fixes)

- [ ] CRIT-1: Replace kubectl-downloading init containers in `postgres` with `bitnami/kubectl`
- [ ] CRIT-2: Add `resources` to `postgres`, `keycloak`, `vaultwarden` (highest-risk services first)
- [ ] CRIT-3: Set security contexts on `enshrouded`, `palworld`, `valheim`
- [ ] CRIT-4: Fix hardcoded `default` namespace in meilisearch helpers
- [ ] CRIT-5: Fix `pvc-watcher/templates/service-acccount` → `serviceaccount.yaml`
- [ ] CRIT-6: Add `postgres/_helpers.tpl`, replace hardcoded labels with release-scoped helpers

### Week 2 — Structural Reliability

- [ ] Add PDB templates to `postgres`, `forgejo`, `vaultwarden`, `keycloak`
- [ ] Add TCP socket probes to `enshrouded`, `palworld`, `valheim`
- [ ] Guard `vaultwarden/templates/virtualservice.yaml` with `cluster.istio.enabled` flag
- [ ] Add `resources` to remaining 9 empty-resources charts
- [ ] Add HPA to `vaultwarden`, `keycloak`, `wikijs` (disabled by default, values wired)
- [ ] Fix `postgres` password-sync job `serviceAccountName: default` → named SA

### Week 3 — Library Extraction

- [ ] Add `gitops-tools.common.*` helpers (fullname, labels, selectorLabels, serviceAccountName)
- [ ] Migrate 5 charts to new common helpers to validate the interface
- [ ] Add `gitops-tools.backup.sidecar` partial
- [ ] Add `game-tools` dependency to `enshrouded`, `palworld`, `valheim`, `hytale`
- [ ] Convert `grafana`, `keycloak`, `openobserve` `file://` deps to versioned remote refs

### Week 4 — Environment Isolation

- [ ] Add `cluster` feature-flag block to all charts' `values.yaml`
- [ ] Create `values/dev.yaml`, `values/staging.yaml`, `values/prod.yaml` for `forgejo`, `vaultwarden`, `keycloak` as pilot
- [ ] Add `ExternalSecret` path to `keycloak`, `postgres`, `meilisearch`
- [ ] Fix storage class defaults — replace hardcoded `longhorn` in templates with `cluster.longhorn.enabled` ternary

### Ongoing (After CRD Inventory)

- [ ] Add `DestinationRule` templates to Istio-enabled charts
- [ ] Add `PeerAuthentication` + `AuthorizationPolicy` for `forgejo`, `vaultwarden`, `keycloak`
- [ ] Add `ServiceMonitor` to `postgres`, `meilisearch`, `keycloak`, `forgejo`
- [ ] Add Longhorn replica annotations to PVC templates
- [ ] Add Prometheus exporter sidecar to `postgres`
