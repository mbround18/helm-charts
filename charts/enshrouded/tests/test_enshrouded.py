
import subprocess
import yaml
from pathlib import Path

def test_chart_rendering(snapshot):
    chart_path = Path(__file__).parent.parent
    command = [
        "helm", "template", "release-name", str(chart_path)
    ]
    
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    
    rendered_templates = list(yaml.safe_load_all(result.stdout))
    
    # The snapshot library expects a string, so we dump the yaml back to a string
    snapshot.assert_match(yaml.dump_all(rendered_templates), 'chart_snapshot.yaml')
