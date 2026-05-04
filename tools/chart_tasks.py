#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import logging
import py_compile
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import yaml

# Assuming this exists based on your provided script
try:
    from tools.fix_chart_deps import sync_local_dependencies
except ImportError:

    def sync_local_dependencies(path: str):
        pass


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("chart-tasks")

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

    @property
    def charts_dir(self) -> Path:
        return self.directory / "charts"


async def run_cmd(cmd: list[str], cwd: Path | None = None, quiet: bool = False) -> str:
    """Run a shell command asynchronously and return stdout."""
    process = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(cwd) if cwd else None,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        error_msg = stderr.decode().strip()
        logger.error(f"Command failed: {' '.join(cmd)}\n{error_msg}")
        raise subprocess.CalledProcessError(
            process.returncode, cmd, output=stdout, stderr=stderr
        )

    result = stdout.decode().strip()
    if not quiet and result:
        logger.debug(result)
    return result


def load_chart(path: Path) -> Chart:
    chart_yaml = path / "Chart.yaml"
    if not chart_yaml.exists():
        raise FileNotFoundError(f"No Chart.yaml found in {path}")

    with chart_yaml.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}

    chart_type = data.get("type", "application")
    dependencies = data.get("dependencies", [])
    has_dependencies = isinstance(dependencies, list) and len(dependencies) > 0

    return Chart(
        name=path.name,
        directory=path,
        chart_yaml=chart_yaml,
        chart_type=chart_type,
        has_dependencies=has_dependencies,
    )


def get_local_dependencies(chart_path: Path) -> list[tuple[str, Path]]:
    """Find local file:// dependencies in a Chart.yaml. Returns list of (declared_name, absolute_path)."""
    chart_yaml_path = chart_path / "Chart.yaml"
    if not chart_yaml_path.exists():
        return []

    with chart_yaml_path.open("r", encoding="utf-8") as h:
        data = yaml.safe_load(h) or {}

    dependencies = data.get("dependencies", [])
    local_deps = []
    for dep in dependencies:
        name = dep.get("name")
        repository = dep.get("repository", "")
        if repository.startswith("file://") and name:
            # Resolve relative path from the chart directory
            rel_path = repository.replace("file://", "")
            local_deps.append((name, (chart_path / rel_path).resolve()))

    return local_deps


async def ensure_local_deps_built(chart_path: Path, visited: set[Path] | None = None):
    """Recursively ensure all local file:// dependencies have their charts/ folders built."""
    if visited is None:
        visited = set()

    if chart_path in visited:
        return
    visited.add(chart_path)

    local_deps = get_local_dependencies(chart_path)
    for declared_name, dep_path in local_deps:
        if not dep_path.exists():
            logger.warning(f"Local dependency path does not exist: {dep_path}")
            continue

        # Check if the name in the dependency's Chart.yaml matches the declared name
        dep_chart_yaml = dep_path / "Chart.yaml"
        if dep_chart_yaml.exists():
            with dep_chart_yaml.open("r", encoding="utf-8") as h:
                dep_data = yaml.safe_load(h) or {}
                actual_name = dep_data.get("name")
                if actual_name and actual_name != declared_name:
                    logger.error(
                        f"Dependency name mismatch in {chart_path.name}: "
                        f"Expected '{declared_name}' based on directory/declaration, "
                        f"but local Chart.yaml at {dep_path} defines it as '{actual_name}'."
                    )
                    raise ValueError(
                        f"Chart name mismatch for dependency: {declared_name}"
                    )

        # Recursive check for the dependency's own local dependencies
        await ensure_local_deps_built(dep_path, visited)

        # Build the dependency itself
        logger.info(f"Building local dependency: {dep_path.name}")
        try:
            await run_cmd(
                ["helm", "dependency", "build", "--skip-refresh", "."],
                cwd=dep_path,
                quiet=True,
            )
        except subprocess.CalledProcessError:
            logger.error(f"Failed to build local dependency: {dep_path.name}")
            raise


def discover_charts(charts_root: Path, selected: Sequence[str]) -> list[Chart]:
    selected_names = set(selected)
    charts = []
    # Search for Chart.yaml files and ensure the directory has a 'charts' folder
    for chart_yaml in sorted(charts_root.glob("*/Chart.yaml")):
        chart_dir = chart_yaml.parent

        # Ensure 'charts' directory and .gitkeep exist
        charts_subdir = chart_dir / "charts"
        charts_subdir.mkdir(exist_ok=True)
        (charts_subdir / ".gitkeep").touch(exist_ok=True)

        chart = load_chart(chart_dir)
        if selected_names and chart.name not in selected_names:
            continue
        charts.append(chart)

    return charts


async def update_dependencies(chart: Chart, semaphore: asyncio.Semaphore):
    async with semaphore:
        if chart.is_library or not chart.has_dependencies:
            return

        sync_local_dependencies(str(chart.chart_yaml))

        # Pre-build local file:// dependencies
        await ensure_local_deps_built(chart.directory)

        logger.info(f"Updating dependencies: {chart.name}")
        await run_cmd(
            ["helm", "dependency", "update", "--skip-refresh", "."], cwd=chart.directory
        )


