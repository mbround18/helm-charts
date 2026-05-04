from tools import update_readme_charts


def test_build_table_includes_library_charts_with_dependency_usage(tmp_path):
    charts_root = tmp_path / "charts"
    charts_root.mkdir()

    library_chart = charts_root / "game-tools"
    library_chart.mkdir()
    (library_chart / "Chart.yaml").write_text(
        ("apiVersion: v2\nname: game-tools\ntype: library\nversion: 0.1.6\n"),
        encoding="utf-8",
    )

    app_chart = charts_root / "vein"
    app_chart.mkdir()
    (app_chart / "Chart.yaml").write_text(
        ("apiVersion: v2\nname: vein\nversion: 0.1.12\n"),
        encoding="utf-8",
    )

    table = update_readme_charts.build_table(str(charts_root))

    assert "<th>type</th>" in table
    assert "game-tools" in table
    assert "<td>library</td>" in table
    assert "repository: https://mbround18.github.io/helm-charts/" in table
    assert "helm install vein mbround18/vein" in table
