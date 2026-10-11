# k8s-reaper Helm Chart

A Helm chart for [k8s-reaper](https://github.com/mbround18/k8s-reaper), a Kubernetes controller that finds workloads that have been crash-looping for a long time. In `report` mode (the default) it only reports what it would do; in `full` mode it scales them to zero, suspends failing CronJobs, and keeps Flux from undoing that until you restore them.

## Features

- `ReaperConfig` CRD and a `ReaperConfig/default` in `report` mode, rendered from values
- Single-replica Deployment (`Recreate`), non-root, read-only root filesystem
- Least-privilege ClusterRole: no `delete`, no Secrets, no wildcards
- Service on port `8080` (`/healthz`, `/readyz`, `/metrics`)
- Optional ServiceMonitor and PrometheusRule with the reaper's alerts
- Optional notifications Secret mount (Discord, Slack, webhooks, email)

## Prerequisites

- Kubernetes 1.25+
- Helm 3.2.0+
- Prometheus Operator CRDs, only if `serviceMonitor.enabled` or `prometheusRule.enabled`

## Quick Start

```bash
helm repo add mbround18 https://mbround18.github.io/helm-charts/
helm repo update
helm install k8s-reaper mbround18/k8s-reaper --namespace k8s-reaper --create-namespace
kubectl get reaperconfig default
```

Install it into its own namespace: the reaper never acts on the namespace it runs in.

## Configuration

| Parameter                    | Description                                                       | Default                         |
| ---------------------------- | ----------------------------------------------------------------- | ------------------------------- |
| `image.repository`           | Container image repository                                        | `mbround18/k8s-reaper`          |
| `image.tag`                  | Image tag                                                         | Chart `appVersion`              |
| `reaperConfig.create`        | Render the cluster-scoped `ReaperConfig`                          | `true`                          |
| `reaperConfig.name`          | Its name; also passed as `REAPER_CONFIG_NAME`                     | `default`                       |
| `reaperConfig.spec`          | Free-form `ReaperConfig` spec; any CRD field                      | `{mode: report}`                |
| `notifications.secretName`   | Secret of channel URLs to mount (`optional: true`); `""` for none | `k8s-reaper-notifications`      |
| `notifications.mountPath`    | Mount path; also passed as `REAPER_NOTIFICATIONS_DIR`             | `/etc/k8s-reaper/notifications` |
| `logFormat`                  | `json` or `text`                                                  | `json`                          |
| `logLevel`                   | `RUST_LOG` filter                                                 | `info`                          |
| `otel.endpoint`              | `OTEL_EXPORTER_OTLP_ENDPOINT`; empty keeps OTLP off               | `""`                            |
| `serviceMonitor.enabled`     | Create a ServiceMonitor                                           | `false`                         |
| `serviceMonitor.honorLabels` | Keep the reaper's `namespace` label (the workload's namespace)    | `true`                          |
| `prometheusRule.enabled`     | Create a PrometheusRule with the reaper's alerts                  | `false`                         |
| `prometheusRule.runbookUrl`  | `runbook_url` annotation on every alert                           | restoring-a-workload guide      |
| `rbac.create`                | Create the ClusterRole and ClusterRoleBinding                     | `true`                          |
| `serviceAccount.create`      | Create the ServiceAccount                                         | `true`                          |
| `resources`                  | CPU/memory requests/limits                                        | See values.yaml                 |

Replicas and the update strategy are fixed: the reaper is a single instance with no leader election.

## Usage Examples

### Switch to full mode

```yaml
reaperConfig:
  spec:
    mode: full
    limits:
      maxReapsPerCycle: 1
      maxReaped: 5
```

### Prometheus Operator

```yaml
serviceMonitor:
  enabled: true
prometheusRule:
  enabled: true
  labels:
    release: kube-prometheus-stack
```

`ReaperDown` matches `up{job="<service name>"}`; the Service is named after the release (`k8s-reaper` when the release is called `k8s-reaper`). It is only installed when `serviceMonitor.enabled` is `true`, since without the ServiceMonitor nothing scrapes the reaper. If the ServiceMonitor is enabled but your Prometheus does not select it, `ReaperDown` fires.

### Notifications

Create the Secret yourself (one key per channel, one URL per key) in the release namespace. The chart never creates it, so URLs stay out of Helm release history:

```bash
kubectl -n k8s-reaper create secret generic k8s-reaper-notifications \
  --from-literal=ops-discord=https://discord.com/api/webhooks/<id>/<token>
```

## CRD upgrades

The CRD lives in `crds/` and is generated by `k8s-reaper crd`. Helm installs it on first install but never upgrades it. On upgrades apply it yourself, or with Flux set `install.crds` and `upgrade.crds` to `CreateReplace`.

## Troubleshooting

- Check pod logs: `kubectl logs -n k8s-reaper deploy/k8s-reaper`
- `kubectl get reaperconfig default` must show `VALID True`; otherwise read its `status.conditions`
- `/readyz` stays failing until the caches sync and a cycle completes

---

For full configuration options, see [values.yaml](values.yaml) and the [k8s-reaper guides](https://github.com/mbround18/k8s-reaper/tree/main/docs/guides).
