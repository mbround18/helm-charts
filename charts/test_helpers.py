import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml


DEFAULT_RELEASE_NAME = "release-name"
DEFAULT_NAMESPACE = "contract-tests"
SNAPSHOT_NAMESPACE = "dev-testing"

WORKLOAD_PATHS = {
    "Deployment": ("spec", "template", "spec"),
    "StatefulSet": ("spec", "template", "spec"),
    "DaemonSet": ("spec", "template", "spec"),
    "Job": ("spec", "template", "spec"),
    "CronJob": ("spec", "jobTemplate", "spec", "template", "spec"),
    "Pod": ("spec",),
}


@dataclass(frozen=True)
class WorkloadManifest:
    kind: str
    name: str
    namespace: str
    pod_labels: dict[str, Any]
    pod_spec: dict[str, Any]
    volume_claim_template_names: tuple[str, ...] = ()


def load_chart_metadata(chart_path: Path) -> dict[str, Any]:
    return yaml.safe_load((chart_path / "Chart.yaml").read_text(encoding="utf-8")) or {}


def application_chart_directories(charts_root: Path | None = None) -> list[Path]:
    root = charts_root or Path(__file__).resolve().parent
    chart_dirs = sorted(path.parent for path in root.glob("*/Chart.yaml"))
    return [
        chart_dir
        for chart_dir in chart_dirs
        if load_chart_metadata(chart_dir).get("type", "application") != "library"
    ]


def resource_namespace(
    document: dict[str, Any], default_namespace: str = DEFAULT_NAMESPACE
) -> str:
    metadata = document.get("metadata") or {}
    return metadata.get("namespace") or default_namespace


def resource_name(document: dict[str, Any]) -> str | None:
    metadata = document.get("metadata") or {}
    return metadata.get("name")


def resource_identity(
    document: dict[str, Any], default_namespace: str = DEFAULT_NAMESPACE
) -> tuple[str, str, str]:
    return (
        resource_namespace(document, default_namespace),
        document.get("kind") or "<unknown>",
        resource_name(document) or "<missing-name>",
    )


def _normalize_checksum_annotations(value):
    if isinstance(value, dict):
        annotations = value.get("annotations")
        if isinstance(annotations, dict):
            for key in annotations:
                if key.startswith("checksum/"):
                    annotations[key] = f"<normalized:{key}>"

        for child in value.values():
            _normalize_checksum_annotations(child)
    elif isinstance(value, list):
        for item in value:
            _normalize_checksum_annotations(item)


def _normalize_secret_payloads(documents):
    for document in documents:
        if not isinstance(document, dict) or document.get("kind") != "Secret":
            continue

        for field in ("data", "stringData"):
            payload = document.get(field)
            if isinstance(payload, dict):
                for key in payload:
                    payload[key] = f"<redacted:{key}>"


def render_chart_documents(
    chart_path: Path,
    *,
    values: dict[str, Any] | None = None,
    release_name: str = DEFAULT_RELEASE_NAME,
    namespace: str = DEFAULT_NAMESPACE,
    api_versions: list[str] | None = None,
) -> list[Any]:
    command = [
        "helm",
        "template",
        release_name,
        str(chart_path),
        "--namespace",
        namespace,
    ]

    for api_version in api_versions or []:
        command.extend(["--api-versions", api_version])

    values_file = None
    if values:
        values_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        )
        yaml.safe_dump(values, values_file)
        values_file.flush()
        command.extend(["--values", values_file.name])

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
        )
    finally:
        if values_file is not None:
            Path(values_file.name).unlink(missing_ok=True)

    return list(yaml.safe_load_all(result.stdout))


def render_chart_snapshot(chart_path: Path, *, normalize_secrets: bool = False) -> str:
    rendered_templates = render_chart_documents(
        chart_path,
        release_name=DEFAULT_RELEASE_NAME,
        namespace=SNAPSHOT_NAMESPACE,
    )
    _normalize_checksum_annotations(rendered_templates)

    if normalize_secrets:
        _normalize_secret_payloads(rendered_templates)

    return yaml.dump_all(rendered_templates)


def iter_workloads(
    documents: Iterable[Any], default_namespace: str = DEFAULT_NAMESPACE
) -> list[WorkloadManifest]:
    workloads: list[WorkloadManifest] = []

    for document in documents:
        if not isinstance(document, dict):
            continue

        path = WORKLOAD_PATHS.get(document.get("kind"))
        if not path:
            continue

        current: Any = document
        for key in path:
            current = (current or {}).get(key)

        if not isinstance(current, dict):
            continue

        if document.get("kind") == "Pod":
            pod_labels = (document.get("metadata") or {}).get("labels") or {}
        else:
            pod_labels = (
                ((document.get("spec") or {}).get("template") or {}).get("metadata")
                or {}
            ).get("labels") or {}

        claim_templates = tuple(
            template.get("metadata", {}).get("name")
            for template in (document.get("spec") or {}).get("volumeClaimTemplates")
            or []
            if template.get("metadata", {}).get("name")
        )

        name = resource_name(document)
        if not name:
            continue

        workloads.append(
            WorkloadManifest(
                kind=document["kind"],
                name=name,
                namespace=resource_namespace(document, default_namespace),
                pod_labels=pod_labels,
                pod_spec=current,
                volume_claim_template_names=claim_templates,
            )
        )

    return workloads
