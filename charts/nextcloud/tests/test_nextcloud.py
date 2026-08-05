from pathlib import Path

from charts.test_helpers import (
    DEFAULT_NAMESPACE,
    iter_workloads,
    render_chart_documents,
)


def _render(values=None, api_versions=None):
    chart_path = Path(__file__).parent.parent
    return render_chart_documents(
        chart_path,
        namespace=DEFAULT_NAMESPACE,
        values=values,
        api_versions=api_versions,
    )


def _document_by_name(documents, kind, name):
    return next(
        document
        for document in documents
        if document.get("kind") == kind and document["metadata"]["name"] == name
    )


def test_statefulset_and_pvc_names_match_legacy_raw_manifests():
    # These names must stay hardcoded: Kubernetes reuses an existing PVC when a
    # StatefulSet's generated claim name (<template>-<statefulset>-<ordinal>)
    # matches one already in the namespace. Changing them would orphan the
    # Longhorn volumes created by the raw-manifest deployment this chart replaces.
    documents = _render()
    workloads = {workload.name: workload for workload in iter_workloads(documents)}

    nextcloud = workloads["nextcloud"]
    assert nextcloud.kind == "StatefulSet"
    assert nextcloud.volume_claim_template_names == ("nextcloud-storage",)

    mysql = workloads["mysql"]
    assert mysql.kind == "StatefulSet"
    assert mysql.volume_claim_template_names == ("mysql-storage",)


def test_secrets_are_referenced_not_created():
    documents = _render()

    assert not any(document.get("kind") == "Secret" for document in documents)

    nextcloud = _document_by_name(documents, "StatefulSet", "nextcloud")
    env = nextcloud["spec"]["template"]["spec"]["containers"][0]["env"]
    env_by_name = {item["name"]: item for item in env}

    assert (
        env_by_name["MYSQL_PASSWORD"]["valueFrom"]["secretKeyRef"]["name"]
        == "mysql-secret"
    )
    assert (
        env_by_name["NEXTCLOUD_ADMIN_PASSWORD"]["valueFrom"]["secretKeyRef"]["name"]
        == "nextcloud-secret"
    )

    mysql = _document_by_name(documents, "StatefulSet", "mysql")
    assert mysql["spec"]["template"]["spec"]["containers"][0]["envFrom"] == [
        {"secretRef": {"name": "mysql-secret"}}
    ]


def test_argocd_metadata_renders_when_application_api_is_available():
    documents = _render(api_versions=["argoproj.io/v1alpha1/Application"])

    nextcloud = _document_by_name(documents, "StatefulSet", "nextcloud")
    mysql = _document_by_name(documents, "StatefulSet", "mysql")

    assert nextcloud["metadata"]["annotations"]["argocd.argoproj.io/sync-wave"] == "30"
    assert mysql["metadata"]["annotations"]["argocd.argoproj.io/sync-wave"] == "10"


def test_istio_disabled_by_default():
    documents = _render()

    assert not any(document.get("kind") == "VirtualService" for document in documents)
    assert not any(document.get("kind") == "Gateway" for document in documents)


def test_istio_routes_include_caldav_carddav_rewrite():
    documents = _render(
        values={
            "istio-ingress": {
                "enabled": True,
                "virtualService": {
                    "enabled": True,
                    "hosts": ["cloud.example.com"],
                    "http": [
                        {
                            "match": [
                                {"uri": {"prefix": "/.well-known/caldav"}},
                                {"uri": {"prefix": "/.well-known/carddav"}},
                            ],
                            "rewrite": {"uri": "/remote.php/dav"},
                            "route": [
                                {
                                    "destination": {
                                        "host": "nextcloud",
                                        "port": {"number": 80},
                                    }
                                }
                            ],
                        },
                        {
                            "name": "nextcloud-web",
                            "match": [{"uri": {"prefix": "/"}}],
                            "route": [
                                {
                                    "destination": {
                                        "host": "nextcloud",
                                        "port": {"number": 80},
                                    }
                                }
                            ],
                        },
                    ],
                },
                "gateway": {"enabled": True},
            }
        }
    )

    virtual_service = next(
        document for document in documents if document.get("kind") == "VirtualService"
    )
    routes = virtual_service["spec"]["http"]

    assert routes[0]["rewrite"]["uri"] == "/remote.php/dav"
    assert routes[0]["match"][0]["uri"]["prefix"] == "/.well-known/caldav"
    assert routes[1]["match"][0]["uri"]["prefix"] == "/"


def test_cron_job_hits_cron_php():
    documents = _render()

    cron_job = next(
        document for document in documents if document.get("kind") == "CronJob"
    )
    container = cron_job["spec"]["jobTemplate"]["spec"]["template"]["spec"][
        "containers"
    ][0]

    assert (
        "http://nextcloud.contract-tests.svc.cluster.local/cron.php"
        in container["args"]
    )
