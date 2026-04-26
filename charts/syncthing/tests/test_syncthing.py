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
    rendered_templates = render_chart_documents(
        chart_path, namespace=SNAPSHOT_NAMESPACE
    )

    # The snapshot library expects a string, so we dump the yaml back to a string
    snapshot.assert_match(yaml.dump_all(rendered_templates), "chart_snapshot.yaml")


def test_argocd_metadata_is_not_rendered_by_default():
    documents = _render()

    statefulset = _document_by_kind(documents, "StatefulSet")
    http_service = next(
        document
        for document in documents
        if document.get("metadata", {}).get("name", "").endswith("-http")
    )

    assert "annotations" not in statefulset["metadata"]
    assert "annotations" not in http_service["metadata"]
    assert "argocd.argoproj.io/instance" not in statefulset["metadata"]["labels"]


def test_argocd_metadata_renders_when_application_api_is_available():
    documents = _render(api_versions=["argoproj.io/v1alpha1/Application"])

    statefulset = _document_by_kind(documents, "StatefulSet")
    service_account = _document_by_kind(documents, "ServiceAccount")
    services = [
        document
        for document in documents
        if isinstance(document, dict) and document.get("kind") == "Service"
    ]

    assert (
        statefulset["metadata"]["annotations"]["argocd.argoproj.io/sync-wave"] == "30"
    )
    assert (
        service_account["metadata"]["annotations"]["argocd.argoproj.io/sync-wave"]
        == "0"
    )
    assert {
        service["metadata"]["annotations"]["argocd.argoproj.io/sync-wave"]
        for service in services
    } == {"40"}


@pytest.mark.parametrize("password_secret", [True, False])
def test_argocd_force_mode_adds_instance_label(password_secret):
    documents = _render(
        values={
            "argoCd": {
                "mode": "enabled",
                "instanceLabel": "syncthing-prod",
            },
            "secrets": {
                "password": {
                    "create": password_secret,
                    "name": "syncthing-password",
                    "key": "PASSWORD",
                }
            },
        }
    )

    statefulset = _document_by_kind(documents, "StatefulSet")

    assert (
        statefulset["metadata"]["labels"]["argocd.argoproj.io/instance"]
        == "syncthing-prod"
    )

    if password_secret:
        secret = _document_by_kind(documents, "Secret")
        assert secret["metadata"]["annotations"]["argocd.argoproj.io/sync-wave"] == "0"
