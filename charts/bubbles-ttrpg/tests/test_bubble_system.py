from pathlib import Path

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


def _app_service(documents):
    # The mongo subchart also renders a Service (named "mongo") -- disambiguate
    # by name so these assertions target the bubble-system app's own Service.
    return next(
        doc
        for doc in documents
        if doc.get("kind") == "Service" and doc["metadata"]["name"] != "mongo"
    )


def _app_container_env(documents):
    deployment = _document_by_kind(documents, "Deployment")
    return {
        env["name"]: env
        for env in deployment["spec"]["template"]["spec"]["containers"][0]["env"]
    }


def test_argocd_metadata_is_not_rendered_by_default():
    documents = _render()

    deployment = _document_by_kind(documents, "Deployment")
    service = _app_service(documents)

    assert "annotations" not in deployment["metadata"]
    assert "annotations" not in service["metadata"]
    assert "argocd.argoproj.io/instance" not in deployment["metadata"]["labels"]


def test_argocd_sync_waves_render_when_application_api_is_available():
    documents = _render(api_versions=["argoproj.io/v1alpha1/Application"])

    service_account = _document_by_kind(documents, "ServiceAccount")
    deployment = _document_by_kind(documents, "Deployment")
    service = _app_service(documents)

    assert (
        service_account["metadata"]["annotations"]["argocd.argoproj.io/sync-wave"]
        == "0"
    )
    assert (
        deployment["metadata"]["annotations"]["argocd.argoproj.io/sync-wave"] == "30"
    )
    assert service["metadata"]["annotations"]["argocd.argoproj.io/sync-wave"] == "40"


def test_default_image_pull_secret_is_docker_credentials():
    documents = _render()

    deployment = _document_by_kind(documents, "Deployment")
    pull_secrets = deployment["spec"]["template"]["spec"]["imagePullSecrets"]

    assert pull_secrets == [{"name": "docker-credentials"}]


def test_mongo_subchart_is_bundled_and_wired_by_default():
    documents = _render()

    mongo_statefulset = next(
        doc for doc in documents if doc.get("kind") == "StatefulSet"
    )
    assert mongo_statefulset["metadata"]["name"] == "mongo"

    env = _app_container_env(documents)
    assert env["MONGODB_URI"] == {"name": "MONGODB_URI", "value": "mongodb://mongo:27017"}


def test_mongo_disabled_renders_no_statefulset_or_uri_env():
    documents = _render(values={"mongo": {"enabled": False}})

    assert not any(doc.get("kind") == "StatefulSet" for doc in documents)
    env = _app_container_env(documents)
    assert "MONGODB_URI" not in env


def test_secret_env_reference_wires_secret_key_ref_and_skips_bundled_mongo():
    documents = _render(
        values={
            "secretEnv": {
                "MONGODB_URI": {
                    "secretName": "external-mongo",
                    "secretKey": "uri",
                },
                "SESSION_SECRET": {
                    "secretName": "app-secrets",
                    "secretKey": "session-secret",
                },
            }
        }
    )

    env = _app_container_env(documents)

    assert env["MONGODB_URI"]["valueFrom"]["secretKeyRef"] == {
        "name": "external-mongo",
        "key": "uri",
    }
    assert env["SESSION_SECRET"]["valueFrom"]["secretKeyRef"] == {
        "name": "app-secrets",
        "key": "session-secret",
    }
    # DISCORD_CLIENT_SECRET wasn't given a secretName -- must not appear at all.
    assert "DISCORD_CLIENT_SECRET" not in env


def test_no_secret_manifest_is_ever_rendered():
    # This chart must never accept secret values through Helm values -- only
    # references (name/key) to Secrets created out-of-band. Assert that
    # invariant holds across every values combination this chart supports,
    # including the bundled mongo subchart's own manifests.
    for values in (
        None,
        {"mongo": {"enabled": False}},
        {
            "secretEnv": {
                "MONGODB_URI": {"secretName": "external-mongo", "secretKey": "uri"},
                "DISCORD_CLIENT_SECRET": {
                    "secretName": "app-secrets",
                    "secretKey": "discord",
                },
                "SESSION_SECRET": {
                    "secretName": "app-secrets",
                    "secretKey": "session",
                },
            }
        },
        {"mongo": {"auth": {"enabled": True, "existingSecret": "mongo-creds"}}},
    ):
        documents = _render(values=values)
        assert not _documents_by_kind(documents, "Secret")
