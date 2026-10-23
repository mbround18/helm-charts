import subprocess
from pathlib import Path

import pytest

from charts.test_helpers import DEFAULT_NAMESPACE, render_chart_documents

CHART_PATH = Path(__file__).parent.parent


def _render(values=None):
    return render_chart_documents(
        CHART_PATH, namespace=DEFAULT_NAMESPACE, values=values
    )


def _kind(documents, kind):
    return [d for d in documents if isinstance(d, dict) and d.get("kind") == kind]


def _config(values=None):
    (configmap,) = _kind(_render(values), "ConfigMap")
    return configmap["data"]


def _pod_spec(values=None):
    (deployment,) = _kind(_render(values), "Deployment")
    return deployment["spec"]["template"]["spec"]


def test_proxies_to_the_configured_upstream():
    conf = _config({"upstream": {"host": "valheim.tailscale", "port": 3030}})[
        "nginx.conf"
    ]

    assert "server valheim.tailscale:3030;" in conf


def test_serves_stale_when_the_origin_fails():
    conf = _config()["nginx.conf"]

    assert (
        "proxy_cache_use_stale error timeout updating http_500 http_502 http_503 http_504;"
        in conf
    )
    assert "proxy_cache_background_update on;" in conf
    # The HTML shell usually says no-cache; it still has to be kept.
    assert "proxy_ignore_headers Cache-Control Expires;" in conf


def test_bypass_paths_are_proxied_without_the_cache():
    conf = _config({"bypassPaths": ["/graphql", "/auth/"]})["nginx.conf"]

    for path in ("/graphql", "/auth/"):
        block = conf.split(f"location ^~ {path} {{", 1)[1].split("}", 1)[0]
        assert "proxy_pass http://origin;" in block
        assert "proxy_cache" not in block
        assert "proxy_read_timeout 1h;" in block


def test_toast_is_injected_by_default():
    data = _config()

    assert "toast.js" in data
    assert '<script src=\\"/__pull-thru/toast.js\\" defer>' in data["nginx.conf"]
    assert 'proxy_set_header Accept-Encoding "";' in data["nginx.conf"]
    assert "location = /__pull-thru/upstream" in data["nginx.conf"]


def test_toast_can_be_disabled():
    data = _config({"toast": {"enabled": False}})

    assert "toast.js" not in data
    assert "sub_filter" not in data["nginx.conf"]
    assert "/__pull-thru/upstream" not in data["nginx.conf"]
    # The offline page for never-cached paths stays.
    assert "offline.html" in data


def test_cache_is_persisted_by_default():
    documents = _render()
    (pvc,) = _kind(documents, "PersistentVolumeClaim")
    (deployment,) = _kind(documents, "Deployment")
    volumes = {v["name"]: v for v in deployment["spec"]["template"]["spec"]["volumes"]}

    assert (
        volumes["cache"]["persistentVolumeClaim"]["claimName"]
        == pvc["metadata"]["name"]
    )
    assert deployment["spec"]["strategy"]["type"] == "Recreate"


def test_cache_falls_back_to_emptydir_without_persistence():
    values = {"cache": {"persistence": {"enabled": False}}}
    documents = _render(values)
    volumes = {v["name"]: v for v in _pod_spec(values)["volumes"]}

    assert not _kind(documents, "PersistentVolumeClaim")
    assert volumes["cache"] == {"name": "cache", "emptyDir": {}}


def test_container_is_locked_down():
    (container,) = _pod_spec()["containers"]
    security = container["securityContext"]

    assert security["runAsNonRoot"] is True
    assert security["readOnlyRootFilesystem"] is True
    assert security["allowPrivilegeEscalation"] is False
    assert security["capabilities"]["drop"] == ["ALL"]


def test_empty_upstream_host_fails_the_render():
    with pytest.raises(subprocess.CalledProcessError):
        _render({"upstream": {"host": ""}})
