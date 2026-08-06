from pathlib import Path

import pytest
import subprocess

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
    return next(doc for doc in documents if doc.get("kind") == kind)


def _documents_by_kind(documents, kind):
    return [doc for doc in documents if doc.get("kind") == kind]


def test_auth_disabled_by_default_and_no_secret_rendered():
    documents = _render()

    assert not _documents_by_kind(documents, "Secret")

    statefulset = _document_by_kind(documents, "StatefulSet")
    container = statefulset["spec"]["template"]["spec"]["containers"][0]

    assert container["command"] == ["redis-server", "--appendonly", "yes"]
    assert "env" not in container


def test_auth_enabled_reads_from_existing_secret_reference():
    documents = _render(
        values={"auth": {"enabled": True, "existingSecret": "my-redis-secret"}}
    )

    assert not _documents_by_kind(documents, "Secret")

    statefulset = _document_by_kind(documents, "StatefulSet")
    container = statefulset["spec"]["template"]["spec"]["containers"][0]
    password_env = next(
        env for env in container["env"] if env["name"] == "REDIS_PASSWORD"
    )

    assert password_env["valueFrom"]["secretKeyRef"]["name"] == "my-redis-secret"
    assert password_env["valueFrom"]["secretKeyRef"]["key"] == "REDIS_PASSWORD"


def test_auth_enabled_without_existing_secret_fails_to_render():
    with pytest.raises(subprocess.CalledProcessError) as excinfo:
        _render(values={"auth": {"enabled": True}})

    assert "auth.existingSecret" in (excinfo.value.stderr or "")


def test_no_secret_manifest_is_ever_rendered():
    # This chart must never accept secret values through Helm values -- only
    # references (name/key) to a Secret created out-of-band. Assert that
    # invariant holds across every values combination this chart supports.
    for values in (
        None,
        {"auth": {"enabled": True, "existingSecret": "my-redis-secret"}},
        {"persistence": {"enabled": False}},
    ):
        documents = _render(values=values)
        assert not _documents_by_kind(documents, "Secret")


def test_persistence_uses_volume_claim_template_by_default():
    documents = _render()

    statefulset = _document_by_kind(documents, "StatefulSet")
    claim_names = {
        template["metadata"]["name"]
        for template in statefulset["spec"]["volumeClaimTemplates"]
    }

    assert claim_names == {"data"}


def test_argocd_sync_waves_render_when_application_api_is_available():
    documents = _render(api_versions=["argoproj.io/v1alpha1/Application"])

    statefulset = _document_by_kind(documents, "StatefulSet")
    service = _document_by_kind(documents, "Service")

    assert (
        statefulset["metadata"]["annotations"]["argocd.argoproj.io/sync-wave"] == "10"
    )
    assert service["metadata"]["annotations"]["argocd.argoproj.io/sync-wave"] == "10"
