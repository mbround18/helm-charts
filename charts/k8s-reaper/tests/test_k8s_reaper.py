from pathlib import Path

import yaml

from charts.test_helpers import DEFAULT_NAMESPACE, render_chart_documents

CHART_PATH = Path(__file__).parent.parent

# contracts/config.md "RBAC required (ClusterRole)" in mbround18/k8s-reaper.
EXPECTED_RULES = {
    ("", "pods"): {"get", "list", "watch"},
    ("", "namespaces"): {"get", "list", "watch"},
    ("apps", "replicasets"): {"get", "list", "watch"},
    ("apps", "deployments"): {"get", "list", "watch", "patch"},
    ("apps", "statefulsets"): {"get", "list", "watch", "patch"},
    ("apps", "daemonsets"): {"get", "list", "watch", "patch"},
    ("apps", "deployments/scale"): {"get", "patch", "update"},
    ("apps", "statefulsets/scale"): {"get", "patch", "update"},
    ("batch", "cronjobs"): {"get", "list", "watch", "patch"},
    ("batch", "jobs"): {"get", "list", "watch"},
    ("autoscaling", "horizontalpodautoscalers"): {"get", "list", "watch"},
    ("keda.sh", "scaledobjects"): {"get", "list", "watch"},
    ("helm.toolkit.fluxcd.io", "helmreleases"): {"get", "list", "watch", "patch"},
    ("events.k8s.io", "events"): {"create", "patch"},
    ("reaper.boop.ninja", "reaperconfigs"): {"get", "list", "watch"},
    ("reaper.boop.ninja", "reaperconfigs/status"): {"get", "patch", "update"},
}

# contracts/metrics.md "Alert rules".
EXPECTED_ALERTS = {
    "ReaperCrashLoopPlanned": ("5m", "warning"),
    "ReaperWorkloadReaped": ("0m", "warning"),
    "ReaperWorkloadSkipped": ("30m", "info"),
    "ReaperActionFailed": ("0m", "critical"),
    "ReaperStalled": ("5m", "critical"),
    "ReaperConfigInvalid": ("5m", "warning"),
    "ReaperDown": ("10m", "critical"),
}


def _render(values=None, release_name="k8s-reaper"):
    return [
        doc
        for doc in render_chart_documents(
            CHART_PATH,
            values=values,
            release_name=release_name,
            namespace=DEFAULT_NAMESPACE,
        )
        if isinstance(doc, dict)
    ]


def _by_kind(documents, kind):
    return [doc for doc in documents if doc.get("kind") == kind]


def _one(documents, kind):
    matches = _by_kind(documents, kind)
    assert len(matches) == 1, f"expected one {kind}, got {len(matches)}"
    return matches[0]


def _container(deployment):
    containers = deployment["spec"]["template"]["spec"]["containers"]
    assert len(containers) == 1
    return containers[0]


def _wave(document):
    return document["metadata"]["annotations"]["argocd.argoproj.io/sync-wave"]


def test_deployment_is_a_single_recreate_replica():
    deployment = _one(_render(), "Deployment")

    assert deployment["spec"]["replicas"] == 1
    assert deployment["spec"]["strategy"] == {"type": "Recreate"}


def test_image_defaults_to_app_version():
    chart = yaml.safe_load((CHART_PATH / "Chart.yaml").read_text(encoding="utf-8"))
    container = _container(_one(_render(), "Deployment"))

    assert container["image"] == f"mbround18/k8s-reaper:{chart['appVersion']}"


def test_pod_runs_non_root_with_read_only_filesystem():
    deployment = _one(_render(), "Deployment")
    pod_security = deployment["spec"]["template"]["spec"]["securityContext"]
    container_security = _container(deployment)["securityContext"]

    assert pod_security["runAsNonRoot"] is True
    assert pod_security["runAsUser"] == 65532
    assert pod_security["runAsGroup"] == 65532
    assert pod_security["seccompProfile"] == {"type": "RuntimeDefault"}
    assert container_security["runAsNonRoot"] is True
    assert container_security["allowPrivilegeEscalation"] is False
    assert container_security["readOnlyRootFilesystem"] is True
    assert container_security["capabilities"]["drop"] == ["ALL"]


def test_container_wires_namespace_probes_and_metrics_port():
    container = _container(_one(_render(), "Deployment"))
    env = {item["name"]: item for item in container["env"]}

    assert env["REAPER_NAMESPACE"]["valueFrom"]["fieldRef"]["fieldPath"] == (
        "metadata.namespace"
    )
    assert env["REAPER_CONFIG_NAME"]["value"] == "default"
    assert {"name": "http", "containerPort": 8080, "protocol": "TCP"} in container[
        "ports"
    ]
    assert container["livenessProbe"]["httpGet"]["path"] == "/healthz"
    assert container["readinessProbe"]["httpGet"]["path"] == "/readyz"
    assert "OTEL_EXPORTER_OTLP_ENDPOINT" not in env