async def lint_chart(chart: Chart, semaphore: asyncio.Semaphore):
    async with semaphore:
        logger.info(f"Linting: {chart.name}")
        if chart.has_dependencies:
            await ensure_local_deps_built(chart.directory)
            await run_cmd(
                ["helm", "dependency", "build", "--skip-refresh", "."],
                cwd=chart.directory,
                quiet=True,
            )
        await run_cmd(["helm", "lint", "."], cwd=chart.directory, quiet=True)


async def dump_chart(chart: Chart, output_dir: Path, semaphore: asyncio.Semaphore):
    async with semaphore:
        if chart.is_library:
            return

        logger.info(f"Dumping manifests: {chart.name}")
        if chart.has_dependencies:
            await ensure_local_deps_built(chart.directory)
            await run_cmd(
                ["helm", "dependency", "build", "--skip-refresh", "."],
                cwd=chart.directory,
                quiet=True,
            )

        rendered = await run_cmd(
            ["helm", "template", "."], cwd=chart.directory, quiet=True
        )

        chart_out = output_dir / chart.name
        chart_out.mkdir(parents=True, exist_ok=True)

        # Split manifests by '---'
        docs = [d for d in rendered.split("\n---\n") if d.strip()]
        for idx, doc in enumerate(docs):
            source_line = next(
                (line for line in doc.splitlines() if line.startswith("# Source:")),
                None,
            )
            if source_line:
                # Extract path after /templates/
                rel_path = source_line.split("/templates/")[-1].strip()
                target = chart_out / rel_path
            else:
                target = chart_out / f"manifest-{idx:03}.yaml"

            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(doc.strip() + "\n", encoding="utf-8")


async def build_chart(chart: Chart, output_dir: Path, semaphore: asyncio.Semaphore):
    async with semaphore:
        logger.info(f"Packaging: {chart.name}")
        if chart.has_dependencies:
            # Pre-build local dependencies before the main chart build
            await ensure_local_deps_built(chart.directory)

            # Build dependencies into the charts/ directory
            await run_cmd(
                ["helm", "dependency", "build", "--skip-refresh", "."],
                cwd=chart.directory,
                quiet=True,
            )

        # Run from REPO_ROOT and use absolute output_dir
        await run_cmd(
            ["helm", "package", str(chart.directory), "-d", str(output_dir)],
            cwd=REPO_ROOT,
        )


async def validate_repo(repo_root: Path, manifest_pytest_args: Sequence[str]):
    logger.info("Validating Python syntax...")
    python_files = [
        p
        for p in repo_root.rglob("*.py")
        if ".venv" not in p.parts and not p.name.startswith(".")
    ]

    for pf in python_files:
        try:
            py_compile.compile(str(pf), doraise=True)
        except Exception as e:
            logger.error(f"Syntax error in {pf}: {e}")
            sys.exit(1)

    logger.info(f"Running pytest: {' '.join(manifest_pytest_args)}")
    process = await asyncio.create_subprocess_exec(
        "uv", "run", "pytest", *manifest_pytest_args, cwd=str(repo_root)
    )
    await process.wait()
    if process.returncode != 0:
        sys.exit(process.returncode)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Async Helm chart repository tasks.")
    parser.add_argument(
        "command", choices=["lint", "dump", "deps-update", "build", "validate"]
    )
    parser.add_argument("--jobs", type=int, default=8, help="Max concurrent tasks.")
    parser.add_argument("--charts-root", type=Path, default=DEFAULT_CHARTS_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument(
        "--manifest-pytest-args",
        nargs="*",
        default=["charts/tests/test_manifest_contracts.py"],
    )
    parser.add_argument("charts", nargs="*", help="Specific charts to process.")
    return parser.parse_args()


async def main():
    args = parse_args()
    semaphore = asyncio.Semaphore(args.jobs)

    if args.command == "validate":
        await validate_repo(args.repo_root, args.manifest_pytest_args)
        return

    if args.command in ["deps-update", "build"]:
        logger.info("Updating helm repositories...")
        try:
            await run_cmd(["helm", "repo", "update"])
        except subprocess.CalledProcessError:
            logger.error("Failed to update helm repositories. Aborting.")
            sys.exit(1)

    charts = discover_charts(args.charts_root, args.charts)
    if not charts:
        logger.warning("No charts found.")
        return

    tasks = []
    if args.command == "lint":
        tasks = [lint_chart(c, semaphore) for c in charts]
    elif args.command == "deps-update":
        tasks = [update_dependencies(c, semaphore) for c in charts]
    elif args.command == "dump":
        shutil.rmtree(args.output_dir, ignore_errors=True)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        tasks = [dump_chart(c, args.output_dir, semaphore) for c in charts]
    elif args.command == "build":
        args.output_dir.mkdir(parents=True, exist_ok=True)
        tasks = [build_chart(c, args.output_dir, semaphore) for c in charts]

    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for res in results:
            if isinstance(res, Exception):
                logger.error(f"Task failed with error: {res}")
                sys.exit(1)

    if args.command == "build":
        logger.info(f"Build complete. Artifacts in {args.output_dir}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(1)
