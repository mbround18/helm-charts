import subprocess
from pathlib import Path

import pytest
import yaml

def test_chart_rendering(snapshot):
    chart_path = Path(__file__).parent.parent
    if "type: library" in (chart_path / "Chart.yaml").read_text(encoding="utf-8"):
        pytest.skip("Library charts are not renderable with helm template")

    command = [
        "helm", "template", "release-name", str(chart_path)
    ]
    
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    
    rendered_templates = list(yaml.safe_load_all(result.stdout))
    
    # The snapshot library expects a string, so we dump the yaml back to a string
    snapshot.assert_match(yaml.dump_all(rendered_templates), 'chart_snapshot.yaml')