def test_cluster_role_matches_the_rbac_contract_exactly():
    role = _one(_render(), "ClusterRole")
    granted = {}

    for rule in role["rules"]:
        assert "*" not in rule["verbs"]
        assert "*" not in rule["resources"]
        assert "*" not in rule["apiGroups"]
        assert "nonResourceURLs" not in rule
        assert "resourceNames" not in rule
        for group in rule["apiGroups"]:
            for resource in rule["resources"]:
                granted.setdefault((group, resource), set()).update(rule["verbs"])

    assert granted == EXPECTED_RULES
    all_verbs = set().union(*granted.values())
    assert not all_verbs & {
        "delete",
        "deletecollection",
        "escalate",
        "bind",
        "impersonate",
    }
    assert not any(resource == "secrets" for _, resource in granted)


def test_cluster_role_binding_targets_the_release_service_account():
    documents = _render()
    binding = _one(documents, "ClusterRoleBinding")
    account = _one(documents, "ServiceAccount")
    deployment = _one(documents, "Deployment")

    assert (
        binding["roleRef"]["name"] == _one(documents, "ClusterRole")["metadata"]["name"]
    )
    assert binding["subjects"] == [
        {
            "kind": "ServiceAccount",
            "name": account["metadata"]["name"],
            "namespace": DEFAULT_NAMESPACE,
        }
    ]
    assert (
        deployment["spec"]["template"]["spec"]["serviceAccountName"]
        == account["metadata"]["name"]
    )


def test_reaper_config_default_is_report_mode():
    config = _one(_render(), "ReaperConfig")

    assert config["apiVersion"] == "reaper.boop.ninja/v1alpha1"
    assert config["metadata"]["name"] == "default"
    assert "namespace" not in config["metadata"]
    assert config["spec"] == {"mode": "report"}


def test_reaper_config_spec_is_passed_through_and_can_be_disabled():
    spec = {
        "mode": "full",
        "detection": {"crashLoopDuration": "1h", "minRestarts": 20},
        "scope": {"excludeNamespaces": ["kube-system"]},
        "notifications": {"clusterName": "prod-eu"},
    }
    config = _one(_render({"reaperConfig": {"spec": spec}}), "ReaperConfig")
    assert config["spec"] == spec

    documents = _render({"reaperConfig": {"create": False}})
    assert not _by_kind(documents, "ReaperConfig")


def test_reaper_config_name_drives_config_name_env():
    documents = _render({"reaperConfig": {"name": "cluster-a"}})
    env = {
        item["name"]: item for item in _container(_one(documents, "Deployment"))["env"]
    }

    assert _one(documents, "ReaperConfig")["metadata"]["name"] == "cluster-a"
    assert env["REAPER_CONFIG_NAME"]["value"] == "cluster-a"


def test_notifications_secret_is_mounted_optional():
    deployment = _one(
        _render({"notifications": {"secretName": "reaper-channels"}}), "Deployment"
    )
    pod = deployment["spec"]["template"]["spec"]
    container = _container(deployment)
    env = {item["name"]: item for item in container["env"]}

    assert pod["volumes"] == [
        {
            "name": "notifications",
            "secret": {"secretName": "reaper-channels", "optional": True},
        }
    ]
    assert container["volumeMounts"] == [
        {
            "name": "notifications",
            "mountPath": "/etc/k8s-reaper/notifications",
            "readOnly": True,
        }
    ]
    assert env["REAPER_NOTIFICATIONS_DIR"]["value"] == "/etc/k8s-reaper/notifications"


def test_notifications_mount_absent_without_secret_name():
    deployment = _one(_render({"notifications": {"secretName": ""}}), "Deployment")
    pod = deployment["spec"]["template"]["spec"]
    container = _container(deployment)

    assert "volumes" not in pod
    assert "volumeMounts" not in container
    assert "REAPER_NOTIFICATIONS_DIR" not in {item["name"] for item in container["env"]}


def test_never_renders_a_secret():
    documents = _render({"notifications": {"secretName": "reaper-channels"}})
    assert not _by_kind(documents, "Secret")


def test_monitoring_resources_only_when_enabled():
    documents = _render()
    assert not _by_kind(documents, "ServiceMonitor")
    assert not _by_kind(documents, "PrometheusRule")

    documents = _render(
        {"serviceMonitor": {"enabled": True}, "prometheusRule": {"enabled": True}}
    )
    assert len(_by_kind(documents, "ServiceMonitor")) == 1
    assert len(_by_kind(documents, "PrometheusRule")) == 1


