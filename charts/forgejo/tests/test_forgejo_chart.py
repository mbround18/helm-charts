from pathlib import Path

import pytest
from ruamel.yaml import YAML

from charts.test_helpers import DEFAULT_NAMESPACE, render_chart_documents

yaml = YAML()


@pytest.fixture
def chart_path():
    return Path(__file__).parent.parent


def _render(chart_path, values=None, api_versions=None):
    return render_chart_documents(
        chart_path,
        namespace=DEFAULT_NAMESPACE,
        values=values,
        api_versions=api_versions,
    )


def _document_by_kind(documents, kind, name=None):
    for doc in documents:
        if doc.get("kind") == kind and (
            name is None or doc["metadata"]["name"] == name
        ):
            return doc
    raise ValueError(
        f"Document of kind '{kind}'{' and name ' + name if name else ''} not found"
    )


def _get_all_docs_by_kind(documents, kind):
    return [doc for doc in documents if doc.get("kind") == kind]


def test_default_render(chart_path):
    """Test rendering the chart with default values."""
    documents = _render(chart_path)

    assert _document_by_kind(documents, "Deployment", "release-name-forgejo")
    assert _document_by_kind(documents, "Service", "release-name-forgejo")
    assert _document_by_kind(documents, "Service", "release-name-forgejo-ssh")
    assert _document_by_kind(documents, "Secret", "release-name-forgejo")
    assert _document_by_kind(documents, "PersistentVolumeClaim", "release-name-forgejo")
    assert _document_by_kind(documents, "Deployment", "release-name-forgejo-runner")

    with pytest.raises(ValueError):
        _document_by_kind(documents, "Ingress")
    with pytest.raises(ValueError):
        _document_by_kind(documents, "CronJob")


def test_ingress_enabled(chart_path):
    """Test that Ingress is created when ingress.enabled is true."""
    documents = _render(chart_path, values={"ingress": {"enabled": True}})
    assert _document_by_kind(documents, "Ingress", "release-name-forgejo")


def test_persistence_disabled(chart_path):
    """Test that no PVC is created when persistence is disabled."""
    documents = _render(chart_path, values={"persistence": {"enabled": False}})

    deployment = _document_by_kind(documents, "Deployment")
    assert (
        "persistentVolumeClaim"
        not in deployment["spec"]["template"]["spec"]["volumes"][0]
    )
    assert "emptyDir" in deployment["spec"]["template"]["spec"]["volumes"][0]

    with pytest.raises(ValueError):
        _document_by_kind(documents, "PersistentVolumeClaim", "release-name-forgejo")


def test_runner_disabled(chart_path):
    """Test that runner deployment is not created when runner is disabled."""
    documents = _render(chart_path, values={"runner": {"enabled": False}})
    with pytest.raises(ValueError):
        _document_by_kind(documents, "Deployment", "release-name-forgejo-runner")


def test_cronjob_enabled(chart_path):
    """Test that CronJob and its secret are created when mirrorCronJob is enabled."""
    documents = _render(chart_path, values={"mirrorCronJob": {"enabled": True}})
    assert _document_by_kind(documents, "CronJob", "release-name-forgejo-mirror")
    assert _document_by_kind(documents, "Secret", "release-name-forgejo-mirror")


@pytest.mark.parametrize("ssh_type", ["LoadBalancer", "NodePort", "ClusterIP"])
def test_ssh_service_type(chart_path, ssh_type):
    """Test different SSH service types."""
    documents = _render(chart_path, values={"service": {"ssh": {"type": ssh_type}}})
    ssh_service = _document_by_kind(documents, "Service", "release-name-forgejo-ssh")
    assert ssh_service["spec"]["type"] == ssh_type


def test_service_account_disabled(chart_path):
    """Test that no service account is created when serviceAccount.create is false."""
    documents = _render(chart_path, values={"serviceAccount": {"create": False}})
    deployment = _document_by_kind(documents, "Deployment")
    assert "serviceAccountName" not in deployment["spec"]["template"]["spec"]
    with pytest.raises(ValueError):
        _document_by_kind(documents, "ServiceAccount")


def test_postgresql_disabled(chart_path):
    """Test that postgresql is not rendered when postgresql.enabled is false."""
    documents = _render(chart_path, values={"postgresql": {"enabled": False}})
    # We can't easily check that the dependency chart is not rendered,
    # but we can check that our app is configured to use an external DB.
    deployment = _document_by_kind(documents, "Deployment", "release-name-forgejo")
    db_host_env = next(
        env
        for env in deployment["spec"]["template"]["spec"]["containers"][0]["env"]
        if env["name"] == "FORGEJO__database__HOST"
    )
    assert db_host_env["value"] != "release-name-forgejo-postgresql:5432"
