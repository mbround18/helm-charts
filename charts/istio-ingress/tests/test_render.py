import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest
import yaml

CHART_DIR = Path(__file__).resolve().parent.parent


def helm_template(values: dict | None = None):
    """Render the chart with optional values and return parsed YAML docs."""
    if not shutil.which("helm"):
        pytest.skip("helm not installed")

    cmd = [
        "helm",
        "template",
        "demo",
        str(CHART_DIR),
        "--namespace",
        "testns",
    ]

    tmp_file = None
    if values:
        tmp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
        yaml.safe_dump(values, tmp_file)
        tmp_file.flush()
        cmd.extend(["--values", tmp_file.name])

    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    finally:
        if tmp_file:
            os.unlink(tmp_file.name)

    docs = [doc for doc in yaml.safe_load_all(result.stdout) if doc]
    return docs


def test_default_renders_gateway_and_vs():
    docs = helm_template()
    kinds = {doc["kind"]: doc for doc in docs}

    assert "Gateway" in kinds
    assert "VirtualService" in kinds

    gateway = kinds["Gateway"]
    vs = kinds["VirtualService"]

    assert gateway["metadata"]["name"] == "demo-istio-ingress-gateway"
    assert gateway["metadata"]["namespace"] == "testns"
    assert vs["metadata"]["name"] == "demo-istio-ingress-vs"
    assert vs["spec"]["gateways"] == ["demo-istio-ingress-gateway"]


def test_vs_uses_explicit_gateway_when_local_disabled():
    values = {
        "gateway": {"enabled": False},
        "helpers": {"useLocalGateway": False},
        "virtualService": {"gateways": ["mesh"]},
    }

    docs = helm_template(values)
    kinds = {doc["kind"]: doc for doc in docs}

    assert "Gateway" not in kinds
    assert "VirtualService" in kinds

    vs = kinds["VirtualService"]
    assert vs["spec"]["gateways"] == ["mesh"]


def test_gateway_tls_https_and_external_dns_annotations():
    values = {
        "externalDns": {
            "enabled": True,
            "annotations": {
                "external-dns.alpha.kubernetes.io/hostname": "example.com",
            },
        },
        "gateway": {
            "servers": [
                {
                    "port": {"number": 443, "protocol": "HTTPS", "name": "https"},
                    "hosts": ["example.com"],
                }
            ]
        },
        "tls": {
            "enabled": True,
            "mode": "SIMPLE",
            "credentialName": "my-cert",
            "httpsRedirect": True,
        },
    }

    docs = helm_template(values)
    kinds = {doc["kind"]: doc for doc in docs}

    gw = kinds["Gateway"]
    server = gw["spec"]["servers"][0]
    assert server["port"]["protocol"] == "HTTPS"
    assert server["tls"]["mode"] == "SIMPLE"
    assert server["tls"]["credentialName"] == "my-cert"
    assert (
        gw["metadata"]["annotations"]["external-dns.alpha.kubernetes.io/hostname"]
        == "example.com"
    )


def test_virtualservice_override_passthroughs_as_is():
    override = {
        "apiVersion": "networking.istio.io/v1beta1",
        "kind": "VirtualService",
        "metadata": {"name": "custom-vs"},
        "spec": {"hosts": ["custom.local"], "http": []},
    }

    docs = helm_template({"virtualServiceOverride": override})
    kinds = {doc["kind"]: doc for doc in docs}

    vs = kinds["VirtualService"]
    assert vs["metadata"]["name"] == "custom-vs"
    assert vs["spec"]["hosts"] == ["custom.local"]


def test_gateway_override_passthroughs_as_is():
    override = {
        "apiVersion": "networking.istio.io/v1beta1",
        "kind": "Gateway",
        "metadata": {"name": "custom-gw"},
        "spec": {"selector": {"istio": "ingress"}, "servers": []},
    }

    docs = helm_template({"gatewayOverride": override})
    kinds = {doc["kind"]: doc for doc in docs}

    gw = kinds["Gateway"]
    assert gw["metadata"]["name"] == "custom-gw"


def test_virtualservice_hosts_and_routes_render():
    values = {
        "virtualService": {
            "hosts": ["a.example.com", "b.example.com"],
            "http": [
                {
                    "name": "api-route",
                    "match": [{"uri": {"prefix": "/api"}}],
                    "route": [
                        {
                            "destination": {
                                "host": "api.default.svc.cluster.local",
                                "port": {"number": 8080},
                            }
                        }
                    ],
                }
            ],
        }
    }

    docs = helm_template(values)
    vs = {doc["kind"]: doc for doc in docs}["VirtualService"]
    assert vs["spec"]["hosts"] == ["a.example.com", "b.example.com"]
    http = vs["spec"]["http"][0]
    assert http["name"] == "api-route"
    assert http["route"][0]["destination"]["port"]["number"] == 8080


def test_chart_disabled_renders_nothing():
    docs = helm_template({"enabled": False})
    assert docs == []


@pytest.mark.parametrize(
    "values,expected_kinds",
    [
        ({}, {"Gateway", "VirtualService"}),
        (
            {
                "gateway": {"enabled": False},
                "helpers": {"useLocalGateway": False},
                "virtualService": {"gateways": ["mesh"]},
            },
            {"VirtualService"},
        ),
        ({"virtualService": {"enabled": False}}, {"Gateway"}),
        ({"enabled": False}, set()),
    ],
)
def test_feature_matrix(values, expected_kinds):
    docs = helm_template(values)
    kinds = {doc["kind"] for doc in docs}
    assert kinds == expected_kinds


def test_tcp_route_renders():
    values = {
        "virtualService": {
            "tcp": [
                {
                    "route": [
                        {
                            "destination": {
                                "host": "tcp-svc.default.svc.cluster.local",
                                "port": {"number": 9000},
                            }
                        }
                    ]
                }
            ]
        }
    }

    docs = helm_template(values)
    vs = {doc["kind"]: doc for doc in docs}["VirtualService"]
    tcp = vs["spec"].get("tcp")
    assert tcp is not None
    assert tcp[0]["route"][0]["destination"]["port"]["number"] == 9000
