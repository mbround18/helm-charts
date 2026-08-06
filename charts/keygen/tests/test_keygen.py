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


def _is_keygen_owned(document):
    labels = (document.get("metadata") or {}).get("labels") or {}
    return labels.get("app.kubernetes.io/name") == "keygen"


def _document_by_kind(documents, kind):
    return next(
        doc
        for doc in documents
        if doc.get("kind") == kind and _is_keygen_owned(doc)
    )


def _documents_by_kind(documents, kind):
    return [
        doc for doc in documents if doc.get("kind") == kind and _is_keygen_owned(doc)
    ]


def _container(pod_spec, name):
    return next(c for c in pod_spec["containers"] if c["name"] == name)


def test_web_deployment_assembles_database_and_redis_url_at_startup():
    documents = _render()

    deployment = _document_by_kind(documents, "Deployment")
    container = _container(deployment["spec"]["template"]["spec"], "keygen")

    assert container["command"][0:2] == ["sh", "-c"]
    script = container["command"][2]
    assert "DATABASE_URL=" in script
    assert "REDIS_URL=" in script
    assert "exec /app/scripts/entrypoint.sh web" in script

    env_names = {env["name"] for env in container["env"]}
    assert {
        "SECRET_KEY_BASE",
        "ENCRYPTION_DETERMINISTIC_KEY",
        "ENCRYPTION_PRIMARY_KEY",
        "ENCRYPTION_KEY_DERIVATION_SALT",
        "KEYGEN_ACCOUNT_ID",
        "DB_HOST",
        "DB_PASSWORD",
        "REDIS_HOST",
    } <= env_names
    # Redis auth is disabled by default -- no REDIS_PASSWORD env should be wired.
    assert "REDIS_PASSWORD" not in env_names


def test_worker_deployment_enabled_by_default_runs_worker_process():
    documents = _render()

    worker = next(
        doc
        for doc in _documents_by_kind(documents, "Deployment")
        if doc["metadata"]["name"].endswith("-worker")
    )
    container = _container(
        worker["spec"]["template"]["spec"], "keygen-worker"
    )

    assert "exec /app/scripts/entrypoint.sh worker" in container["command"][2]


def test_worker_deployment_omitted_when_disabled():
    documents = _render(values={"worker": {"enabled": False}})

    deployments = _documents_by_kind(documents, "Deployment")
    assert len(deployments) == 1
    assert not deployments[0]["metadata"]["name"].endswith("-worker")


def test_migration_job_runs_as_pre_install_pre_upgrade_hook():
    documents = _render()

    job = _document_by_kind(documents, "Job")
    annotations = job["metadata"]["annotations"]

    assert annotations["helm.sh/hook"] == "pre-install,pre-upgrade"
    container = _container(job["spec"]["template"]["spec"], "keygen-migrate")
    assert "exec /app/scripts/entrypoint.sh release" in container["command"][2]


def test_migration_job_omitted_when_disabled():
    documents = _render(values={"migrations": {"enabled": False}})

    assert not _documents_by_kind(documents, "Job")


def test_secrets_generated_by_default():
    documents = _render()

    secret = _document_by_kind(documents, "Secret")
    assert secret["metadata"]["name"].endswith("-secrets")
    for key in (
        "SECRET_KEY_BASE",
        "ENCRYPTION_DETERMINISTIC_KEY",
        "ENCRYPTION_PRIMARY_KEY",
        "ENCRYPTION_KEY_DERIVATION_SALT",
        "KEYGEN_ACCOUNT_ID",
    ):
        assert key in secret["stringData"]


def test_secrets_omitted_when_create_disabled():
    documents = _render(values={"secrets": {"create": False}})

    assert not _documents_by_kind(documents, "Secret")


def test_argocd_sync_waves_render_when_application_api_is_available():
    documents = _render(api_versions=["argoproj.io/v1alpha1/Application"])

    secret = _document_by_kind(documents, "Secret")
    deployment = _document_by_kind(documents, "Deployment")
    service = _document_by_kind(documents, "Service")
    job = _document_by_kind(documents, "Job")

    assert secret["metadata"]["annotations"]["argocd.argoproj.io/sync-wave"] == "0"
    assert (
        deployment["metadata"]["annotations"]["argocd.argoproj.io/sync-wave"] == "30"
    )
    assert service["metadata"]["annotations"]["argocd.argoproj.io/sync-wave"] == "40"
    assert job["metadata"]["annotations"]["argocd.argoproj.io/sync-wave"] == "20"
