from pathlib import Path

from charts.test_helpers import render_chart_documents


def _render(values=None, api_versions=None):
    chart_path = Path(__file__).parent.parent
    return render_chart_documents(chart_path, values=values, api_versions=api_versions)


def _document_by_kind(documents, kind):
    return next(document for document in documents if document.get("kind") == kind)


def test_defaults_render_production_workload_and_foundation_resources():
    documents = _render()

    deployment = _document_by_kind(documents, "Deployment")
    service = _document_by_kind(documents, "Service")
    admin_secret = next(
        document
        for document in documents
        if document.get("kind") == "Secret"
        and document.get("metadata", {}).get("name") == "release-name-keycloak-admin"
    )
    pvc = _document_by_kind(documents, "PersistentVolumeClaim")

    assert service["spec"]["ports"][0]["targetPort"] == "http"
    assert "annotations" not in service["metadata"]
    assert deployment["spec"]["template"]["spec"]["containers"][0]["args"][0] == "start"
    assert "--optimized" in deployment["spec"]["template"]["spec"]["containers"][0][
        "args"
    ]
    assert admin_secret["stringData"]["KC_BOOTSTRAP_ADMIN_USERNAME"] == "admin"
    assert pvc["metadata"]["annotations"]["helm.sh/resource-policy"] == "keep"
    assert (
        deployment["spec"]["template"]["spec"]["containers"][0]["securityContext"][
            "readOnlyRootFilesystem"
        ]
        is True
    )
    assert any(
        vm.get("name") == "tmp"
        and vm.get("mountPath") == "/tmp"
        for vm in deployment["spec"]["template"]["spec"]["containers"][0][
            "volumeMounts"
        ]
    )
    init_container = deployment["spec"]["template"]["spec"]["initContainers"][0]
    assert init_container["name"] == "keycloak-build"
    assert init_container["args"][0] == "build"
    assert init_container["securityContext"]["runAsNonRoot"] is True
    assert any(
        vm.get("name") == "quarkus-lib"
        and vm.get("mountPath") == "/opt/keycloak/lib/quarkus"
        for vm in init_container["volumeMounts"]
    )


def test_import_realm_adds_mount_and_startup_arg():
    documents = _render(
        values={
            "keycloak": {
                "importRealm": {
                    "enabled": True,
                    "existingConfigMap": "keycloak-realms",
                }
            }
        }
    )

    deployment = _document_by_kind(documents, "Deployment")
    args = deployment["spec"]["template"]["spec"]["containers"][0]["args"]
    volumes = deployment["spec"]["template"]["spec"]["volumes"]

    assert "--import-realm" in args
    assert any(
        volume.get("name") == "realm-import"
        and volume.get("configMap", {}).get("name") == "keycloak-realms"
        for volume in volumes
    )


def test_build_init_can_be_disabled():
    documents = _render(values={"keycloak": {"buildInit": {"enabled": False}}})
    deployment = _document_by_kind(documents, "Deployment")

    assert "initContainers" not in deployment["spec"]["template"]["spec"]
    assert "--optimized" not in deployment["spec"]["template"]["spec"]["containers"][0][
        "args"
    ]


def test_optimized_start_is_respected_without_build_init():
    documents = _render(
        values={"keycloak": {"buildInit": {"enabled": False}, "optimizedStart": True}}
    )
    deployment = _document_by_kind(documents, "Deployment")

    assert deployment["spec"]["template"]["spec"]["containers"][0]["args"][:2] == [
        "start",
        "--optimized",
    ]


def test_existing_secret_mode_skips_chart_managed_secrets():
    documents = _render(
        values={
            "bootstrapAdmin": {
                "existingSecret": "keycloak-bootstrap",
                "create": False,
            },
            "database": {
                "existingSecret": "keycloak-db-pass",
                "createSecret": False,
            },
        }
    )

    deployment = _document_by_kind(documents, "Deployment")
    env = deployment["spec"]["template"]["spec"]["containers"][0]["env"]

    assert all(document.get("kind") != "Secret" for document in documents)
    assert any(
        item.get("name") == "KC_BOOTSTRAP_ADMIN_USERNAME"
        and item.get("valueFrom", {}).get("secretKeyRef", {}).get("name")
        == "keycloak-bootstrap"
        for item in env
    )
    assert any(
        item.get("name") == "KC_DB_PASSWORD"
        and item.get("valueFrom", {}).get("secretKeyRef", {}).get("name")
        == "keycloak-db-pass"
        for item in env
    )


def test_argocd_annotations_render_when_application_api_is_available():
    documents = _render(api_versions=["argoproj.io/v1alpha1/Application"])

    service_account = _document_by_kind(documents, "ServiceAccount")
    deployment = _document_by_kind(documents, "Deployment")
    service = _document_by_kind(documents, "Service")

    assert (
        service_account["metadata"]["annotations"]["argocd.argoproj.io/sync-wave"]
        == "0"
    )
    assert deployment["metadata"]["annotations"]["argocd.argoproj.io/sync-wave"] == "30"
    assert service["metadata"]["annotations"]["argocd.argoproj.io/sync-wave"] == "40"
