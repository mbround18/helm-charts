from pathlib import Path

import yaml

from charts.test_helpers import SNAPSHOT_NAMESPACE, render_chart_documents


def test_chart_rendering(snapshot):
    chart_path = Path(__file__).parent.parent
    rendered_templates = render_chart_documents(
        chart_path, namespace=SNAPSHOT_NAMESPACE
    )

    # The snapshot library expects a string, so we dump the yaml back to a string
    snapshot.assert_match(yaml.dump_all(rendered_templates), "chart_snapshot.yaml")
