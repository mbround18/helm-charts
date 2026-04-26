# Vaultwarden Helm Chart

This chart was reconstructed from the live manifests in the `vaultwarden` namespace and then adapted to be safer for redeploys.

## Safety Defaults

- Reuses the existing PVC `vaultwarden` by default instead of creating a new claim
- Reuses the existing secret `vaultwarden` for `ADMIN_TOKEN` by default
- Uses `Recreate` deployment strategy by default to avoid concurrent writers on SQLite data
- Marks chart-created PVCs with `helm.sh/resource-policy: keep` so uninstall does not delete data

These defaults are intentional. They reduce the chance of Helm creating a replacement volume or leaving two pods competing over the same database files.

## Current Live Settings Captured

- Image: `vaultwarden/server:1.32.7`
- Data path: `/data`
- Existing PVC: `vaultwarden`
- Existing admin secret: `vaultwarden` key `admin-token`
- Domain: `https://key.bruno.fyi`
- VirtualService host: `key.bruno.fyi`
- VirtualService gateway: `vaultwarden-gateway`

## Safe Migration

Before changing anything, confirm the current PVC is still bound:

```bash
kubectl -n vaultwarden get pvc vaultwarden
```

Render the chart exactly as it is intended to be installed:

```bash
helm template vaultwarden charts/vaultwarden --namespace vaultwarden
```

Install or upgrade while reusing the live claim and secret:

```bash
helm upgrade --install vaultwarden charts/vaultwarden \
  --namespace vaultwarden \
  --create-namespace \
  --set persistence.existingClaim=vaultwarden \
  --set secret.existingSecret=vaultwarden
```

If you want Helm to create a brand new PVC for a fresh environment, explicitly disable the existing claim reference:

```bash
helm upgrade --install vaultwarden charts/vaultwarden \
  --namespace vaultwarden \
  --set persistence.existingClaim= \
  --set persistence.create=true
```

## Notes

- `ADMIN_TOKEN` should be an Argon2 hash, not a plain token, if you choose to let this chart create the secret.
- The optional `VirtualService` template is enabled by default because that matches the live namespace today.
- If your ingress is managed elsewhere, disable `virtualService.enabled`.

## Argo CD Metadata

The chart now detects Argo CD by checking Helm capabilities for Argo CD APIs such as `argoproj.io/v1alpha1/Application`.

The Argo CD detection and metadata merge logic now lives in the shared library chart `gitops-tools`, so other charts can reuse the same behavior without copying helper blocks.

- `argoCd.mode=auto`: add Argo CD sync-wave annotations only when Argo CD CRDs are present
- `argoCd.mode=enabled`: always emit Argo CD metadata even in plain `helm template`
- `argoCd.mode=disabled`: never emit Argo CD metadata
- `argoCd.instanceLabel`: optional value for `argocd.argoproj.io/instance`
- `argoCd.commonAnnotations`: common Argo annotations to place on rendered resources
- `argoCd.commonLabels`: common Argo-oriented labels to place on rendered resources

This keeps plain Helm renders clean while still making use of Argo CD sync ordering and tracking metadata when the cluster supports it.
