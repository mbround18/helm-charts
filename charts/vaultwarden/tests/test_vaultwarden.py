from pathlib import Path

import pytest

from charts.test_helpers import render_chart_documents, render_chart_snapshot


def _render(values=None):
    chart_path = Path(__file__).parent.parent
    return render_chart_documents(chart_path, values=values)


def _render_with_api_versions(api_versions, values=None):
    chart_path = Path(__file__).parent.parent
    return render_chart_documents(chart_path, values=values, api_versions=api_versions)


def _document_by_kind(documents, kind):
    return next(document for document in documents if document.get("kind") == kind)


def test_chart_rendering(snapshot):
    chart_path = Path(__file__).parent.parent

    snapshot.assert_match(
        render_chart_snapshot(chart_path, normalize_secrets=True),
        "chart_snapshot.yaml",
    )


def test_defaults_reuse_existing_claim_and_secret_without_creating_them():
    documents = _render()

    deployment = _document_by_kind(documents, "Deployment")
    service = _document_by_kind(documents, "Service")

    assert all(
        document.get("kind") != "PersistentVolumeClaim" for document in documents
    )
    assert all(document.get("kind") != "Secret" for document in documents)
    assert deployment["spec"]["strategy"]["type"] == "Recreate"
    assert "annotations" not in service["metadata"]
    assert "argocd.argoproj.io/instance" not in service["metadata"]["labels"]
    assert (
        deployment["spec"]["template"]["spec"]["volumes"][0]["persistentVolumeClaim"][
            "claimName"
        ]
        == "vaultwarden"
    )
    assert any(
        env.get("name") == "ADMIN_TOKEN"
        and env.get("valueFrom", {}).get("secretKeyRef", {}).get("name")
        == "vaultwarden"
        for env in deployment["spec"]["template"]["spec"]["containers"][0]["env"]
    )


def test_safe_persistence_defaults_can_create_retained_pvc():
    documents = _render(
        values={
            "persistence": {
                "existingClaim": "",
                "create": True,
            },
            "secret": {
                "existingSecret": "",
                "create": True,
                "adminToken": "$$argon2id$$v=19$$m=65540,t=3,p=4$$example$$example",
            },
            "virtualService": {
                "enabled": False,
            },
        },
    )

    pvc = _document_by_kind(documents, "PersistentVolumeClaim")
    deployment = _document_by_kind(documents, "Deployment")

    assert pvc["metadata"]["annotations"]["helm.sh/resource-policy"] == "keep"
    assert "argocd.argoproj.io/sync-wave" not in pvc["metadata"]["annotations"]
    assert deployment["spec"]["strategy"]["type"] == "Recreate"
    assert (
        deployment["spec"]["template"]["spec"]["volumes"][0]["persistentVolumeClaim"][
            "claimName"
        ]
        == "release-name-vaultwarden"
    )
    assert pvc["spec"]["storageClassName"] == "longhorn-static"


def test_can_create_admin_secret_when_not_reusing_existing_one():
    documents = _render(
        values={
            "secret": {
                "existingSecret": "",
                "create": True,
                "adminToken": "$$argon2id$$v=19$$m=65540,t=3,p=4$$example$$example",
            },
            "virtualService": {
                "enabled": False,
            },
        }
    )

    secret = _document_by_kind(documents, "Secret")
    deployment = _document_by_kind(documents, "Deployment")

    assert secret["type"] == "Opaque"
    assert (
        secret["stringData"]["admin-token"]
        == "$$argon2id$$v=19$$m=65540,t=3,p=4$$example$$example"
    )
    assert any(
        env.get("name") == "ADMIN_TOKEN"
        and env.get("valueFrom", {}).get("secretKeyRef", {}).get("name")
        == "release-name-vaultwarden"
        for env in deployment["spec"]["template"]["spec"]["containers"][0]["env"]
    )


