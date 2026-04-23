import shutil

import pytest

from charts.test_helpers import (
    DEFAULT_NAMESPACE,
    application_chart_directories,
    iter_workloads,
    render_chart_documents,
    resource_identity,
    resource_name,
    resource_namespace,
)


HELM_AVAILABLE = shutil.which("helm") is not None
APPLICATION_CHARTS = application_chart_directories()


def _chart_id(chart_path):
    return chart_path.name


def _service_port_target(service_port):
    return service_port.get("targetPort", service_port.get("port"))


def _container_ports(container):
    ports = container.get("ports") or []
    return {
        "names": {port.get("name") for port in ports if port.get("name")},
        "numbers": {port.get("containerPort") for port in ports if port.get("containerPort") is not None},
    }


@pytest.mark.skipif(not HELM_AVAILABLE, reason="helm not installed")
@pytest.mark.parametrize("chart_path", APPLICATION_CHARTS, ids=_chart_id)
def test_rendered_resources_have_unique_identity(chart_path):
    documents = render_chart_documents(chart_path)
    seen = set()
    duplicates = []

    for document in documents:
        if not isinstance(document, dict) or not resource_name(document):
            continue

        identity = resource_identity(document)
        if identity in seen:
            duplicates.append(identity)
        seen.add(identity)

    assert not duplicates, f"duplicate rendered resources: {duplicates}"


@pytest.mark.skipif(not HELM_AVAILABLE, reason="helm not installed")
@pytest.mark.parametrize("chart_path", APPLICATION_CHARTS, ids=_chart_id)
def test_rendered_services_select_workloads_and_resolve_ports(chart_path):
    documents = render_chart_documents(chart_path)
    workloads = iter_workloads(documents)
    errors = []

    for document in documents:
        if not isinstance(document, dict) or document.get("kind") != "Service":
            continue

        spec = document.get("spec") or {}
        selector = spec.get("selector") or {}
        if spec.get("type") == "ExternalName" or not selector:
            continue

        service_namespace = resource_namespace(document, DEFAULT_NAMESPACE)
        matching_workloads = [
            workload
            for workload in workloads
            if workload.namespace == service_namespace
            and selector.items() <= workload.pod_labels.items()
        ]

        if not matching_workloads:
            errors.append(
                f"{chart_path.name}: Service {resource_name(document)} selector {selector} matches no workload"
            )
            continue

        for port in spec.get("ports") or []:
            target = _service_port_target(port)
            if isinstance(target, str):
                if not any(
                    target in _container_ports(container)["names"]
                    for workload in matching_workloads
                    for container in workload.pod_spec.get("containers") or []
                ):
                    errors.append(
                        f"{chart_path.name}: Service {resource_name(document)} targetPort '{target}' not exposed by selected workloads"
                    )
            elif isinstance(target, int):
                if not any(
                    target in _container_ports(container)["numbers"]
                    for workload in matching_workloads
                    for container in workload.pod_spec.get("containers") or []
                ):
                    errors.append(
                        f"{chart_path.name}: Service {resource_name(document)} targetPort {target} not exposed by selected workloads"
                    )

    assert not errors, "\n".join(errors)


@pytest.mark.skipif(not HELM_AVAILABLE, reason="helm not installed")
@pytest.mark.parametrize("chart_path", APPLICATION_CHARTS, ids=_chart_id)
def test_workload_volume_mounts_and_service_accounts_are_declared(chart_path):
    documents = render_chart_documents(chart_path)
    workloads = iter_workloads(documents)
    service_accounts = {
        (resource_namespace(document, DEFAULT_NAMESPACE), resource_name(document))
        for document in documents
        if isinstance(document, dict)
        and document.get("kind") == "ServiceAccount"
        and resource_name(document)
    }
    errors = []

    for workload in workloads:
        declared_volumes = {
            volume.get("name")
            for volume in workload.pod_spec.get("volumes") or []
            if volume.get("name")
        }
        declared_volumes.update(workload.volume_claim_template_names)

        for container in (workload.pod_spec.get("initContainers") or []) + (
            workload.pod_spec.get("containers") or []
        ):
            for mount in container.get("volumeMounts") or []:
                mount_name = mount.get("name")
                if mount_name and mount_name not in declared_volumes:
                    errors.append(
                        f"{chart_path.name}: {workload.kind} {workload.name} mounts undeclared volume '{mount_name}'"
                    )

        service_account_name = workload.pod_spec.get("serviceAccountName")
        if (
            service_account_name
            and service_account_name != "default"
            and (workload.namespace, service_account_name) not in service_accounts
        ):
            errors.append(
                f"{chart_path.name}: {workload.kind} {workload.name} references missing ServiceAccount '{service_account_name}'"
            )

    assert not errors, "\n".join(errors)