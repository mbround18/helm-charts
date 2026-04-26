import tarfile
from pathlib import Path

from tools import release_charts


def create_chart_package(tmp_path: Path, name: str, version: str) -> Path:
    chart_root = tmp_path / f"{name}-{version}"
    chart_root.mkdir()
    (chart_root / "Chart.yaml").write_text(
        (
            "apiVersion: v2\n"
            f"name: {name}\n"
            f"version: {version}\n"
            "description: demo chart\n"
        ),
        encoding="utf-8",
    )
    package_path = tmp_path / f"{name}-{version}.tgz"
    with tarfile.open(package_path, "w:gz") as archive:
        archive.add(chart_root, arcname=chart_root.name)
    return package_path


def test_load_chart_package_reads_embedded_chart_metadata(tmp_path: Path):
    package_path = create_chart_package(tmp_path, "demo", "1.2.3")

    package = release_charts.load_chart_package(package_path)

    assert package.name == "demo"
    assert package.version == "1.2.3"
    assert package.filename == "demo-1.2.3.tgz"
    assert package.digest
    assert package.metadata["description"] == "demo chart"


def test_merge_index_replaces_same_version_and_keeps_history(tmp_path: Path):
    package_path = create_chart_package(tmp_path, "demo", "1.2.0")
    package = release_charts.load_chart_package(package_path)

    existing_index = {
        "apiVersion": "v1",
        "entries": {
            "demo": [
                {
                    "name": "demo",
                    "version": "1.2.0",
                    "urls": ["https://old.example/demo-1.2.0.tgz"],
                },
                {
                    "name": "demo",
                    "version": "1.1.0",
                    "urls": ["https://old.example/demo-1.1.0.tgz"],
                },
            ]
        },
    }

    merged = release_charts.merge_index(existing_index, [package], "owner", "repo")

    assert merged["apiVersion"] == "v1"
    assert [entry["version"] for entry in merged["entries"]["demo"]] == [
        "1.2.0",
        "1.1.0",
    ]
    assert merged["entries"]["demo"][0]["urls"] == [
        "https://github.com/owner/repo/releases/download/demo-1.2.0/demo-1.2.0.tgz"
    ]
    assert merged["entries"]["demo"][1]["urls"] == [
        "https://old.example/demo-1.1.0.tgz"
    ]
