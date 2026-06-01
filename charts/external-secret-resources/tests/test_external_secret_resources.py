from pathlib import Path

from charts.test_helpers import DEFAULT_NAMESPACE, render_chart_documents


def _render(values=None):
    chart_path = Path(__file__).parent.parent
    return render_chart_documents(chart_path, namespace=DEFAULT_NAMESPACE, values=values)


def _documents_by_kind(documents, kind):
    return [doc for doc in documents if isinstance(doc, dict) and doc.get("kind") == kind]


def test_external_secrets_disabled_by_default():
    documents = _render()

    assert documents == []


def test_external_secret_store_and_generator_resources_render():
    documents = _render(
        values={
            "enabled": True,
            "annotations": {"gitops.tool": "argocd"},
            "secrets": {
                "admin": {
                    "mode": "generator",
                    "targetName": "grafana-admin-creds",
                    "generator": {"name": "grafana-admin-password"},
                    "target": {"data": {"user": "admin"}},
                },
                "database": {
                    "mode": "generator",
                    "targetName": "grafana-db-credentials",
                    "generator": {"name": "grafana-db-password"},
                },
            }
        }
    )

    passwords = _documents_by_kind(documents, "Password")
    external_secrets = _documents_by_kind(documents, "ExternalSecret")

    assert len(passwords) == 2
    assert len(external_secrets) == 2

    password = next(
        doc for doc in passwords if doc["metadata"]["name"] == "grafana-admin-password"
    )
    database_password = next(
        doc for doc in passwords if doc["metadata"]["name"] == "grafana-db-password"
    )
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

    assert password["metadata"]["annotations"]["argocd.argoproj.io/sync-wave"] == "0"
    assert database_password["metadata"]["annotations"]["argocd.argoproj.io/sync-wave"] == "0"
    assert password["metadata"]["annotations"]["gitops.tool"] == "argocd"
    assert admin_secret["spec"]["target"]["creationPolicy"] == "Orphan"
    assert admin_secret["spec"]["target"]["deletionPolicy"] == "Retain"
    assert (
        admin_secret["spec"]["target"]["template"]["metadata"]["annotations"][
            "argocd.argoproj.io/sync-options"
        ]
        == "Prune=false,Delete=false"
    )
    assert admin_secret["spec"]["target"]["template"]["data"]["user"] == "admin"
    assert database_secret["spec"]["target"]["name"] == "grafana-db-credentials"
