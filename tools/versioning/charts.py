from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

import yaml

from tools.versioning.common import log


def list_chart_dirs(charts_root: Path) -> list[Path]:
    return sorted(
        path
        for path in charts_root.iterdir()
        if path.is_dir() and (path / "Chart.yaml").exists()
    )


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return data if isinstance(data, dict) else {}


def write_yaml(path: Path, data: dict) -> None:
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False)


def load_chart_version(chart_yaml: Path) -> Optional[str]:
    version = load_yaml(chart_yaml).get("version")
    return version if isinstance(version, str) else None


def write_chart_version(chart_yaml: Path, new_version: str) -> None:
    data = load_yaml(chart_yaml)
    data["version"] = new_version
    write_yaml(chart_yaml, data)


def sync_local_dependency_versions(
    charts_root: Path,
    bumped_versions: dict[str, str],
) -> list[Path]:
    updated_chart_dirs: list[Path] = []

    for chart_dir in list_chart_dirs(charts_root):
        chart_yaml = chart_dir / "Chart.yaml"
        if not chart_yaml.exists():
            continue

        data = load_yaml(chart_yaml)
        dependencies = data.get("dependencies")
        if not isinstance(dependencies, list):
            continue

        changed = False
        for dependency in dependencies:
            if not isinstance(dependency, dict):
                continue

            repository = dependency.get("repository")
            dependency_name = dependency.get("name")
            dependency_version = dependency.get("version")
            if not (
                isinstance(repository, str)
                and repository.startswith("file://")
                and isinstance(dependency_name, str)
                and isinstance(dependency_version, str)
            ):
                continue

            target_version = bumped_versions.get(dependency_name)
            if target_version and dependency_version != target_version:
                log(
                    "INFO",
                    (
                        f"Updating local dependency version in {chart_yaml}: "
                        f"{dependency_name} {dependency_version} -> {target_version}"
                    ),
                )
                dependency["version"] = target_version
                changed = True

        if changed:
            write_yaml(chart_yaml, data)
            updated_chart_dirs.append(chart_dir)

    return updated_chart_dirs


def refresh_dependency_locks(chart_dirs: list[Path]) -> list[Path]:
    updated_lockfiles: list[Path] = []

    for chart_dir in chart_dirs:
        lock_path = chart_dir / "Chart.lock"
        if not lock_path.exists():
            continue

        log("INFO", f"Refreshing dependency lock for {chart_dir.name}")
        subprocess.check_call(
            ["helm", "dependency", "build", "--skip-refresh", str(chart_dir)],
            cwd=str(chart_dir.parent.parent),
        )
        updated_lockfiles.append(lock_path)

    return updated_lockfiles
