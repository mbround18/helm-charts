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

    statefulset = _document_by_kind(documents, "StatefulSet")
    service = _document_by_kind(documents, "Service")

    assert "annotations" not in statefulset["metadata"]
    assert "annotations" not in service["metadata"]
    assert "argocd.argoproj.io/instance" not in statefulset["metadata"]["labels"]


def test_argocd_metadata_renders_when_application_api_is_available():
    documents = _render(api_versions=["argoproj.io/v1alpha1/Application"])

    statefulset = _document_by_kind(documents, "StatefulSet")
    service = _document_by_kind(documents, "Service")
    service_account = _document_by_kind(documents, "ServiceAccount")

    assert (
        statefulset["metadata"]["annotations"]["argocd.argoproj.io/sync-wave"] == "30"
    )
    assert service["metadata"]["annotations"]["argocd.argoproj.io/sync-wave"] == "40"
    assert (
        service_account["metadata"]["annotations"]["argocd.argoproj.io/sync-wave"]
        == "0"
    )


@pytest.mark.parametrize("jwt_secret", [True, False])
def test_argocd_force_mode_adds_instance_label(jwt_secret):
    documents = _render(
        values={
            "argoCd": {
                "mode": "enabled",
                "instanceLabel": "audiobookshelf-prod",
            },
            "secrets": {
                "jwt": {
                    "create": jwt_secret,
                    "name": "audiobookshelf-jwt",
                    "key": "JWT_SECRET_KEY",
                }
            },
        }
    )

    statefulset = _document_by_kind(documents, "StatefulSet")

    assert (
        statefulset["metadata"]["labels"]["argocd.argoproj.io/instance"]
        == "audiobookshelf-prod"
    )

    if jwt_secret:
        secret = _document_by_kind(documents, "Secret")
        assert secret["metadata"]["annotations"]["argocd.argoproj.io/sync-wave"] == "0"
