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


def _document_by_kind(documents, kind, name=None):
    matches = [document for document in documents if document.get("kind") == kind]
    if name is not None:
        matches = [
            document for document in matches if document["metadata"]["name"] == name
        ]
    return matches[0]


def test_nodeport_service_groups_ports_by_protocol_not_port_number():
    # ArgoCD/kubectl compute strategic-merge $setElementOrder using the
    # ServicePort merge key "port" alone (protocol is not part of the legacy
    # merge key). query and game each expose the same port number over both
    # TCP and UDP, so the two protocol entries for a given port must stay
    # adjacent and in a stable order across renders/releases, or ArgoCD fails
    # with "doesn't match $setElementOrder list" during normalization.
    documents = _render()

    service = _document_by_kind(documents, "Service", "release-name-palworld")
    ports = service["spec"]["ports"]

    assert [(p["port"], p["protocol"]) for p in ports] == [
        (27015, "TCP"),
        (27015, "UDP"),
        (8211, "TCP"),
        (8211, "UDP"),
    ]

    # Every duplicate-port pair must carry an identical, pinned nodePort so
    # the two entries are indistinguishable other than by protocol/name.
    by_port = {}
    for entry in ports:
        by_port.setdefault(entry["port"], []).append(entry)
    for port, entries in by_port.items():
        node_ports = {e["nodePort"] for e in entries}
        assert len(node_ports) == 1, (
            f"mismatched nodePort within port {port}: {entries}"
        )

    assert ports[0]["nodePort"] == ports[1]["nodePort"] == 30764
    assert ports[2]["nodePort"] == ports[3]["nodePort"] == 32285


def test_nodeport_service_uses_server_side_apply():
    # Replace=true does not prevent ArgoCD's diff/normalize step from
    # computing a strategic-merge patch against a stale live object, which is
    # what raises the $setElementOrder error. ServerSideApply=true routes
    # ArgoCD through structured merge diff, which respects the port+protocol
    # composite list-map key instead of the ambiguous single-field "port"
    # merge key, so it doesn't hit this ordering ambiguity at all.
    documents = _render(api_versions=["argoproj.io/v1alpha1/Application"])

    service = _document_by_kind(documents, "Service", "release-name-palworld")

    assert (
        service["metadata"]["annotations"]["argocd.argoproj.io/sync-options"]
        == "ServerSideApply=true"
    )


def test_nodeport_service_port_order_is_stable_across_reraders():
    # Guard against regressions where the outer/inner range loop nesting
    # order changes again (as happened between commits a71fcd1 and 8f41f7e),
    # which reshuffles $setElementOrder relative to any already-applied live
    # object and reproduces the ArgoCD normalization failure.
    first = _render()
    second = _render()

    first_ports = _document_by_kind(first, "Service", "release-name-palworld")["spec"][
        "ports"
    ]
    second_ports = _document_by_kind(second, "Service", "release-name-palworld")[
        "spec"
    ]["ports"]

    assert first_ports == second_ports


def _kinds(documents):
    return {document.get("kind") for document in documents}


def test_agones_mode_replaces_statefulset_and_services_with_gameserver():
    documents = _render(values={"agones": {"enabled": True}})

    kinds = _kinds(documents)
    assert "GameServer" in kinds
    assert "StatefulSet" not in kinds
    assert "Service" not in kinds

    # PVCs are still needed for persistent world/save data in Agones mode.
    assert "PersistentVolumeClaim" in kinds


def test_default_mode_does_not_render_gameserver():
    documents = _render()

    assert "GameServer" not in _kinds(documents)
    assert "StatefulSet" in _kinds(documents)


def test_gameserver_exposes_the_same_ports_as_the_statefulset_container():
    documents = _render(values={"agones": {"enabled": True}})

    gameserver = _document_by_kind(documents, "GameServer", "release-name-palworld")
    ports = gameserver["spec"]["ports"]

    assert [(p["containerPort"], p["protocol"], p["portPolicy"]) for p in ports] == [
        (27015, "TCP", "Dynamic"),
        (27015, "UDP", "Dynamic"),
        (8211, "TCP", "Dynamic"),
        (8211, "UDP", "Dynamic"),
    ]

    container = gameserver["spec"]["template"]["spec"]["containers"][0]
    container_ports = [(p["containerPort"], p["protocol"]) for p in container["ports"]]
    assert container_ports == [
        (27015, "TCP"),
        (27015, "UDP"),
        (8211, "TCP"),
        (8211, "UDP"),
    ]


def test_gameserver_mounts_the_same_pvcs_as_the_statefulset():
    agones_documents = _render(values={"agones": {"enabled": True}})
    statefulset_documents = _render()

    gameserver = _document_by_kind(
        agones_documents, "GameServer", "release-name-palworld"
    )
    statefulset = _document_by_kind(
        statefulset_documents, "StatefulSet", "release-name-palworld"
    )

    gameserver_container = gameserver["spec"]["template"]["spec"]["containers"][0]
    statefulset_container = statefulset["spec"]["template"]["spec"]["containers"][0]

    assert gameserver_container["volumeMounts"] == statefulset_container["volumeMounts"]
    assert (
        gameserver["spec"]["template"]["spec"]["volumes"]
        == statefulset["spec"]["template"]["spec"]["volumes"]
    )


def test_gameserver_honors_custom_port_policy_and_health_settings():
    documents = _render(
        values={
            "agones": {
                "enabled": True,
                "portPolicy": "Static",
                "scheduling": "Distributed",
                "health": {
                    "disabled": False,
                    "periodSeconds": 5,
                    "failureThreshold": 2,
                    "initialDelaySeconds": 30,
                },
            }
        }
    )

    gameserver = _document_by_kind(documents, "GameServer", "release-name-palworld")

    assert all(p["portPolicy"] == "Static" for p in gameserver["spec"]["ports"])
    assert gameserver["spec"]["scheduling"] == "Distributed"
    assert gameserver["spec"]["health"] == {
        "disabled": False,
        "periodSeconds": 5,
        "failureThreshold": 2,
        "initialDelaySeconds": 30,
    }
