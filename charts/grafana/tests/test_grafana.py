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


def test_external_secrets_render_admin_and_database_targets():
    documents = _render(
        values={
            "externalSecrets": {
                "enabled": True,
                "mode": "store",
                "secretStore": "vault-kv",
                "secretStoreKind": "ClusterSecretStore",
                "admin": {"passwordKey": "grafana/data/adminPassword", "user": "admin"},
                "database": {
                    "passwordKey": "grafana/data/databasePassword",
                },
            }
        }
    )

    external_secrets = _documents_by_kind(documents, "ExternalSecret")
    names = [doc["metadata"]["name"] for doc in external_secrets]

    assert names == ["release-name-admin", "release-name-database"]

    admin_secret = next(
        doc for doc in external_secrets if doc["metadata"]["name"] == "release-name-admin"
    )
    database_secret = next(
        doc for doc in external_secrets
        if doc["metadata"]["name"] == "release-name-database"
    )

    assert admin_secret["spec"]["target"]["name"] == "grafana-admin-creds"
    assert [entry["secretKey"] for entry in admin_secret["spec"]["data"]] == ["user", "password"]
    assert (
        admin_secret["spec"]["target"]["template"]["metadata"]["annotations"][
            "argocd.argoproj.io/sync-options"
        ]
        == "Prune=false,Delete=false"
    )
    assert database_secret["spec"]["target"]["name"] == "grafana-db-credentials"
    assert [entry["secretKey"] for entry in database_secret["spec"]["data"]] == ["password"]


def test_external_secret_generator_mode_renders_password_generators():
    documents = _render(values={"externalSecrets": {"enabled": True}})

    passwords = _documents_by_kind(documents, "Password")
    external_secrets = _documents_by_kind(documents, "ExternalSecret")

    assert [doc["metadata"]["name"] for doc in passwords] == [
        "release-name-admin-password",
        "release-name-database-password",
    ]
    assert len(external_secrets) == 2
    assert (
        external_secrets[0]["spec"]["dataFrom"][0]["sourceRef"]["generatorRef"]["kind"]
        == "Password"
    )
    assert external_secrets[0]["spec"]["target"]["template"]["data"]["user"] == "admin"
    assert (
        external_secrets[0]["spec"]["target"]["template"]["metadata"]["annotations"][
            "argocd.argoproj.io/compare-options"
        ]
        == "IgnoreExtraneous"
    )
