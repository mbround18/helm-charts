import asyncio
from pathlib import Path

from tools import upgrade


def test_save_yaml_preserves_existing_quotes(tmp_path: Path):
    values_path = tmp_path / "values.yaml"
    values_path.write_text(
        """
image:
  repository: busybox
  tag: "1.37"
backups:
  schedule: "0 2 * * *"
  image: "mbround18/backup-cron:latest"
""".lstrip(),
        encoding="utf-8",
    )

    values_data = upgrade.load_yaml_file(values_path)
    values_data["image"]["tag"] = upgrade.apply_scalar_style(
        "1.38", values_data["image"]["tag"]
    )

    upgrade.save_yaml_file(values_path, values_data)
    rendered = values_path.read_text(encoding="utf-8")

    assert 'tag: "1.38"' in rendered
    assert 'schedule: "0 2 * * *"' in rendered
    assert 'image: "mbround18/backup-cron:latest"' in rendered


def test_save_chart_yaml_keeps_icon_inline_and_app_version_quoted(tmp_path: Path):
    chart_path = tmp_path / "Chart.yaml"
    chart_path.write_text(
        """
apiVersion: v2
name: demo
icon: https://example.com/logo.png
version: 0.1.0
appVersion: "main"
""".lstrip(),
        encoding="utf-8",
    )

    chart_data = upgrade.load_yaml_file(chart_path)
    chart_data["appVersion"] = upgrade.apply_scalar_style(
        "v1.2.3", chart_data["appVersion"]
    )

    upgrade.save_yaml_file(chart_path, chart_data)
    rendered = chart_path.read_text(encoding="utf-8")

    assert "icon: https://example.com/logo.png" in rendered
    assert 'appVersion: "v1.2.3"' in rendered


def test_get_latest_stable_tag_honors_min_age():
    now = upgrade.datetime.datetime.now(upgrade.datetime.timezone.utc)

    tags = [
        ("v1.0.0", now - upgrade.datetime.timedelta(days=30)),
        ("v1.1.0", now - upgrade.datetime.timedelta(days=2)),
        ("latest", now - upgrade.datetime.timedelta(days=100)),
    ]

    assert upgrade.get_latest_stable_tag(tags, min_age_days=14) == "v1.0.0"


def test_parse_args_supports_multiple_chart_paths():
    args = upgrade.parse_args(["charts/one", "charts/two", "--chart-concurrency", "2"])

    assert args.chart_paths == [Path("charts/one"), Path("charts/two")]
    assert args.chart_concurrency == 2
    assert args.image_concurrency == 8


def test_process_chart_async_updates_single_image_chart(tmp_path: Path, monkeypatch):
    chart_dir = tmp_path / "demo"
    chart_dir.mkdir()

    (chart_dir / "Chart.yaml").write_text(
        """
apiVersion: v2
name: demo
version: 0.1.0
appVersion: "1.37"
""".lstrip(),
        encoding="utf-8",
    )
    (chart_dir / "values.yaml").write_text(
        """
image:
  repository: busybox
  tag: "1.37"
""".lstrip(),
        encoding="utf-8",
    )

    now = upgrade.datetime.datetime.now(upgrade.datetime.timezone.utc)
    monkeypatch.setattr(
        upgrade,
        "get_docker_hub_tags",
        lambda repository: [("1.38", now - upgrade.datetime.timedelta(days=30))],
    )

    exit_code, logs = asyncio.run(
        upgrade.process_chart(
            chart_dir, min_tag_age_days=14, image_semaphore=asyncio.Semaphore(4)
        )
    )

    assert exit_code == 0
    assert any("Found new version: 1.38" in line for line in logs)
    assert 'tag: "1.38"' in (chart_dir / "values.yaml").read_text(encoding="utf-8")
    assert 'appVersion: "1.38"' in (chart_dir / "Chart.yaml").read_text(
        encoding="utf-8"
    )
