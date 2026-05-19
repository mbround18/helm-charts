#!/usr/bin/env python3
"""Generate an agentskills.io-compliant skill for the mbround18 helm-charts repo.

Reads all charts, extracts metadata and values shapes, fetches live CRD schemas
from the cluster (ArgoCD, FluxCD, Istio), then writes skills/charts/.

Usage:
    uv run scripts/generate-charts-skill.py
    python3 scripts/generate-charts-skill.py
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent.parent
CHARTS_DIR = REPO_ROOT / "charts"
SKILL_DIR = REPO_ROOT / "skills" / "charts"
HELM_REPO = "https://mbround18.github.io/helm-charts"
REPO_URL = "https://github.com/mbround18/helm-charts"

# CRDs we want to capture for install-method documentation
RELEVANT_CRDS = {
    "argocd-application": "applications.argoproj.io",
    "fluxcd-helmrelease": "helmreleases.helm.toolkit.fluxcd.io",
    "fluxcd-helmrepository": "helmrepositories.source.toolkit.fluxcd.io",
    "istio-gateway": "gateways.networking.istio.io",
    "istio-virtualservice": "virtualservices.networking.istio.io",
}

# Preferred version per CRD
CRD_PREFERRED_VERSION = {
    "applications.argoproj.io": "v1alpha1",
    "helmreleases.helm.toolkit.fluxcd.io": "v2",
    "helmrepositories.source.toolkit.fluxcd.io": "v1",
    "gateways.networking.istio.io": "v1",
    "virtualservices.networking.istio.io": "v1",
}


def run(cmd: list[str], check=True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def kubectl_crd_schema(crd_name: str, preferred_version: str) -> dict:
    """Return the spec OpenAPIV3Schema for the given CRD and version, or {}."""
    result = run(["kubectl", "get", "crd", crd_name, "-o", "json"], check=False)
    if result.returncode != 0:
        return {}
    data = json.loads(result.stdout)
    versions = data.get("spec", {}).get("versions", [])
    # Prefer the requested version, then fall back to first served version
    target = None
    for v in versions:
        if v["name"] == preferred_version and v.get("served", True):
            target = v
            break
    if target is None:
        for v in versions:
            if v.get("served", True):
                target = v
                break
    if target is None:
        return {}
    schema = target.get("schema", {}).get("openAPIV3Schema", {})
    spec = schema.get("properties", {}).get("spec", {})
    return {
        "crd": crd_name,
        "version": target["name"],
        "group": data["spec"]["group"],
        "scope": data["spec"]["scope"],
        "spec": spec,
    }


def load_chart(chart_dir: Path) -> dict | None:
    chart_yaml = chart_dir / "Chart.yaml"
    values_yaml = chart_dir / "values.yaml"
    if not chart_yaml.exists():
        return None
    with chart_yaml.open() as f:
        chart = yaml.safe_load(f)
    values = {}
    if values_yaml.exists():
        with values_yaml.open() as f:
            values = yaml.safe_load(f) or {}
    deps = chart.get("dependencies", [])
    return {
        "name": chart.get("name", chart_dir.name),
        "description": chart.get("description", ""),
        "version": chart.get("version", ""),
        "appVersion": chart.get("appVersion", ""),
        "type": chart.get("type", "application"),
        "keywords": chart.get("keywords", []),
        "home": chart.get("home", ""),
        "sources": chart.get("sources", []),
        "dependencies": [
            {
                "name": d.get("name"),
                "version": d.get("version"),
                "repository": d.get("repository"),
                "condition": d.get("condition"),
                "alias": d.get("alias"),
            }
            for d in deps
        ],
        "values": values,
    }


def flatten_values_keys(values: dict, prefix: str = "") -> list[dict]:
    """Walk values dict and emit top-level + one-level-deep keys with types."""
    items = []
    for k, v in values.items():
        path = f"{prefix}{k}" if not prefix else f"{prefix}.{k}"
        typ = type(v).__name__ if v is not None else "null"
        if isinstance(v, dict) and not prefix:
            items.append({"key": path, "type": "object", "default": None})
            for sk, sv in v.items():
                styp = type(sv).__name__ if sv is not None else "null"
                items.append(
                    {
                        "key": f"{path}.{sk}",
                        "type": styp,
                        "default": sv if not isinstance(sv, (dict, list)) else None,
                    }
                )
        else:
            items.append(
                {
                    "key": path,
                    "type": typ,
                    "default": v if not isinstance(v, (dict, list)) else None,
                }
            )
    return items


def build_charts_json(charts: list[dict]) -> dict:
    out = {}
    for c in charts:
        name = c["name"]
        out[name] = {
            "name": name,
            "description": c["description"],
            "version": c["version"],
            "appVersion": c["appVersion"],
            "type": c["type"],
            "keywords": c["keywords"],
            "home": c["home"],
            "sources": c["sources"],
            "helmRepo": HELM_REPO,
            "installName": name,
            "dependencies": c["dependencies"],
            "valuesKeys": flatten_values_keys(c["values"]),
            "values": c["values"],
        }
    return out


def build_crds_json() -> dict:
    print("  Fetching CRD schemas from cluster...", file=sys.stderr)
    out = {}
    for alias, crd_name in RELEVANT_CRDS.items():
        preferred = CRD_PREFERRED_VERSION.get(crd_name, "v1")
        schema = kubectl_crd_schema(crd_name, preferred)
        if schema:
            print(f"    Got {crd_name} @ {schema['version']}", file=sys.stderr)
            out[alias] = schema
        else:
            print(f"    Skipped {crd_name} (not found in cluster)", file=sys.stderr)
    return out


SKILL_MD = """\
---
name: charts
description: >
  Install and configure Helm charts from the mbround18 helm-chart repository
  (https://mbround18.github.io/helm-charts). Covers audiobookshelf, changedetection-io,
  enshrouded, forgejo, foundryvtt, fvtt-dndbeyond-companion, grafana, helm-hub, hytale,
  istio-ingress, keycloak, meilisearch, openobserve, opentelemetry-collector, palworld,
  postgres, pvc-watcher, syncthing, valheim, vaultwarden, vein, wikijs. Use when the user
  asks to install, configure, upgrade, or troubleshoot any of these charts via Helm CLI,
  ArgoCD, or FluxCD.
license: MIT
compatibility: Requires helm >=3.12, kubectl, and optionally argocd-cli or flux-cli
metadata:
  author: mbround18
  repo: https://github.com/mbround18/helm-charts
  generated-by: scripts/generate-charts-skill.py
allowed-tools: Bash(helm:*) Bash(kubectl:*) Bash(flux:*) Bash(argocd:*) Read
---

# mbround18 Helm Charts Skill

Full chart metadata, values references, and CRD schemas live in the `references/` and
`assets/` directories — load them as needed rather than guessing.

- All chart data (names, versions, values keys): [references/charts.json](references/charts.json)
- Live CRD schemas (ArgoCD, FluxCD, Istio): [references/crds.json](references/crds.json)
- Install templates: [assets/](assets/)

## Helm Repository

```bash
helm repo add mbround18 https://mbround18.github.io/helm-charts
helm repo update
```

Charts are published as `mbround18/<chart-name>`. Library charts (`game-tools`,
`gitops-tools`) are not installable directly — they are subcharts only.

## Installation Methods

### 1. Helm CLI

```bash
helm install <release-name> mbround18/<chart-name> \\
  --namespace <namespace> \\
  --create-namespace \\
  --version <version> \\
  -f values.yaml
```

Key flags:
- `--set key=value` for one-off overrides
- `--wait` to block until all resources are ready
- `--timeout 10m` for charts with heavy init (forgejo, wikijs)
- `helm upgrade --install` for idempotent apply

### 2. ArgoCD

Use the template at [assets/argocd-application.yaml](assets/argocd-application.yaml).
The cluster has `applications.argoproj.io` CRD. Full spec shape is in
[references/crds.json](references/crds.json) under `argocd-application`.

Key fields:
```yaml
spec:
  source:
    repoURL: https://mbround18.github.io/helm-charts
    chart: <chart-name>
    targetRevision: <version>          # e.g. 0.1.11
    helm:
      valuesObject: {}                 # inline values (preferred over values string)
  destination:
    server: https://kubernetes.default.svc
    namespace: <namespace>
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
```

#### Sync Waves

All charts use ArgoCD sync waves. Do not invent new wave numbers:

| Phase       | Wave | Resource types                              |
|-------------|------|---------------------------------------------|
| foundation  | 0    | Secrets, PVCs, ServiceAccounts, ConfigMaps  |
| database    | 10   | Database StatefulSets                        |
| supporting  | 20   | Post-dependency Jobs                         |
| release     | 30   | Primary application Deployment/StatefulSet   |
| ingress     | 40   | Services, Ingresses, VirtualServices         |

Charts that depend on `gitops-tools` apply waves automatically via the
`gitops-tools.argocd.annotations` helper. If you need a custom Application
that wraps multiple charts, keep the wave ordering intact.

### 3. FluxCD

Use the template at [assets/fluxcd-helmrelease.yaml](assets/fluxcd-helmrelease.yaml).
The cluster has `helmreleases.helm.toolkit.fluxcd.io` v2 and
`helmrepositories.source.toolkit.fluxcd.io` v1. Full spec shapes in
[references/crds.json](references/crds.json).

Step 1 — add the Helm repository (once per cluster/namespace):
```yaml
apiVersion: source.toolkit.fluxcd.io/v1
kind: HelmRepository
metadata:
  name: mbround18
  namespace: flux-system
spec:
  interval: 1h
  url: https://mbround18.github.io/helm-charts
```

Step 2 — create a HelmRelease:
```yaml
apiVersion: helm.toolkit.fluxcd.io/v2
kind: HelmRelease
metadata:
  name: <release-name>
  namespace: <namespace>
spec:
  interval: 10m
  chart:
    spec:
      chart: <chart-name>
      version: "<version>"
      sourceRef:
        kind: HelmRepository
        name: mbround18
        namespace: flux-system
  values: {}
```

## Chart-Specific Notes

### postgres
Standalone PostgreSQL with secret management. Used as a subchart by `forgejo`,
`wikijs`, and `helm-hub`. Exposes `auth.password` and `auth.superuserPassword`;
when `secrets.password.create: true` these are stored in a Kubernetes Secret.
HA mode (`ha.enabled`) deploys a replica set — leave disabled unless you have a
compatible storage class.

### forgejo
Depends on `postgres` (aliased as `postgresql`) and `gitops-tools`. Requires an
`ExternalSecret` (or manual secret) with keys: `databasePassword`, `runnerToken`,
`githubToken`, `forgejoToken`. Set `config.server.root_url` and
`config.server.domain` before installing.

### istio-ingress
Subchart only — not installable standalone. Controls Istio `Gateway` and
`VirtualService` resources. Enable via `istio-ingress.enabled: true` in the parent
chart. `tls.credentialName` defaults to `cloudflare-client-tls`.

### wikijs
Bundles `postgres` and optionally `meilisearch`. Set `global.secret.annotations`
for external-secrets integration. The wiki DB defaults to `wikijs`/`wikijs`.

### Game servers (valheim, enshrouded, palworld, vein, hytale)
All use `game-tools` library for consistent StatefulSet rendering. Pass
server-specific env vars via the `environment` list. Storage class selection via
`storageClassName`. Backups are opt-in (`backups.enabled: true`).

### vaultwarden
Runs as UID 65534 (nobody). `persistence.enabled: true` is required — data loss
occurs without it. Strategy is `Recreate` to avoid two replicas mounting the same
PVC.

## Common Troubleshooting

```bash
# Render locally to inspect manifests
helm template release-name mbround18/<chart> -f values.yaml

# Check what's failing in ArgoCD
argocd app get <app-name> --show-operation

# Force FluxCD reconciliation
flux reconcile helmrelease <name> -n <namespace>

# Inspect generated secrets
kubectl get secret <name> -o jsonpath='{.data}' | base64 -d
```

## Upgrading Charts

```bash
helm repo update mbround18
helm upgrade <release> mbround18/<chart> -f values.yaml --version <new-version>
```

For ArgoCD: update `targetRevision` and sync. For FluxCD: update `version` field
and let the controller reconcile (interval-driven) or force it with `flux reconcile`.
"""


ARGOCD_APPLICATION_YAML = """\
# ArgoCD Application template for mbround18 helm charts
# Replace <PLACEHOLDERS> before applying.
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: <chart-name>          # e.g. forgejo
  namespace: argocd
  # Sync wave — set to the wave appropriate for this chart's role
  # foundation=0, database=10, supporting=20, release=30, ingress=40
  annotations:
    argocd.argoproj.io/sync-wave: "30"
spec:
  project: default
  source:
    repoURL: https://mbround18.github.io/helm-charts
    chart: <chart-name>       # e.g. forgejo
    targetRevision: <version> # e.g. 0.1.4
    helm:
      valuesObject:
        # Paste chart-specific values here (see references/charts.json for keys)
        {}
  destination:
    server: https://kubernetes.default.svc
    namespace: <namespace>    # e.g. forgejo
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
      - ServerSideApply=true
"""


FLUXCD_HELMRELEASE_YAML = """\
# FluxCD manifests for mbround18 helm charts
# Apply the HelmRepository once per cluster, then one HelmRelease per chart.
---
# Step 1: Register the Helm repository (apply once to flux-system or your namespace)
apiVersion: source.toolkit.fluxcd.io/v1
kind: HelmRepository
metadata:
  name: mbround18
  namespace: flux-system
spec:
  interval: 1h
  url: https://mbround18.github.io/helm-charts
---
# Step 2: HelmRelease — one per chart installation
apiVersion: helm.toolkit.fluxcd.io/v2
kind: HelmRelease
metadata:
  name: <release-name>        # e.g. forgejo
  namespace: <namespace>      # e.g. forgejo
spec:
  interval: 10m
  chart:
    spec:
      chart: <chart-name>     # e.g. forgejo
      version: "<version>"    # e.g. "0.1.4"  (semver constraint supported)
      sourceRef:
        kind: HelmRepository
        name: mbround18
        namespace: flux-system
  # Override values inline (or use valuesFrom to reference a ConfigMap/Secret)
  values:
    {}
  # Uncomment to pull sensitive values from a Secret
  # valuesFrom:
  #   - kind: Secret
  #     name: <chart-name>-values
  #     valuesKey: values.yaml
  install:
    remediation:
      retries: 3
  upgrade:
    remediation:
      retries: 3
      remediateLastFailure: true
    cleanupOnFail: true
"""


def write_skill(charts_json: dict, crds_json: dict) -> None:
    refs_dir = SKILL_DIR / "references"
    assets_dir = SKILL_DIR / "assets"
    refs_dir.mkdir(parents=True, exist_ok=True)
    assets_dir.mkdir(parents=True, exist_ok=True)

    (SKILL_DIR / "SKILL.md").write_text(SKILL_MD)

    (refs_dir / "charts.json").write_text(
        json.dumps(charts_json, indent=2, default=str)
    )

    (refs_dir / "crds.json").write_text(json.dumps(crds_json, indent=2, default=str))

    (assets_dir / "argocd-application.yaml").write_text(ARGOCD_APPLICATION_YAML)
    (assets_dir / "fluxcd-helmrelease.yaml").write_text(FLUXCD_HELMRELEASE_YAML)

    print(f"Wrote skill to {SKILL_DIR}", file=sys.stderr)
    print(f"  SKILL.md          ({len(SKILL_MD)} chars)", file=sys.stderr)
    print(f"  references/charts.json", file=sys.stderr)
    print(f"  references/crds.json", file=sys.stderr)
    print(f"  assets/argocd-application.yaml", file=sys.stderr)
    print(f"  assets/fluxcd-helmrelease.yaml", file=sys.stderr)


def main() -> None:
    print("Scanning charts...", file=sys.stderr)
    charts = []
    for chart_dir in sorted(CHARTS_DIR.iterdir()):
        if not chart_dir.is_dir():
            continue
        chart = load_chart(chart_dir)
        if chart is None:
            continue
        # Skip library charts from the charts.json installable list
        charts.append(chart)
        marker = " [library]" if chart["type"] == "library" else ""
        print(f"  {chart['name']} {chart['version']}{marker}", file=sys.stderr)

    charts_json = build_charts_json(charts)
    crds_json = build_crds_json()
    write_skill(charts_json, crds_json)

    installable = [c for c in charts if c["type"] != "library"]
    library = [c for c in charts if c["type"] == "library"]
    print(
        f"\nDone. {len(installable)} installable charts, {len(library)} library charts, "
        f"{len(crds_json)} CRD schemas captured.",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