def test_service_monitor_scrapes_the_service_and_keeps_workload_labels():
    documents = _render({"serviceMonitor": {"enabled": True}})
    monitor = _one(documents, "ServiceMonitor")
    service = _one(documents, "Service")

    assert monitor["spec"]["selector"]["matchLabels"].items() <= (
        service["metadata"]["labels"].items()
    )
    assert monitor["spec"]["namespaceSelector"] == {"matchNames": [DEFAULT_NAMESPACE]}
    endpoint = monitor["spec"]["endpoints"][0]
    assert endpoint["port"] == "http"
    assert endpoint["path"] == "/metrics"
    # The reaper's `namespace` label is the workload's, not the scrape target's.
    assert endpoint["honorLabels"] is True


def test_prometheus_rule_ships_the_contract_alerts():
    rule = _one(
        _render(
            {"serviceMonitor": {"enabled": True}, "prometheusRule": {"enabled": True}}
        ),
        "PrometheusRule",
    )
    alerts = {
        item["alert"]: item
        for group in rule["spec"]["groups"]
        for item in group["rules"]
    }

    assert set(alerts) == set(EXPECTED_ALERTS)
    for name, (duration, severity) in EXPECTED_ALERTS.items():
        assert alerts[name]["for"] == duration, name
        assert alerts[name]["labels"]["severity"] == severity, name
        assert alerts[name]["annotations"]["runbook_url"].endswith(
            "restoring-a-workload.md"
        )
    assert alerts["ReaperDown"]["expr"] == 'absent(up{job="k8s-reaper"} == 1)'


def _alerts(rule):
    return {
        item["alert"]: item
        for group in rule["spec"]["groups"]
        for item in group["rules"]
    }


def test_reaper_down_tracks_the_service_name_for_other_release_names():
    documents = _render(
        {"serviceMonitor": {"enabled": True}, "prometheusRule": {"enabled": True}},
        release_name="other-name",
    )
    down = _alerts(_one(documents, "PrometheusRule"))["ReaperDown"]
    service = _one(documents, "Service")

    assert service["metadata"]["name"] == "other-name-k8s-reaper"
    assert down["expr"] == 'absent(up{job="other-name-k8s-reaper"} == 1)'


def test_reaper_down_absent_without_the_service_monitor():
    documents = _render(
        {"serviceMonitor": {"enabled": False}, "prometheusRule": {"enabled": True}}
    )
    alerts = _alerts(_one(documents, "PrometheusRule"))

    assert "ReaperDown" not in alerts
    assert set(alerts) == set(EXPECTED_ALERTS) - {"ReaperDown"}


def test_memory_request_covers_observed_use():
    resources = _container(_one(_render(), "Deployment"))["resources"]

    assert resources["requests"]["memory"] == "64Mi"
    assert resources["limits"]["memory"] == "128Mi"


def test_sync_waves_follow_the_repo_phase_model():
    documents = _render(
        {"serviceMonitor": {"enabled": True}, "prometheusRule": {"enabled": True}}
    )
    expected = {
        "ServiceAccount": "0",
        "ClusterRole": "0",
        "ClusterRoleBinding": "0",
        "ReaperConfig": "0",
        "Deployment": "30",
        "Service": "40",
        "ServiceMonitor": "40",
        "PrometheusRule": "40",
    }

    assert {doc["kind"]: _wave(doc) for doc in documents} == expected


def test_crd_ships_in_crds_directory_and_is_marked_generated():
    crd_files = sorted((CHART_PATH / "crds").glob("*.yaml"))
    assert [path.name for path in crd_files] == ["reaperconfigs.reaper.boop.ninja.yaml"]

    text = crd_files[0].read_text(encoding="utf-8")
    assert text.startswith("# GENERATED by `k8s-reaper crd`")
    crd = yaml.safe_load(text)
    assert crd["kind"] == "CustomResourceDefinition"
    assert crd["metadata"]["name"] == "reaperconfigs.reaper.boop.ninja"
    assert crd["spec"]["scope"] == "Cluster"
    assert [version["name"] for version in crd["spec"]["versions"]] == ["v1alpha1"]


def test_crd_carries_the_cron_job_failure_rate_settings():
    crd = yaml.safe_load(
        (CHART_PATH / "crds" / "reaperconfigs.reaper.boop.ninja.yaml").read_text(
            encoding="utf-8"
        )
    )
    spec = crd["spec"]["versions"][0]["schema"]["openAPIV3Schema"]["properties"]["spec"]
    failure_rate = spec["properties"]["cronJobs"]["properties"]["failureRate"]
    assert set(failure_rate["properties"]) == {"enabled", "threshold", "windowRuns"}
    assert failure_rate["properties"]["windowRuns"]["minimum"] == 3
    assert failure_rate["properties"]["windowRuns"]["maximum"] == 100
