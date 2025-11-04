# Helm Charts Repository

[![Helm Validation](https://github.com/mbround18/helm-charts/actions/workflows/helm.yml/badge.svg)](https://github.com/mbround18/helm-charts/actions/workflows/helm.yml)

Welcome to our Helm Charts Repository, hosted with ❤️ by GitHub Pages. This repository contains a collection of Helm charts for various applications, ready to be deployed in your Kubernetes cluster with ease and efficiency.

## Getting Started

Helm is a package manager for Kubernetes that allows you to manage Kubernetes applications. Helm Charts help you define, install, and upgrade even the most complex Kubernetes application.

### Prerequisites

- Kubernetes cluster
- Helm 3 installed

If you're new to Helm, please follow the [official Helm installation guide](https://helm.sh/docs/intro/install/) to get started.

### Adding Repo

To add this Helm repository to your Helm client:

```shell
helm repo add mbround18 https://mbround18.github.io/helm-charts/
```

### Installing Charts

To install a chart from this repository:

```shell
helm install my-release mbround18/<chart-name>
```

Replace `<chart-name>` with the name of the chart you wish to install.

### Searching for Charts

To search for charts in this repository:

```shell
helm search repo mbround18
```

## Available Charts

- **Palworld**: Palworld server.
- _Add more charts as necessary._

For more information on each chart, please refer to the individual chart's README within the repository.

## Contributing

We welcome contributions! Please read our [CONTRIBUTING.md](CONTRIBUTING.md) for details on how to submit contributions, report issues, and make suggestions.

## Contact

For any further questions or feedback, please [open an issue](https://github.com/mbround18/helm-charts/issues) in the GitHub repository.

Thank you for using our Helm Charts!

---

This template is a starting point. Be sure to customize each section, especially the "Available Charts" section, with the specific details of the charts in your repository. If your repository has additional requirements or instructions, include those as well.
