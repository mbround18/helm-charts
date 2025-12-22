## Contributing

Thank you for wanting to contribute! See the repository `README.md` for general information. This file contains project-specific developer guidance.

---

## Getting Started

### Prerequisites

Before developing charts, ensure you have:

- Helm 3.2.0+
- Python 3.12+
- Node.js (for prettier)
- `git` and basic Kubernetes familiarity

### Initial Setup

1. Clone the repository:

   ```bash
   git clone https://github.com/mbround18/helm-charts.git
   cd helm-charts
   ```

2. Create a feature branch:

   ```bash
   git checkout -b feature/my-chart-name
   ```

---

## Chart Anatomy

### Standard Structure

Every chart follows this layout:

```text
charts/<chart-name>/
├── Chart.yaml          # Metadata (name, version, appVersion)
├── values.yaml         # Default configuration
├── templates/          # Kubernetes manifests
│   ├── deployment.yaml # Workload definitions
│   ├── service.yaml    # Service exposure
│   ├── _helpers.tpl    # Reusable functions
│   └── ...
├── README.md          # Chart documentation
└── .helmignore        # Ignore patterns for packaging
```

### Creating a New Chart

Use Helm to scaffold:

```bash
helm create charts/<chart-name>
cd charts/<chart-name>
```

Then customize `Chart.yaml`, `values.yaml`, and templates for your application.

---

## Development Best Practices

### Storage

Always provide persistent storage options for data-bearing workloads:

- Add `persistence.enabled` and `persistence.storageClass` to `values.yaml`
- Use `storageClassName: {{ .Values.persistence.storageClass }}` in PVCs

### Resources

Set reasonable resource requests and limits:

```yaml
resources:
  requests:
    cpu: "100m"
    memory: "128Mi"
  limits:
    cpu: "500m"
    memory: "512Mi"
```

### Security

Use non-root containers and drop unnecessary capabilities:

```yaml
securityContext:
  runAsNonRoot: true
  runAsUser: 1000
  allowPrivilegeEscalation: false
  capabilities:
    drop: [ALL]
```

### Documentation

Include a comprehensive `README.md` with:

- Chart overview and use case
- Configuration examples
- Troubleshooting tips
- Performance tuning notes

### Secrets

Never hardcode credentials—use Kubernetes secrets:

```yaml
env:
  - name: API_KEY
    valueFrom:
      secretKeyRef:
        name: myapp-secrets
        key: api-key
```

Use `values.secret.yml` (git-ignored) for sensitive values during development.

### Versioning

- **Chart version**: Increment `Chart.yaml` `version` when the _chart_ changes (templates, values structure)
- **appVersion**: Update when the _application_ version changes

Example:

```yaml
version: 0.2.0 # Bumped for new features
appVersion: "1.5.3" # Application version
```

---

## Development Workflow

### Format & Lint

Ensure code quality:

```bash
make lint
```

This runs:

- Prettier (YAML/markdown formatting)
- Helm lint (chart validation)
- Ruff (Python style checks)

### Template Charts

Generate Kubernetes manifests from your templates:

```bash
make dump
```

Output: `tmp/<chart-name>/manifest-00.yaml`, etc.

### Validate YAML

Ensure generated manifests are valid:

```bash
make test
```

This validates without requiring a Kubernetes cluster.

### Test Installation

For a dry-run (no cluster required):

```bash
helm install test-release ./charts/<chart-name> --dry-run --debug
```

For a real cluster (requires `kubectl` access):

```bash
helm install test-release ./charts/<chart-name> \
  --namespace test-env \
  --create-namespace \
  --wait
```

### Build & Package

Create distributable chart packages:

```bash
make build
```

Output: `tmp/<chart-name>-<version>.tgz`

---

## Contribution Steps

### 1. Fork the Repository

Create your own GitHub fork.

### 2. Create a Feature Branch

```bash
git checkout -b feature/my-awesome-change
```

### 3. Make & Test Changes

```bash
# Edit your chart
vim charts/<chart-name>/values.yaml

# Lint & validate
make lint
make dump
make test

# Test installation
helm install test ./charts/<chart-name> --dry-run --debug
```

### 4. Commit with Clear Messages

```bash
git commit -m "Add backup support to palworld chart"
```

### 5. Push & Open a Pull Request

```bash
git push origin feature/my-awesome-change
```

Then open a PR on GitHub with:

- Clear description of changes
- Any related issues
- Testing notes

### Code Review

All PRs require review before merging:

- CI/CD validation must pass
- Documentation must be updated
- Follow existing chart patterns

---

## Advanced Topics

### Using the game-tools Library

When creating game server charts, leverage the `game-tools` library:

1. Add to `Chart.yaml` dependencies
2. See [charts/game-tools/README.md](../charts/game-tools/README.md) for template usage

### Centralized Makefile Pattern

We use `config/Makefile` to avoid duplication across charts. When creating a chart with a Makefile, use this wrapper pattern:

```makefile
# Chart-specific overrides
CHART_DIR := $(CURDIR)
RELEASE_NAME ?= your-chart-name
BUILD_DIR ?= tmp

# Include centralized targets
include $(abspath $(CURDIR)/../..)/config/Makefile
```

From your chart directory, you can now run: `make lint`, `make dump`, `make test`, `make build`.

---

## Troubleshooting

### Chart Won't Template

Check for validation errors:

```bash
helm lint ./charts/<chart-name>
```

Common issues:

- Indentation errors (YAML is whitespace-sensitive)
- Missing quotes around variables
- Incorrect template syntax

### Tests Fail with YAML Errors

See what was generated:

```bash
make dump
cat tmp/<chart-name>/manifest-00.yaml
```

Validate manually:

```bash
kubectl apply -f tmp/<chart-name>/manifest-00.yaml --dry-run=client
```

### Makefile Target Not Found

Ensure:

- You're in a chart directory with a `Makefile`
- The `Makefile` includes `config/Makefile` from repo root
- `config/Makefile` exists in repository root

---

## Quick Reference

| Task            | Command                               |
| --------------- | ------------------------------------- |
| Format & lint   | `make lint`                           |
| Template charts | `make dump`                           |
| Validate YAML   | `make test`                           |
| Package charts  | `make build`                          |
| Test (dry-run)  | `helm install test <chart> --dry-run` |
| View values     | `helm show values <chart>`            |
| Debug templates | `helm template <chart> --debug`       |
