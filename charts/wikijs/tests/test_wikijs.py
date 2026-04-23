from pathlib import Path

from charts.test_helpers import render_chart_snapshot

def test_chart_rendering(snapshot):
    chart_path = Path(__file__).parent.parent

    snapshot.assert_match(
        render_chart_snapshot(chart_path, normalize_secrets=True),
        'chart_snapshot.yaml',
    )
