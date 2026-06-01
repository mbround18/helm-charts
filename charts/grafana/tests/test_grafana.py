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


def _documents_by_kind(documents, kind):
    return [
        doc for doc in documents if isinstance(doc, dict) and doc.get("kind") == kind
    ]


def test_wrapper_servicemonitor_renders_with_unique_name():
    documents = _render()

    service_monitors = _documents_by_kind(documents, "ServiceMonitor")
    names = [doc["metadata"]["name"] for doc in service_monitors]

    assert "release-name-wrapper" in names
    assert len(names) == len(set(names))


def test_istio_authorization_policy_can_be_disabled():
    documents = _render(values={"istio-ingress": {"enabled": False}})

    assert all(doc.get("kind") != "AuthorizationPolicy" for doc in documents)


def test_istio_authorization_policy_is_rendered_by_default():
    documents = _render()

    policies = _documents_by_kind(documents, "AuthorizationPolicy")

    assert len(policies) == 1
    assert policies[0]["metadata"]["name"] == "release-name-telemetry-deny"


def test_external_secrets_are_disabled_by_default():
    documents = _render()

    assert all(doc.get("kind") != "ExternalSecret" for doc in documents)
    assert all(doc.get("kind") != "Password" for doc in documents)


def test_external_secrets_render_generator_targets_with_retention_defaults():
    documents = _render(values={"externalSecrets": {"enabled": True}})

    passwords = _documents_by_kind(documents, "Password")
    external_secrets = _documents_by_kind(documents, "ExternalSecret")

    assert {doc["metadata"]["name"] for doc in passwords} == {
        "grafana-admin-password",
        "grafana-db-password",
    }
    assert {doc["metadata"]["name"] for doc in external_secrets} == {
        "release-name-external-secret-resources-admin",
        "release-name-external-secret-resources-database",
    }

    admin_secret = next(
        doc
        for doc in external_secrets
        if doc["metadata"]["name"] == "release-name-external-secret-resources-admin"
    )
    database_secret = next(
        doc
        for doc in external_secrets
        if doc["metadata"]["name"] == "release-name-external-secret-resources-database"
    )

    assert admin_secret["spec"]["target"]["creationPolicy"] == "Orphan"
    assert admin_secret["spec"]["target"]["deletionPolicy"] == "Retain"
    assert (
        admin_secret["spec"]["target"]["template"]["metadata"]["annotations"][
            "argocd.argoproj.io/compare-options"
        ]
        == "IgnoreExtraneous"
    )
    assert (
        admin_secret["spec"]["target"]["template"]["metadata"]["annotations"][
            "argocd.argoproj.io/sync-options"
        ]
        == "Prune=false,Delete=false"
    )
    assert admin_secret["spec"]["target"]["template"]["data"]["user"] == "admin"
    assert (
        admin_secret["spec"]["target"]["template"]["data"]["password"]
        == "{{ .password }}"
    )
    assert database_secret["spec"]["dataFrom"][0]["sourceRef"]["generatorRef"]["kind"] == "Password"
