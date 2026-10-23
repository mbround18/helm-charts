# static-pull-thru

A pull-through cache for an origin that is sometimes down: a home server
reached over a VPN, a game server's web panel, anything you don't control the
uptime of.

nginx sits between your ingress and the origin. While the origin is up,
responses are cached and refreshed in the background. While it is down, nginx
answers from the cache, and pages get a small "server offline" toast.

```
ingress / gateway → static-pull-thru → origin
```

## Install

```sh
helm install maps mbround18/static-pull-thru \
  --set upstream.host=my-origin.my-namespace.svc \
  --set upstream.port=3030
```

Then point your route at the `static-pull-thru` Service (port `8080`) instead of
the origin.

## What it does

- **Serves stale on failure.** Connection errors, timeouts and 5xx answers from
  the origin return the last cached copy (`X-Cache-Status: STALE`).
- **Stays fresh while the origin is up.** Entries are fresh for `cache.validFor`
  (5 minutes), then refreshed in the background.
- **Keeps entries for `cache.inactive`** (30 days), on a PVC by default, so the
  cache survives pod restarts.
- **Toast.** HTML responses get `<script src="/__pull-thru/toast.js">`. It
  polls `/__pull-thru/upstream` and shows a toast while the origin is down. The
  script comes from the same origin, so a `script-src 'self'` CSP allows it.
- **Offline page.** A path never cached while the origin was up gets a 503
  page explaining that, instead of a bare gateway error.

## Limits

- **Only what was fetched is cached.** A file nobody requested while the origin
  was up cannot be served while it is down.
- **Everything outside `bypassPaths` is treated as public.** Responses that set
  a cookie, and requests with an `Authorization` header, are never cached. Put
  per-user paths such as APIs and auth in `bypassPaths`, which go straight to
  the origin, websockets included.
- **`upstream.host` is resolved once, at startup.** Use a name that always
  resolves, such as a ClusterIP Service: the origin being down is fine, its
  name not resolving is not.
- **One replica.** The cache volume is ReadWriteOnce.

## Values

| Key                         | Default                       | Description                                   |
| --------------------------- | ----------------------------- | --------------------------------------------- |
| `upstream.host`             | `origin` (placeholder)        | Origin host. Must be set.                     |
| `upstream.port`             | `80`                          | Origin port.                                  |
| `upstream.hostHeader`       | `""`                          | Host header for the origin; empty forwards it |
| `upstream.connectTimeout`   | `3s`                          | How long to wait before serving stale.        |
| `bypassPaths`               | `[]`                          | Path prefixes never cached.                   |
| `cache.validFor`            | `5m`                          | Freshness window.                             |
| `cache.inactive`            | `30d`                         | Longest outage the cache can cover.           |
| `cache.maxSize`             | `900m`                        | nginx cache cap; keep below the PVC size.     |
| `cache.persistence.enabled` | `true`                        | `false` uses an emptyDir.                     |
| `cache.persistence.size`    | `1Gi`                         | PVC size.                                     |
| `toast.enabled`             | `true`                        | Inject the offline toast into HTML.           |
| `toast.message`             | `The server is offline. …`    | Toast text.                                   |
| `toast.checkInterval`       | `30`                          | Seconds between origin checks.                |
| `toast.healthPath`          | `/`                           | Origin path probed; below 500 means up.       |
| `offlinePage.message`       | `The server is offline and …` | Body of the never-cached 503 page.            |
