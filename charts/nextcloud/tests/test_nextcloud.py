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


def test_workloads_are_hardened_by_default():
    documents = _render()
    workloads = {workload.name: workload for workload in iter_workloads(documents)}

    for workload in workloads.values():
        spec = workload.pod_spec
        assert spec["automountServiceAccountToken"] is False, workload.name
        assert spec["securityContext"]["seccompProfile"]["type"] == "RuntimeDefault"
        for container in spec["containers"]:
            context = container["securityContext"]
            assert context["allowPrivilegeEscalation"] is False, workload.name
            assert context["capabilities"]["drop"] == ["ALL"], workload.name

    mysql = workloads["mysql"].pod_spec
    assert mysql["securityContext"]["runAsNonRoot"] is True
    assert mysql["securityContext"]["runAsUser"] == 999
    assert "add" not in mysql["containers"][0]["securityContext"]["capabilities"]

    cron = workloads["release-name-nextcloud-cron"].pod_spec
    assert cron["securityContext"]["runAsNonRoot"] is True
    assert "@sha256:" in cron["containers"][0]["image"]
    assert cron["containers"][0]["args"][0] == "-fsS"


def test_hardening_config_hides_versions_and_mounts_after_image_defaults():
    documents = _render()
    config_map = _document_by_name(documents, "ConfigMap", "nextcloud-hardening")
    assert "ServerTokens Prod" in config_map["data"]["apache-hardening.conf"]
    assert "ServerSignature Off" in config_map["data"]["apache-hardening.conf"]
    assert "expose_php = Off" in config_map["data"]["php-hardening.ini"]

    statefulset = _document_by_name(documents, "StatefulSet", "nextcloud")
    template = statefulset["spec"]["template"]
    assert "checksum/hardening" in template["metadata"]["annotations"]
    mounts = {
        mount["mountPath"]: mount
        for mount in template["spec"]["containers"][0]["volumeMounts"]
    }
    assert mounts["/etc/apache2/conf-enabled/zz-hardening.conf"]["subPath"] == (
        "apache-hardening.conf"
    )
    assert mounts["/usr/local/etc/php/conf.d/zz-hardening.ini"]["readOnly"] is True


def test_hardening_can_be_disabled():
    documents = _render({"nextcloud": {"hardening": {"enabled": False}}})
    assert not any(document.get("kind") == "ConfigMap" for document in documents)
    statefulset = _document_by_name(documents, "StatefulSet", "nextcloud")
    assert "volumes" not in statefulset["spec"]["template"]["spec"]


def test_extra_volumes_and_mounts_are_appended():
    documents = _render(
        {
            "nextcloud": {
                "extraVolumes": [
                    {"name": "remoteip", "configMap": {"name": "remoteip-conf"}}
                ],
                "extraVolumeMounts": [
                    {
                        "name": "remoteip",
                        "mountPath": "/etc/apache2/conf-enabled/zz-remoteip.conf",
                        "subPath": "remoteip.conf",
                    }
                ],
            }
        }
    )
    spec = _document_by_name(documents, "StatefulSet", "nextcloud")["spec"]["template"][
        "spec"
    ]
    assert [volume["name"] for volume in spec["volumes"]] == ["hardening", "remoteip"]
    assert spec["containers"][0]["volumeMounts"][-1]["name"] == "remoteip"
