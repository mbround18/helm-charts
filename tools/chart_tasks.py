#!/usr/bin/env python3
from __future__ import annotations

import argparse
import py_compile
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Sequence

import yaml

from tools.fix_chart_deps import sync_local_dependencies


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CHARTS_ROOT = REPO_ROOT / "charts"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "tmp"


@dataclass(frozen=True)
class Chart:
    name: str
    directory: Path
    chart_yaml: Path
    chart_type: str
    has_dependencies: bool

    @property
    def lockfile(self) -> Path:
        return self.directory / "Chart.lock"

    @property
    def is_library(self) -> bool:
        return self.chart_type == "library"


def load_chart(path: Path) -> Chart:
    chart_yaml = path / "Chart.yaml"
    with chart_yaml.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}

    chart_type = (
        data.get("type") if isinstance(data.get("type"), str) else "application"
    )
    dependencies = data.get("dependencies")
    has_dependencies = isinstance(dependencies, list) and len(dependencies) > 0
    return Chart(
        name=path.name,
        directory=path,
        chart_yaml=chart_yaml,
        chart_type=chart_type,
        has_dependencies=has_dependencies,
    )


def discover_charts(charts_root: Path, selected: Sequence[str]) -> list[Chart]:
    selected_names = set(selected)
    charts = []
    for chart_yaml in sorted(charts_root.glob("*/Chart.yaml")):
        chart = load_chart(chart_yaml.parent)
        if selected_names and chart.name not in selected_names:
            continue
        charts.append(chart)

    return charts


def run_command(
    command: list[str], cwd: Path | None = None, quiet: bool = False
) -> str:
    result = subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        check=True,
        capture_output=quiet,
        text=True,
    )
    return result.stdout if quiet else ""


def ensure_lockfile(chart: Chart) -> None:
    if chart.has_dependencies and not chart.lockfile.exists():
        raise FileNotFoundError(f"Missing {chart.lockfile}. Run make deps-update.")


def build_vendored_dependencies(chart: Chart, quiet: bool = False) -> None:
    if not chart.has_dependencies or chart.is_library:
        return

    ensure_lockfile(chart)
    run_command(
        ["helm", "dependency", "build", "--skip-refresh", str(chart.directory)],
        cwd=REPO_ROOT,
        quiet=quiet,
    )


def update_dependencies(chart: Chart) -> None:
    if chart.is_library or not chart.has_dependencies:
        return

    sync_local_dependencies(str(chart.chart_yaml))
    print(f"Updating dependencies for {chart.name}...")
    run_command(["helm", "dependency", "update", str(chart.directory)], cwd=REPO_ROOT)


def lint_chart(chart: Chart) -> None:
    build_vendored_dependencies(chart, quiet=True)
    print(f"Linting {chart.name}")
    run_command(["helm", "lint", str(chart.directory)], cwd=REPO_ROOT, quiet=True)


def split_manifests(rendered: str, out_dir: Path) -> None:
    documents: list[str] = []
    current: list[str] = []

    for line in rendered.splitlines(keepends=True):
        if line.strip() == "---":
            documents.append("".join(current))
            current = []
            continue
        current.append(line)
    documents.append("".join(current))

    index = 0
    for document in documents:
        if not document.strip():
            continue

        source_path = None
        for line in document.splitlines():
            if line.startswith("# Source:"):
                source_path = line[len("# Source:") :].strip()
                break

        if source_path:
            parts = source_path.split("/templates/", 1)
            relative_path = Path(parts[1] if len(parts) == 2 else source_path)
        else:
            relative_path = Path(f"manifest-{index:02d}.yaml")

        target_path = out_dir / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(document, encoding="utf-8")
        index += 1


def dump_chart(chart: Chart, output_dir: Path) -> None:
    if chart.is_library:
        print(f"Skipping library chart: {chart.name}")
        return

    build_vendored_dependencies(chart)
    print(f"Dumping {chart.name}...")
    rendered = run_command(
        ["helm", "template", str(chart.directory)],
        cwd=REPO_ROOT,
        quiet=True,
    )
    chart_output_dir = output_dir / chart.name
    chart_output_dir.mkdir(parents=True, exist_ok=True)
    split_manifests(rendered, chart_output_dir)


