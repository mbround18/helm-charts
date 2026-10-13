from pathlib import Path

from charts.test_helpers import DEFAULT_NAMESPACE, render_chart_documents

CHART_PATH = Path(__file__).parent.parent
RELEASE = "thanos"


def _render(values=None):
    return [
        doc
        for doc in render_chart_documents(
            CHART_PATH,
            values=values,
            release_name=RELEASE,
            namespace=DEFAULT_NAMESPACE,
        )
        if isinstance(doc, dict)
    ]


def _find(documents, kind, name):
    matches = [
        doc
        for doc in documents
        if doc.get("kind") == kind and doc["metadata"]["name"] == name
    ]
    assert len(matches) == 1, f"expected one {kind}/{name}, got {len(matches)}"
    return matches[0]


def _container(workload):
    containers = workload["spec"]["template"]["spec"]["containers"]
    assert len(containers) == 1
    return containers[0]


def _args(workload):
    return _container(workload)["args"]


def test_default_render_has_store_compactor_and_query():
    docs = _render()
    _find(docs, "StatefulSet", "thanos-store")
    _find(docs, "StatefulSet", "thanos-compactor")
    _find(docs, "Deployment", "thanos-query")
    _find(docs, "Service", "thanos-store")
    _find(docs, "Service", "thanos-compactor")
    _find(docs, "Service", "thanos-query")
    assert not [d for d in docs if d["kind"] == "ServiceMonitor"]
    assert not [d for d in docs if d["kind"] == "Secret"], (
        "chart must not own credentials"
    )


def test_components_can_be_disabled():
    docs = _render({"store": {"enabled": False}, "compactor": {"enabled": False}})
    kinds = {(d["kind"], d["metadata"]["name"]) for d in docs}
    assert ("StatefulSet", "thanos-store") not in kinds
    assert ("StatefulSet", "thanos-compactor") not in kinds
    assert ("Deployment", "thanos-query") in kinds
    assert not any(
        "thanos-store" in a for a in _args(_find(docs, "Deployment", "thanos-query"))
    )


def test_bucket_components_read_objstore_config_from_existing_secret():
    docs = _render({"objstore": {"existingSecret": "b2", "key": "thanos.yml"}})
    for name in ("thanos-store", "thanos-compactor"):
        workload = _find(docs, "StatefulSet", name)
        volumes = {
            v["name"]: v for v in workload["spec"]["template"]["spec"]["volumes"]
        }
        secret = volumes["objstore"]["secret"]
        assert secret["secretName"] == "b2"
        assert secret["items"] == [{"key": "thanos.yml", "path": "objstore.yml"}]
        assert "--objstore.config-file=/etc/thanos/objstore.yml" in _args(workload)


def test_compactor_is_a_singleton_with_retention_per_resolution():
    docs = _render(
        {
            "compactor": {
                "replicas": 3,
                "retention": {"raw": "30d", "fiveMinutes": "90d", "oneHour": "395d"},
            }
        }
    )
    compactor = _find(docs, "StatefulSet", "thanos-compactor")
    assert compactor["spec"]["replicas"] == 1
    args = _args(compactor)
    assert args[0] == "compact"
    assert "--wait" in args
    assert "--retention.resolution-raw=30d" in args
    assert "--retention.resolution-5m=90d" in args
    assert "--retention.resolution-1h=395d" in args


def test_query_fans_out_to_store_and_extra_endpoints():
    docs = _render(
        {
            "query": {
                "extraEndpoints": [
                    "dnssrv+_grpc._tcp.kube-prometheus-stack-thanos-discovery.monitoring.svc"
                ],
                "replicaLabels": ["prometheus_replica"],
            }
        }
    )
    args = _args(_find(docs, "Deployment", "thanos-query"))
    assert args[0] == "query"
    assert (
        f"--endpoint=dnssrv+_grpc._tcp.thanos-store.{DEFAULT_NAMESPACE}.svc.cluster.local"
        in args
    )
    assert (
        "--endpoint=dnssrv+_grpc._tcp.kube-prometheus-stack-thanos-discovery.monitoring.svc"
        in args
    )
    assert "--query.replica-label=prometheus_replica" in args


def test_store_service_is_headless_so_query_sees_every_replica():
    service = _find(_render(), "Service", "thanos-store")
    assert service["spec"]["clusterIP"] == "None"
    assert {p["name"] for p in service["spec"]["ports"]} == {"grpc", "http"}


def test_image_digest_pins_every_component():
    digest = "sha256:" + "a" * 64
    docs = _render({"image": {"tag": "v0.42.4", "digest": digest}})
    for kind, name in (
        ("StatefulSet", "thanos-store"),
        ("StatefulSet", "thanos-compactor"),
        ("Deployment", "thanos-query"),
    ):
        image = _container(_find(docs, kind, name))["image"]
        assert image == f"quay.io/thanos/thanos:v0.42.4@{digest}"


def test_containers_run_unprivileged():
    docs = _render()
    for doc in docs:
        if doc["kind"] not in ("StatefulSet", "Deployment"):
            continue
        pod = doc["spec"]["template"]["spec"]
        assert pod["securityContext"]["runAsNonRoot"] is True
        context = _container(doc)["securityContext"]
        assert context["allowPrivilegeEscalation"] is False
        assert context["readOnlyRootFilesystem"] is True
        assert context["capabilities"]["drop"] == ["ALL"]


def test_service_monitor_scrapes_every_component():
    docs = _render({"serviceMonitor": {"enabled": True, "labels": {"team": "ops"}}})
    monitor = _find(docs, "ServiceMonitor", "thanos")
    assert monitor["metadata"]["labels"]["team"] == "ops"
    selector = monitor["spec"]["selector"]["matchLabels"]
    assert "app.kubernetes.io/component" not in selector
    assert [e["port"] for e in monitor["spec"]["endpoints"]] == ["http"]


def test_bucket_credentials_come_from_env_on_bucket_components_only():
    docs = _render(
        {
            "objstore": {
                "extraEnvFrom": [{"secretRef": {"name": "s3-credentials"}}],
                "extraEnv": [{"name": "S3_ENDPOINT", "value": "s3.example.test"}],
            }
        }
    )
    for name in ("thanos-store", "thanos-compactor"):
        container = _container(_find(docs, "StatefulSet", name))
        assert container["envFrom"] == [{"secretRef": {"name": "s3-credentials"}}]
        assert container["env"] == [{"name": "S3_ENDPOINT", "value": "s3.example.test"}]
    query = _container(_find(docs, "Deployment", "thanos-query"))
    assert "envFrom" not in query and "env" not in query


def test_no_env_by_default():
    for doc in _render():
        if doc["kind"] in ("StatefulSet", "Deployment"):
            container = _container(doc)
            assert "envFrom" not in container and "env" not in container
