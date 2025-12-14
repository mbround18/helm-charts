# Helm Charts Repository

[![Helm Validation](https://github.com/mbround18/helm-charts/actions/workflows/helm.yml/badge.svg)](https://github.com/mbround18/helm-charts/actions/workflows/helm.yml)
[![License: BSD-3-Clause](https://img.shields.io/badge/License-BSD%203--Clause-blue.svg)](LICENSE)

Welcome to the **mbround18 Helm Charts Repository** - a curated collection of production-ready Helm charts for game servers and companion tools, hosted with ❤️ on GitHub Pages. Whether you're running a private gaming community or managing multiple game servers at scale, these charts provide battle-tested Kubernetes deployments with sensible defaults and extensive customization options.

---

## 📚 Table of Contents

- [Quick Start](#-quick-start)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
- [Available Charts](#-available-charts)
  - [Game Servers](#game-servers)
  - [Utility & Tools](#utility--tools)
- [Usage Examples](#-usage-examples)
- [Chart Development](#-chart-development)
- [Contributing](#-contributing)
- [Documentation](#-documentation)
- [Support & Community](#-support--community)
- [License](#-license)

---

## 🚀 Quick Start

### Prerequisites

Before you begin, ensure you have the following:

**Required:**

- **Kubernetes cluster** (v1.19+)
  - Cloud providers: GKE, EKS, AKS, DigitalOcean Kubernetes
  - Self-hosted: kubeadm, k3s, RKE, or similar
- **Helm 3** (v3.2.0+) - [Installation Guide](https://helm.sh/docs/intro/install/)
- **kubectl** configured with access to your cluster

**Recommended:**

- **Persistent Volume provisioner** (most charts require storage)
  - Cloud: Use provider's default StorageClass
  - Self-hosted: Longhorn, Rook-Ceph, NFS, or hostPath
- **NodePort or LoadBalancer** capability (for external game server access)

**For Newcomers:**

If you're new to Kubernetes and Helm, here's what you need to know:

1. **Kubernetes** is a container orchestration platform that manages application deployments
2. **Helm** is a package manager for Kubernetes (think `apt`/`yum` for Kubernetes)
3. **Helm Charts** are pre-configured Kubernetes resource templates
4. **kubectl** is the command-line tool for interacting with Kubernetes

**Quickstart Guides by Platform:**

- [Getting Started with k3s](https://docs.k3s.io/quick-start) (Lightweight Kubernetes for home servers)
- [Getting Started with Docker Desktop Kubernetes](https://docs.docker.com/desktop/kubernetes/) (Local development)
- [Getting Started with Minikube](https://minikube.sigs.k8s.io/docs/start/) (Local testing)

### Installation

#### Step 1: Add the Helm Repository

```bash
# Add this repository to your Helm client
helm repo add mbround18 https://mbround18.github.io/helm-charts/

# Update your local cache
helm repo update
```

#### Step 2: Search Available Charts

```bash
# List all available charts
helm search repo mbround18

# Search for specific charts
helm search repo mbround18/palworld
```

#### Step 3: Install a Chart

```bash
# Basic installation (uses default values)
helm install my-game-server mbround18/<chart-name>

# Installation with custom values
helm install my-game-server mbround18/<chart-name> \
  --namespace game-servers \
  --create-namespace \
  --set key=value

# Installation with values file (recommended)
helm show values mbround18/<chart-name> > values.yaml
# Edit values.yaml with your preferences
helm install my-game-server mbround18/<chart-name> \
  --namespace game-servers \
  --create-namespace \
  --values values.yaml
```

#### Step 4: Verify Installation

```bash
# Check deployment status
helm status my-game-server --namespace game-servers

# Watch pod startup
kubectl get pods --namespace game-servers --watch

# View logs
kubectl logs -f <pod-name> --namespace game-servers
```

---

## 📦 Available Charts

### Game Servers

These charts deploy dedicated game servers optimized for Kubernetes with persistent storage, automatic restarts, and resource management.

#### **[Palworld](charts/palworld/)**

**Status:** Production Ready | **Version:** 0.3.2

Deploy a Palworld dedicated server with persistent world saves and player data.

- **Features:** Persistent storage, configurable settings, RCON support
- **Resources:** ~4GB RAM, 2 CPU cores recommended
- **Use Case:** Private Palworld servers for friends or communities

```bash
helm install palworld mbround18/palworld \
  --namespace palworld \
  --create-namespace \
  --set env.SERVER_NAME="My Palworld Server"
```

#### **[Valheim](charts/valheim/)**

**Status:** Production Ready | **Version:** 0.4.1

Run a Valheim dedicated server with automated backups and world management.

- **Features:** World persistence, backup support, BepInEx mod support
- **Resources:** ~2GB RAM, 2 CPU cores recommended
- **Use Case:** Viking survival servers with persistent worlds

```bash
helm install valheim mbround18/valheim \
  --namespace valheim \
  --create-namespace \
  --set env.SERVER_NAME="Valhalla"
```

## Contributing

**Status:** Stable | **Version:** 0.1.0 | [📖 Detailed README](charts/game-tools/README.md)

A Helm library chart providing reusable templates and patterns for game server deployments.

- **Type:** Library (not directly installable)
- **Purpose:** Shared templates for NodePort services, storage patterns, etc.
- **Use Case:** Creating your own game server charts
- **Features:**
  - NodePort service helper with intelligent port negotiation
  - Auto-assignment and fixed port support
  - Multi-protocol (UDP/TCP) configuration

#### **[fvtt-dndbeyond-companion](charts/fvtt-dndbeyond-companion/)**

**Status:** Stable | **Version:** 0.0.3 | [📖 Detailed README](charts/fvtt-dndbeyond-companion/README.md)

Companion service for the FoundryVTT D&D Beyond integration module.

- **Features:** RESTful API companion, ingress support
- **Resources:** Minimal (~512MB RAM)
- **Use Case:** Enhance FoundryVTT with D&D Beyond integration

```bash
helm install beyond-companion mbround18/fvtt-dndbeyond-companion \
  --namespace foundry \
  --values values.yaml
```

#### **[pvc-watcher](charts/pvc-watcher/)**

**Status:** Experimental | **Version:** 0.3.0

Utility for monitoring and managing Persistent Volume Claims.

- **Features:** PVC monitoring, automatic cleanup helpers
- **Use Case:** PVC lifecycle management

---

## 💡 Usage Examples

### Example 1: Simple Game Server Setup (Newcomer Friendly)

This example shows how to set up a basic Valheim server from scratch:

```bash
# 1. Create a dedicated namespace
kubectl create namespace vikings

# 2. Install the chart with minimal configuration
helm install my-valheim mbround18/valheim \
  --namespace vikings \
  --set env.SERVER_NAME="My First Server" \
  --set env.WORLD_NAME="Midgard" \
  --set env.SERVER_PASSWORD="super-secret-password"

# 3. Wait for the pod to be ready
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=valheim -n vikings --timeout=300s

# 4. Get the server connection information
kubectl get svc -n vikings
# Look for the NodePort (30000-32767 range)
# Connect using: <NODE_IP>:<NODEPORT>

# 5. View server logs
kubectl logs -f -l app.kubernetes.io/name=valheim -n vikings
```

### Example 2: Production Setup with Custom Values (Experienced Users)

```bash
# 1. Export default values to customize
helm show values mbround18/palworld > palworld-prod.yaml

# 2. Edit the values file (palworld-prod.yaml)
cat << 'EOF' > palworld-prod.yaml
replicaCount: 1

image:
  pullPolicy: Always

env:
  SERVER_NAME: "Palworld Production"
  SERVER_PASSWORD: "change-me-via-secret"
  MAX_PLAYERS: "32"
  PUBLIC_PORT: "8211"

service:
  type: NodePort
  ports:
    game:
      nodePort: 30211

persistence:
  enabled: true
  storageClass: "fast-ssd"
  size: 50Gi

resources:
  requests:
    cpu: "2"
    memory: "4Gi"
  limits:
    cpu: "4"
    memory: "8Gi"

nodeSelector:
  node-role: game-servers
EOF

# 3. Install with custom values
helm install palworld-prod mbround18/palworld \
  --namespace production \
  --create-namespace \
  --values palworld-prod.yaml

# 4. Monitor rollout
kubectl rollout status statefulset/palworld-prod -n production
```

### Example 3: Multi-Server Setup

```bash
# Deploy multiple game servers in isolated namespaces
for game in palworld valheim enshrouded; do
  helm install $game mbround18/$game \
    --namespace $game \
    --create-namespace \
    --set resources.limits.memory=8Gi
done

# List all game servers
kubectl get pods --all-namespaces -l 'app.kubernetes.io/managed-by=Helm'
```

### Example 4: Upgrading a Chart

```bash
# Check for updates
helm repo update

# See what would change
helm diff upgrade my-game-server mbround18/<chart-name> \
  --namespace game-servers \
  --values values.yaml

# Perform the upgrade
helm upgrade my-game-server mbround18/<chart-name> \
  --namespace game-servers \
  --values values.yaml

# Rollback if needed
helm rollback my-game-server --namespace game-servers
```

---

## 🛠 Chart Development

### For Contributors and Chart Developers

Want to create your own game server chart or contribute to existing ones? Here's how to get started.

#### Local Development Setup

```bash
# 1. Clone the repository
git clone https://github.com/mbround18/helm-charts.git
cd helm-charts

# 2. Install development dependencies
# - Helm 3.2.0+
# - Python 3.12+
# - Node.js (for prettier)

# 3. Make changes to charts in ./charts/<chart-name>/

# 4. Lint your changes
make lint

# 5. Test chart rendering
make dump

# 6. Validate generated YAML
make test

# 7. Test installation (requires Kubernetes cluster)
helm install test-release ./charts/<chart-name> \
  --dry-run --debug
```

#### Development Workflow

```bash
# Format code
make lint

# Build all charts
make build

# Test chart templates
make test

# Package charts (output to ./tmp/)
make build
```

#### Using game-tools Library

When creating a new game server chart, leverage the `game-tools` library:

```yaml
# Chart.yaml
dependencies:
  - name: game-tools
    version: 0.1.0
    repository: https://mbround18.github.io/helm-charts/
```

See the [game-tools README](charts/game-tools/README.md) for template usage.

#### Chart Structure

```
charts/<chart-name>/
├── Chart.yaml          # Chart metadata
├── values.yaml         # Default configuration values
├── templates/          # Kubernetes manifests
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── _helpers.tpl
│   └── ...
├── README.md          # Chart documentation
└── .helmignore        # Files to ignore during packaging
```

#### Best Practices

1. **Storage:** Always provide persistent storage options for game data
2. **Resources:** Set reasonable resource requests and limits
3. **Security:** Use non-root containers where possible
4. **Documentation:** Include comprehensive README with examples
5. **Secrets:** Never hardcode credentials - use Kubernetes secrets
6. **Testing:** Test with `helm lint` and `make test` before submitting

---

## 🤝 Contributing

We welcome contributions from both newcomers and experienced developers! Here's how you can help:

### Ways to Contribute

- **Report Bugs:** [Open an issue](https://github.com/mbround18/helm-charts/issues/new) with details
- **Request Features:** Share your ideas for new charts or improvements
- **Improve Documentation:** Fix typos, add examples, clarify instructions
- **Submit Charts:** Add support for new game servers
- **Fix Issues:** Browse [open issues](https://github.com/mbround18/helm-charts/issues) and submit PRs

### Contribution Workflow

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Make** your changes and test thoroughly
4. **Commit** with clear messages (`git commit -m 'Add amazing feature'`)
5. **Push** to your fork (`git push origin feature/amazing-feature`)
6. **Open** a Pull Request with a clear description

### Code Review Process

- All submissions require review before merging
- CI/CD must pass (Helm validation, YAML linting)
- Documentation must be updated for user-facing changes
- Follow existing chart patterns and conventions

### Testing Your Changes

```bash
# Lint all charts
make lint

# Validate chart templates
make test

# Test specific chart installation
helm install test-release ./charts/<chart-name> \
  --dry-run --debug \
  --namespace test

# Test in a real cluster (recommended)
helm install test-release ./charts/<chart-name> \
  --namespace test-env \
  --create-namespace
```

---

## 📖 Documentation

### Repository Documentation

- **[PVC Cleaning Guide](docs/guide-pvc-cleaning.md)** - Comprehensive guide for managing PVCs and fresh installations

### Chart-Specific Documentation

Each chart has its own detailed README with:

- Complete configuration reference
- Advanced usage examples
- Troubleshooting guides
- Performance tuning recommendations

**Detailed Chart READMEs:**

- [Vein Chart Documentation](charts/vein/README.md) - Comprehensive guide with 400+ lines
- [game-tools Library Documentation](charts/game-tools/README.md) - Template usage guide
- [fvtt-dndbeyond-companion Documentation](charts/fvtt-dndbeyond-companion/README.md)

### External Resources

- [Helm Documentation](https://helm.sh/docs/) - Official Helm docs
- [Kubernetes Documentation](https://kubernetes.io/docs/) - Official Kubernetes docs
- [Game Server Hosting Best Practices](https://kubernetes.io/blog/2018/03/22/kubernetes-game-servers/)

---

## 🆘 Support & Community

### Getting Help

**For Chart Issues:**

1. Check the chart's README for troubleshooting sections
2. Search [existing issues](https://github.com/mbround18/helm-charts/issues)
3. [Open a new issue](https://github.com/mbround18/helm-charts/issues/new) with:
   - Chart name and version
   - Kubernetes version
   - Error messages or unexpected behavior
   - Steps to reproduce

**For General Questions:**

- Review the [documentation](#-documentation)
- Check the [examples](#-usage-examples)
- Look at the [PVC Cleaning Guide](docs/guide-pvc-cleaning.md) for storage issues

### FAQ

**Q: My game server isn't accessible from the internet. What do I check?**

A: Verify these in order:

1. Pod is running: `kubectl get pods -n <namespace>`
2. Service is created: `kubectl get svc -n <namespace>`
3. Check the NodePort or LoadBalancer IP
4. Ensure firewall rules allow traffic to the port (UDP/TCP as needed)
5. For cloud providers, check security groups

**Q: How do I backup my game server data?**

A: Game data is stored in Persistent Volume Claims (PVCs). Options:

1. Use Velero for cluster-level backups
2. Use your storage provider's snapshot feature
3. Manually backup using `kubectl exec` to tar the data

See individual chart READMEs for specific backup instructions.

**Q: Can I run multiple game servers on the same cluster?**

A: Yes! Use different namespaces and ensure adequate resources:

```bash
kubectl create namespace game1
kubectl create namespace game2
helm install server1 mbround18/palworld -n game1
helm install server2 mbround18/valheim -n game2
```

**Q: How do I customize game server settings?**

A: Each chart has a `values.yaml` with configurable options:

```bash
helm show values mbround18/<chart-name> > custom-values.yaml
# Edit custom-values.yaml
helm install my-server mbround18/<chart-name> -f custom-values.yaml
```

**Q: What if my chart version is outdated?**

A: Update your Helm repo and upgrade:

```bash
helm repo update
helm upgrade my-server mbround18/<chart-name>
```

**Q: How do I completely remove a game server?**

A: Uninstall the Helm release (note: this may keep PVCs):

```bash
helm uninstall my-server -n <namespace>

# To also delete PVCs:
kubectl delete pvc -n <namespace> --all

# To delete the entire namespace:
kubectl delete namespace <namespace>
```

---

## 📋 Requirements

### Minimum Requirements

| Component  | Version | Notes                          |
| ---------- | ------- | ------------------------------ |
| Kubernetes | 1.19+   | Most cloud providers supported |
| Helm       | 3.2.0+  | Helm 2 not supported           |
| kubectl    | 1.19+   | Should match cluster version   |

### Resource Requirements by Chart

| Chart      | CPU (min) | Memory (min) | Storage (min) | Notes                     |
| ---------- | --------- | ------------ | ------------- | ------------------------- |
| Palworld   | 2 cores   | 4Gi          | 20Gi          | RAM scales with players   |
| Valheim    | 2 cores   | 2Gi          | 10Gi          | Modest requirements       |
| Vein       | 4 cores   | 12Gi         | 25Gi          | **Very memory-intensive** |
| Enshrouded | 2 cores   | 4Gi          | 20Gi          | Similar to Palworld       |
| FoundryVTT | 1 core    | 2Gi          | 5Gi           | Lightweight               |

**Note:** These are minimum requirements. Production deployments should allocate more resources for optimal performance.

---

## 📄 License

This repository is licensed under the **BSD 3-Clause License**. See the [LICENSE](LICENSE) file for details.

```
Copyright (c) 2023, Michael
All rights reserved.
```

---

## 🙏 Acknowledgments

- All contributors who have helped improve these charts
- The Helm and Kubernetes communities for excellent tooling
- Game developers whose servers we're hosting
- Users who report issues and provide feedback

---

## 📊 Project Status

- **Build Status:** ![Helm Validation](https://github.com/mbround18/helm-charts/actions/workflows/helm.yml/badge.svg)
- **Active Maintenance:** ✅ Regularly updated
- **Production Ready:** Most charts are stable and battle-tested
- **Community:** Open to contributions

---

**Happy Gaming! 🎮**

If you find these charts useful, please ⭐ star the repository and share it with others!
