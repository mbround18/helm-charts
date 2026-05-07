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


def test_network_policy_is_disabled_by_default():
    documents = _render()

    assert all(doc.get("kind") != "NetworkPolicy" for doc in documents)


def test_checksum_and_observability_annotations_render_without_pod_annotations():
    documents = _render(values={"podAnnotations": {}})

    workload = _document_by_kind(documents, "Deployment")
    annotations = workload["spec"]["template"]["metadata"]["annotations"]

    assert "checksum/config" in annotations
    assert annotations["prometheus.io/scrape"] == "true"
    assert annotations["prometheus.io/port"] == "8888"


def test_network_policy_namespace_allowlist_rendering():
    documents = _render(
        values={
            "networkPolicy": {
                "enabled": True,
                "allowPrometheusScraping": True,
                "prometheusNamespaces": ["monitoring", "observability"],
            }
        }
    )

    network_policy = _document_by_kind(documents, "NetworkPolicy")
    metrics_rule = network_policy["spec"]["ingress"][-1]

    selectors = metrics_rule["from"]
    assert len(selectors) == 2
    assert selectors[0]["namespaceSelector"]["matchLabels"]["kubernetes.io/metadata.name"] == "monitoring"
    assert selectors[1]["namespaceSelector"]["matchLabels"]["kubernetes.io/metadata.name"] == "observability"
