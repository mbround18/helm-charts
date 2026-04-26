from pathlib import Path

from tools.manager import VersionBumpManager
from tools.versioning.models import VersionBumpConfig


def test_plan_chart_update_skips_library_chart(tmp_path: Path):
    charts_root = tmp_path / "charts"
    chart_dir = charts_root / "game-tools"
    chart_dir.mkdir(parents=True)
    chart_yaml = chart_dir / "Chart.yaml"
    chart_yaml.write_text(
        """
apiVersion: v2
name: game-tools
type: library
version: 0.1.0
""".lstrip(),
        encoding="utf-8",
    )

    config = VersionBumpConfig(
        repo_root=tmp_path,
        charts_root=charts_root,
        dry_run=False,
        push_changes=False,
        fetch_tags=False,
        owner_repo="",
        github_token=None,
        summary_file=None,
    )
    manager = VersionBumpManager(config)

    update = manager._plan_chart_update(
        chart_dir,
        {"game-tools": ("game-tools-0.1.0", "0.1.0", (0, 1, 0))},
    )

    assert update is None
