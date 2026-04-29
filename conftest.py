from pathlib import Path
import sys
import asyncio
import yaml
import time
from typing import List

ROOT = Path(__file__).resolve().parent
root_str = str(ROOT)
if root_str not in sys.path:
    sys.path.insert(0, root_str)


async def build_chart_dependencies(
    chart_path: Path, semaphore: asyncio.Semaphore
) -> None:
    """Asynchronously build dependencies for a single chart, with concurrency limits and timing."""
    async with semaphore:
        start_time = time.perf_counter()

        proc = await asyncio.create_subprocess_exec(
            "helm",
            "dependency",
            "build",
            cwd=chart_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        elapsed_time = time.perf_counter() - start_time

        if proc.returncode != 0:
            raise RuntimeError(
                f"Failed to build dependencies for chart: {chart_path.name} (took {elapsed_time:.2f}s)\n"
                f"STDOUT: {stdout.decode()}\n"
                f"STDERR: {stderr.decode()}"
            )

        print(
            f"Successfully built dependencies for chart: {chart_path.name} in {elapsed_time:.2f}s"
        )


def pytest_sessionstart(session) -> None:
    """
    Build Helm chart dependencies asynchronously before running tests.
    This runs once before xdist distributes the tests.
    """
    charts_dir = ROOT / "charts"
    charts_to_build: List[Path] = []

    for chart_yaml_path in charts_dir.glob("*/Chart.yaml"):
        try:
            with open(chart_yaml_path, "r") as f:
                chart_yaml = yaml.safe_load(f) or {}

            if "dependencies" in chart_yaml:
                charts_to_build.append(chart_yaml_path.parent)
        except Exception as e:
            print(f"Warning: Failed to parse {chart_yaml_path}: {e}")

    async def main() -> None:
        # Limit concurrency to prevent CPU/Network overloading
        semaphore = asyncio.Semaphore(5)
        tasks = [
            build_chart_dependencies(chart, semaphore) for chart in charts_to_build
        ]
        await asyncio.gather(*tasks)

    if charts_to_build:
        print(f"Building dependencies for {len(charts_to_build)} chart(s)...")

        total_start = time.perf_counter()
        asyncio.run(main())
        total_elapsed = time.perf_counter() - total_start

        print(f"All chart dependencies built successfully in {total_elapsed:.2f}s")
