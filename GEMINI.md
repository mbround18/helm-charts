# Gemini Agent Guidelines for helm-charts Repository

This document provides guidance for the Gemini agent when interacting with the `helm-charts` repository. It outlines the project structure, conventions, and common tasks to help the agent operate effectively and adhere to project standards.

## Project Overview

This repository hosts a collection of Helm charts for various applications. Each chart resides in its own subdirectory under `charts/`. The repository also includes tooling, documentation, and GitHub Actions workflows to manage and maintain these charts.

## Key Directories

*   `.github/`: Contains GitHub Actions workflows for CI/CD, as well as utility scripts and action definitions.
*   `charts/`: The core directory containing all Helm charts. Each subdirectory here is an independent Helm chart.
    *   `charts/<chart-name>/`: Individual Helm chart directories. Expect to find `Chart.yaml`, `values.yaml`, `templates/`, `README.md`, and potentially a `Makefile` or `Chart.lock`.
*   `docs/`: Project documentation, including contribution guidelines and specific guides.
*   `tools/`: Python scripts for various automation tasks related to chart management (e.g., validation, README updates).

## Observed Conventions and Technologies

*   **Helm:** All charts follow Helm 3 best practices.
*   **YAML:** Configuration and templating heavily rely on YAML syntax.
*   **Python:** Used for repository tooling, often managed with `uv` and `pyproject.toml`. Expect `ruff` for linting.
*   **Makefiles:** Used for common development tasks within the root, `config/`, and individual chart directories.
*   **Git:** Standard Git workflow for version control.
*   **GitHub Actions:** CI/CD is managed through workflows in `.github/workflows/`.

## Common Tasks for Gemini

When working in this repository, the Gemini agent may be asked to perform tasks such as:

1.  **Chart Development:**
    *   Creating new Helm charts.
    *   Modifying existing `Chart.yaml` or `values.yaml` files.
    *   Updating or adding new templates in `charts/<chart-name>/templates/`.
    *   Ensuring `NOTES.txt` and `README.md` are up-to-date.
2.  **Linting and Testing:**
    *   Running `helm lint` on charts.
    *   Executing `make test` or similar commands found in `Makefiles` for testing.
    *   Using Python-based tools in `tools/` for validation.
3.  **Dependency Management:**
    *   Updating chart dependencies (`helm dependency update`).
    *   Managing Python dependencies with `uv`.
4.  **Documentation Updates:**
    *   Modifying `README.md` files for charts or the main repository.
    *   Updating `docs/` content.
5.  **Automation Scripting:**
    *   Modifying or creating Python scripts in `tools/`.
    *   Adjusting GitHub Actions workflows.

## General Guidelines

*   **Respect Existing Structure:** Adhere to the established directory structure and file locations.
*   **Helm Best Practices:** When modifying charts, follow Helm's recommended best practices.
*   **YAML Formatting:** Maintain consistent YAML formatting and indentation.
*   **Python Standards:** For Python scripts, follow PEP 8 and respect `ruff` configurations.
*   **Makefile Usage:** Leverage existing `Makefile` targets where appropriate for common operations.
*   **Testing:** Whenever making changes, consider if corresponding tests (e.g., `helm template` checks, Python unit tests) need to be updated or added.
*   **Documentation:** Keep documentation (especially `README.md` files) accurate and up-to-date with any changes.