def build_chart(chart: Chart, output_dir: Path) -> None:
    if chart.is_library:
        print(f"Skipping library chart: {chart.name}")
        return

    build_vendored_dependencies(chart)
    print(f"Building {chart.name}...")
    run_command(
        ["helm", "package", str(chart.directory), "-d", str(output_dir)], cwd=REPO_ROOT
    )


def run_parallel(
    charts: Iterable[Chart], jobs: int, handler: Callable[[Chart], None]
) -> None:
    failures: list[tuple[str, Exception]] = []

    with ThreadPoolExecutor(max_workers=max(1, jobs)) as executor:
        futures = {executor.submit(handler, chart): chart for chart in charts}
        for future in as_completed(futures):
            chart = futures[future]
            try:
                future.result()
            except Exception as exc:  # noqa: BLE001
                failures.append((chart.name, exc))

    if failures:
        for chart_name, error in failures:
            print(f"ERROR: {chart_name}: {error}")
        raise SystemExit(1)


def discover_python_files(repo_root: Path) -> list[Path]:
    python_files: list[Path] = []
    for path in repo_root.rglob("*.py"):
        relative = path.relative_to(repo_root)
        if ".venv" in relative.parts:
            continue
        if any(part.startswith(".") for part in relative.parts):
            continue
        python_files.append(path)
    return sorted(python_files)


def validate_repo(
    repo_root: Path, jobs: int, manifest_pytest_args: Sequence[str]
) -> None:
    print("Checking Python syntax...")
    failures: list[tuple[Path, Exception]] = []
    python_files = discover_python_files(repo_root)

    with ThreadPoolExecutor(max_workers=max(1, jobs)) as executor:
        futures = {
            executor.submit(py_compile.compile, str(path), doraise=True): path
            for path in python_files
        }
        for future in as_completed(futures):
            path = futures[future]
            try:
                future.result()
            except Exception as exc:  # noqa: BLE001
                failures.append((path, exc))

    if failures:
        for path, error in failures:
            print(f"ERROR: {path.relative_to(repo_root)}: {error}")
        raise SystemExit(1)

    print(
        f"Validating rendered manifests with pytest ({' '.join(manifest_pytest_args)})"
    )
    subprocess.check_call(
        ["uv", "run", "pytest", *manifest_pytest_args], cwd=str(repo_root)
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run shared Helm chart repository tasks."
    )
    parser.add_argument(
        "command", choices=["lint", "dump", "deps-update", "build", "validate"]
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=4,
        help="Maximum number of charts to process concurrently.",
    )
    parser.add_argument(
        "--charts-root",
        type=Path,
        default=DEFAULT_CHARTS_ROOT,
        help="Directory that contains chart subdirectories.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Output directory for dump and build commands.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT,
        help="Repository root used for validation commands.",
    )
    parser.add_argument(
        "--manifest-pytest-args",
        nargs="*",
        default=["charts/tests/test_manifest_contracts.py"],
        help="Arguments passed to pytest for manifest validation.",
    )
    parser.add_argument(
        "charts",
        nargs="*",
        help="Optional chart names to limit the command to a subset of charts.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.command == "validate":
        validate_repo(args.repo_root, args.jobs, args.manifest_pytest_args)
        return 0

    charts = discover_charts(args.charts_root, args.charts)
    if not charts:
        print("No charts matched the requested selection.")
        return 0

    if args.command == "lint":
        run_parallel(charts, args.jobs, lint_chart)
        return 0

    if args.command == "deps-update":
        for chart in charts:
            update_dependencies(chart)
        return 0

    if args.command == "dump":
        shutil.rmtree(args.output_dir, ignore_errors=True)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        run_parallel(
            charts, args.jobs, lambda chart: dump_chart(chart, args.output_dir)
        )
        return 0

    if args.command == "build":
        args.output_dir.mkdir(parents=True, exist_ok=True)
        run_parallel(
            charts, args.jobs, lambda chart: build_chart(chart, args.output_dir)
        )
        print(f"Packaged charts available in {args.output_dir}")
        return 0

    raise SystemExit(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
