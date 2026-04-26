
from pathlib import Path

import yaml
import pytest

from charts.test_helpers import SNAPSHOT_NAMESPACE, render_chart_documents


def _render(values=None, api_versions=None):
    chart_path = Path(__file__).parent.parent
    return render_chart_documents(
        chart_path,
        namespace=SNAPSHOT_NAMESPACE,
        values=values,
        api_versions=api_versions,
    )


def _document_by_kind(documents, kind):
    return next(document for document in documents if document.get("kind") == kind)


def test_chart_rendering(snapshot):
    chart_path = Path(__file__).parent.parent
    rendered_templates = render_chart_documents(chart_path, namespace=SNAPSHOT_NAMESPACE)
    
    # The snapshot library expects a string, so we dump the yaml back to a string
    snapshot.assert_match(yaml.dump_all(rendered_templates), 'chart_snapshot.yaml')


def test_argocd_metadata_is_not_rendered_by_default():
    documents = _render()

    statefulset = _document_by_kind(documents, "StatefulSet")
    service = _document_by_kind(documents, "Service")

    assert "annotations" not in statefulset["metadata"]
    assert "annotations" not in service["metadata"]
    assert "argocd.argoproj.io/instance" not in statefulset["metadata"]["labels"]


def test_argocd_metadata_renders_when_application_api_is_available():
    documents = _render(api_versions=["argoproj.io/v1alpha1/Application"])

    statefulset = _document_by_kind(documents, "StatefulSet")
    service_account = _document_by_kind(documents, "ServiceAccount")
    service = _document_by_kind(documents, "Service")

    assert statefulset["metadata"]["annotations"]["argocd.argoproj.io/sync-wave"] == "30"
    assert service_account["metadata"]["annotations"]["argocd.argoproj.io/sync-wave"] == "0"
    assert service["metadata"]["annotations"]["argocd.argoproj.io/sync-wave"] == "40"


@pytest.mark.parametrize(
    ("values", "expected_kind", "expected_wave"),
    [
        ({"ingress": {"enabled": True}}, "Ingress", "40"),
        ({"istio": {"enabled": True, "gateway": {"selector": {"istio": "ingress"}}}}, "VirtualService", "40"),
        ({"backup_cleanup": {"enabled": True}}, "CronJob", "20"),
    ],
)
def test_argocd_force_mode_applies_expected_phase_annotations(values, expected_kind, expected_wave):
    documents = _render(
        values={
            "argoCd": {
                "mode": "enabled",
                "instanceLabel": "foundry-prod",
            },
            **values,
        }
    )

    resource = _document_by_kind(documents, expected_kind)
    statefulset = _document_by_kind(documents, "StatefulSet")

    assert statefulset["metadata"]["labels"]["argocd.argoproj.io/instance"] == "foundry-prod"
    assert resource["metadata"]["annotations"]["argocd.argoproj.io/sync-wave"] == expected_wave
