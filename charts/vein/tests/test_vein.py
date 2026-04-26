from pathlib import Path

import pytest

from charts.test_helpers import DEFAULT_NAMESPACE, render_chart_documents


def _render(values=None, api_versions=None):
    chart_path = Path(__file__).parent.parent
    return render_chart_documents(
        chart_path,
        namespace=DEFAULT_NAMESPACE,
        values=values,
        api_versions=api_versions,
    )


def _document_by_kind(documents, kind):
    return next(document for document in documents if document.get("kind") == kind)


def test_argocd_metadata_is_not_rendered_by_default():
    documents = _render()

    service_account = _document_by_kind(documents, "ServiceAccount")
    statefulset = _document_by_kind(documents, "StatefulSet")

    assert all(document.get("kind") != "Service" for document in documents)
    assert "annotations" not in service_account["metadata"]
    assert "annotations" not in statefulset["metadata"]
    assert "argocd.argoproj.io/instance" not in statefulset["metadata"]["labels"]


def test_argocd_metadata_renders_when_application_api_is_available():
    documents = _render(api_versions=["argoproj.io/v1alpha1/Application"])

    statefulset = _document_by_kind(documents, "StatefulSet")
    service_account = _document_by_kind(documents, "ServiceAccount")

    assert (
        statefulset["metadata"]["annotations"]["argocd.argoproj.io/sync-wave"] == "30"
    )
    assert (
        service_account["metadata"]["annotations"]["argocd.argoproj.io/sync-wave"]
        == "0"
    )


@pytest.mark.parametrize("bind_to_node", [True, False])
def test_argocd_force_mode_adds_instance_label_for_service_and_statefulset(
    bind_to_node,
):
    documents = _render(
        values={
            "argoCd": {
                "mode": "enabled",
                "instanceLabel": "vein-prod",
                "commonLabels": {
                    "gitops.tool": "argocd",
                },
            },
            "service": {
                "bindToNode": bind_to_node,
            },
        }
    )

    statefulset = _document_by_kind(documents, "StatefulSet")

    assert (
        statefulset["metadata"]["labels"]["argocd.argoproj.io/instance"] == "vein-prod"
    )
    assert statefulset["metadata"]["labels"]["gitops.tool"] == "argocd"

    if bind_to_node:
        assert all(document.get("kind") != "Service" for document in documents)
    else:
        service = _document_by_kind(documents, "Service")
        assert (
            service["metadata"]["labels"]["argocd.argoproj.io/instance"] == "vein-prod"
        )
        assert (
            service["metadata"]["annotations"]["argocd.argoproj.io/sync-wave"] == "40"
        )


def test_argocd_auto_detection_applies_to_nodeport_service_when_service_is_enabled():
    documents = _render(
        values={
            "service": {
                "bindToNode": False,
            },
        },
        api_versions=["argoproj.io/v1alpha1/Application"],
    )

    service = _document_by_kind(documents, "Service")

    assert service["metadata"]["annotations"]["argocd.argoproj.io/sync-wave"] == "40"