def test_disabling_admin_token_omits_secret_reference_and_secret_resource():
    documents = _render(
        values={
            "secret": {
                "existingSecret": "",
                "create": True,
                "adminToken": "$$argon2id$$v=19$$m=65540,t=3,p=4$$example$$example",
            },
            "vaultwarden": {
                "admin": {
                    "enabled": True,
                    "disableAdminToken": True,
                },
            },
            "virtualService": {
                "enabled": False,
            },
        }
    )

    deployment = _document_by_kind(documents, "Deployment")
    env_names = {
        env["name"]
        for env in deployment["spec"]["template"]["spec"]["containers"][0]["env"]
    }

    assert "ADMIN_TOKEN" not in env_names
    assert all(document.get("kind") != "Secret" for document in documents)


def test_extra_env_and_secret_env_are_injected_into_container():
    documents = _render(
        values={
            "vaultwarden": {
                "extraEnv": [
                    {"name": "TZ", "value": "UTC"},
                ],
                "extraSecretEnv": [
                    {
                        "name": "SMTP_PASSWORD",
                        "secretName": "smtp-secret",
                        "key": "password",
                    },
                ],
            },
        }
    )

    deployment = _document_by_kind(documents, "Deployment")
    env = deployment["spec"]["template"]["spec"]["containers"][0]["env"]

    assert any(item.get("name") == "TZ" and item.get("value") == "UTC" for item in env)
    assert any(
        item.get("name") == "SMTP_PASSWORD"
        and item.get("valueFrom", {}).get("secretKeyRef", {}).get("name")
        == "smtp-secret"
        and item.get("valueFrom", {}).get("secretKeyRef", {}).get("key") == "password"
        for item in env
    )


@pytest.mark.parametrize(
    ("values", "expected_kinds"),
    [
        ({}, {"Service", "Deployment", "VirtualService"}),
        ({"virtualService": {"enabled": False}}, {"Service", "Deployment"}),
        (
            {
                "virtualService": {"enabled": False},
                "ingress": {
                    "enabled": True,
                },
            },
            {"Service", "Deployment", "Ingress"},
        ),
    ],
)
def test_network_resources_follow_feature_toggles(values, expected_kinds):
    documents = _render(values)

    assert {document.get("kind") for document in documents} == expected_kinds


def test_argocd_auto_detection_adds_sync_wave_annotations_when_api_is_present():
    documents = _render_with_api_versions(["argoproj.io/v1alpha1/Application"])

    service = _document_by_kind(documents, "Service")
    deployment = _document_by_kind(documents, "Deployment")
    virtual_service = _document_by_kind(documents, "VirtualService")

    assert service["metadata"]["annotations"]["argocd.argoproj.io/sync-wave"] == "40"
    assert deployment["metadata"]["annotations"]["argocd.argoproj.io/sync-wave"] == "30"
    assert (
        virtual_service["metadata"]["annotations"]["argocd.argoproj.io/sync-wave"]
        == "40"
    )


def test_argocd_force_mode_adds_instance_label_and_common_metadata():
    documents = _render(
        values={
            "argoCd": {
                "mode": "enabled",
                "instanceLabel": "vaultwarden-prod",
                "commonAnnotations": {
                    "argocd.argoproj.io/compare-options": "IgnoreExtraneous",
                },
                "commonLabels": {
                    "gitops.tool": "argocd",
                },
            },
        }
    )

    service = _document_by_kind(documents, "Service")
    deployment = _document_by_kind(documents, "Deployment")

    assert (
        service["metadata"]["labels"]["argocd.argoproj.io/instance"]
        == "vaultwarden-prod"
    )
    assert service["metadata"]["labels"]["gitops.tool"] == "argocd"
    assert (
        service["metadata"]["annotations"]["argocd.argoproj.io/compare-options"]
        == "IgnoreExtraneous"
    )
    assert deployment["metadata"]["annotations"]["argocd.argoproj.io/sync-wave"] == "30"
