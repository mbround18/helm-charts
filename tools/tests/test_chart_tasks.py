import asyncio
from pathlib import Path

from tools import chart_tasks


def test_build_chart_packages_library_chart(tmp_path: Path, monkeypatch):
    chart_dir = tmp_path / "game-tools"
    chart_dir.mkdir()
    chart_yaml = chart_dir / "Chart.yaml"
    output_dir = tmp_path / "packages"
    output_dir.mkdir()
    commands: list[tuple[list[str], Path | None, bool]] = []

    async def fake_run_cmd(
        cmd: list[str], cwd: Path | None = None, quiet: bool = False
    ) -> str:
        commands.append((cmd, cwd, quiet))
        return ""

    monkeypatch.setattr(chart_tasks, "run_cmd", fake_run_cmd)

    chart = chart_tasks.Chart(
        name="game-tools",
        directory=chart_dir,
        chart_yaml=chart_yaml,
        chart_type="library",
        has_dependencies=False,
    )

    asyncio.run(chart_tasks.build_chart(chart, output_dir, asyncio.Semaphore(1)))

    assert commands == [
        (
            ["helm", "package", str(chart_dir), "-d", str(output_dir)],
            chart_tasks.REPO_ROOT,
            False,
        )
    ]
