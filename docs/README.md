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

## 📦 Available Charts

<!-- CHARTS:START -->

```bash
helm repo add mbround18 https://mbround18.github.io/helm-charts/
helm repo update
```

<table>
  <thead>
    <tr><th>name</th><th>version</th><th>setup</th><th>values</th></tr>
  </thead>
  <tbody>
    <tr><td><a href="../charts/audiobookshelf/README.md">audiobookshelf</a></td><td>0.1.1</td><td><pre><code class="language-sh">helm install audiobookshelf mbround18/audiobookshelf --namespace audiobookshelf --create-namespace</code></pre></td><td><pre><code class="language-sh">helm show values mbround18/audiobookshelf</code></pre></td></tr>
    <tr><td><a href="../charts/enshrouded/README.md">enshrouded</a></td><td>0.3.2</td><td><pre><code class="language-sh">helm install enshrouded mbround18/enshrouded --namespace enshrouded --create-namespace</code></pre></td><td><pre><code class="language-sh">helm show values mbround18/enshrouded</code></pre></td></tr>
    <tr><td><a href="../charts/foundryvtt/README.md">foundryvtt</a></td><td>0.2.9</td><td><pre><code class="language-sh">helm install foundryvtt mbround18/foundryvtt --namespace foundryvtt --create-namespace</code></pre></td><td><pre><code class="language-sh">helm show values mbround18/foundryvtt</code></pre></td></tr>
    <tr><td><a href="../charts/fvtt-dndbeyond-companion/README.md">fvtt-dndbeyond-companion</a></td><td>0.0.3</td><td><pre><code class="language-sh">helm install fvtt-dndbeyond-companion mbround18/fvtt-dndbeyond-companion --namespace fvtt-dndbeyond-companion --create-namespace</code></pre></td><td><pre><code class="language-sh">helm show values mbround18/fvtt-dndbeyond-companion</code></pre></td></tr>
    <tr><td><a href="../charts/istio-ingress/README.md">istio-ingress</a></td><td>0.1.0</td><td><pre><code class="language-sh">helm install istio-ingress mbround18/istio-ingress --namespace istio-ingress --create-namespace</code></pre></td><td><pre><code class="language-sh">helm show values mbround18/istio-ingress</code></pre></td></tr>
    <tr><td><a href="../charts/meilisearch/README.md">meilisearch</a></td><td>0.1.9</td><td><pre><code class="language-sh">helm install meilisearch mbround18/meilisearch --namespace meilisearch --create-namespace</code></pre></td><td><pre><code class="language-sh">helm show values mbround18/meilisearch</code></pre></td></tr>
    <tr><td><a href="../charts/palworld/README.md">palworld</a></td><td>0.3.2</td><td><pre><code class="language-sh">helm install palworld mbround18/palworld --namespace palworld --create-namespace</code></pre></td><td><pre><code class="language-sh">helm show values mbround18/palworld</code></pre></td></tr>
    <tr><td><a href="../charts/postgres/README.md">postgres</a></td><td>0.1.12</td><td><pre><code class="language-sh">helm install postgres mbround18/postgres --namespace postgres --create-namespace</code></pre></td><td><pre><code class="language-sh">helm show values mbround18/postgres</code></pre></td></tr>
    <tr><td><a href="../charts/pvc-watcher/README.md">palworld</a></td><td>0.3.0</td><td><pre><code class="language-sh">helm install pvc-watcher mbround18/pvc-watcher --namespace pvc-watcher --create-namespace</code></pre></td><td><pre><code class="language-sh">helm show values mbround18/pvc-watcher</code></pre></td></tr>
    <tr><td><a href="../charts/syncthing/README.md">syncthing</a></td><td>0.1.0</td><td><pre><code class="language-sh">helm install syncthing mbround18/syncthing --namespace syncthing --create-namespace</code></pre></td><td><pre><code class="language-sh">helm show values mbround18/syncthing</code></pre></td></tr>
    <tr><td><a href="../charts/valheim/README.md">valheim</a></td><td>0.4.2</td><td><pre><code class="language-sh">helm install valheim mbround18/valheim --namespace valheim --create-namespace</code></pre></td><td><pre><code class="language-sh">helm show values mbround18/valheim</code></pre></td></tr>
    <tr><td><a href="../charts/vein/README.md">vein</a></td><td>0.1.8</td><td><pre><code class="language-sh">helm install vein mbround18/vein --namespace vein --create-namespace</code></pre></td><td><pre><code class="language-sh">helm show values mbround18/vein</code></pre></td></tr>
    <tr><td><a href="../charts/wikijs/README.md">wikijs</a></td><td>0.2.21</td><td><pre><code class="language-sh">helm install wikijs mbround18/wikijs --namespace wikijs --create-namespace</code></pre></td><td><pre><code class="language-sh">helm show values mbround18/wikijs</code></pre></td></tr>
  </tbody>
</table>

<!-- CHARTS:END -->

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

## 📖 Documentation

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

## 🙏 Acknowledgments

- All contributors who have helped improve these charts
- The Helm and Kubernetes communities for excellent tooling
- Game developers whose servers we're hosting
- Users who report issues and provide feedback

## **Happy Gaming! 🎮**

If you find these charts useful, please ⭐ star the repository and share it with others!
