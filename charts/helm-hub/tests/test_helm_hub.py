from pathlib import Path

from charts.test_helpers import DEFAULT_NAMESPACE, render_chart_documents


def _render(values=None):
    chart_path = Path(__file__).parent.parent
    return render_chart_documents(
        chart_path, namespace=DEFAULT_NAMESPACE, values=values
    )


def _container(documents):
    deployment = next(doc for doc in documents if doc.get("kind") == "Deployment")
    return deployment["spec"]["template"]["spec"]["containers"][0]


def test_probes_tolerate_a_slow_response():
    container = _container(_render())

    for probe in ("livenessProbe", "readinessProbe"):
        assert container[probe]["timeoutSeconds"] >= 3


def test_probes_are_overridable():
    container = _container(
        _render(values={"readinessProbe": {"timeoutSeconds": 7}})
    )

    assert container["readinessProbe"]["timeoutSeconds"] == 7
    assert container["readinessProbe"]["httpGet"]["path"] == "/readyz"


def test_jwt_secret_from_values_is_used():
    documents = _render(values={"secrets": {"JWT_SECRET": "fixed-for-test"}})
    conn = next(
        doc
        for doc in documents
        if doc.get("kind") == "Secret" and doc["metadata"]["name"].endswith("-db-conn")
    )

    assert conn["stringData"]["JWT_SECRET"] == "fixed-for-test"


def test_jwt_secret_survives_upgrades():
    # helm template has no cluster, so lookup returns nothing; the template
    # must still read an existing Secret before generating a new value.
    template = (Path(__file__).parent.parent / "templates" / "secret.yaml").read_text()

    assert 'lookup "v1" "Secret"' in template
