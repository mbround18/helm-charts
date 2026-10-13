from pathlib import Path

import pytest

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
    return next(document for document in documents if document.get("kind") == kind)


def test_argocd_metadata_is_not_rendered_by_default():
    documents = _render()

    statefulset = _document_by_kind(documents, "StatefulSet")
    service = _document_by_kind(documents, "Service")

    assert "annotations" not in statefulset["metadata"]
    assert "annotations" not in service["metadata"]
    assert "argocd.argoproj.io/instance" not in statefulset["metadata"]["labels"]


def test_argocd_metadata_renders_when_application_api_is_available():
    documents = _render(api_versions=["argoproj.io/v1alpha1/Application"])

    statefulset = _document_by_kind(documents, "StatefulSet")
    service_account = _document_by_kind(documents, "ServiceAccount")
    service = _document_by_kind(documents, "Service")

    assert (
        statefulset["metadata"]["annotations"]["argocd.argoproj.io/sync-wave"] == "30"
    )
    assert (
        service_account["metadata"]["annotations"]["argocd.argoproj.io/sync-wave"]
        == "0"
    )
    assert service["metadata"]["annotations"]["argocd.argoproj.io/sync-wave"] == "40"


@pytest.mark.parametrize(
    ("values", "expected_kind", "expected_wave"),
    [
        ({"ingress": {"enabled": True}}, "Ingress", "40"),
        (
            {"istio": {"enabled": True, "gateway": {"selector": {"istio": "ingress"}}}},
            "VirtualService",
            "40",
        ),
        ({"backup_cleanup": {"enabled": True}}, "CronJob", "20"),
    ],
)
def test_argocd_force_mode_applies_expected_phase_annotations(
    values, expected_kind, expected_wave
):
    documents = _render(
        values={
            "argoCd": {
                "mode": "enabled",
                "instanceLabel": "foundry-prod",
            },
            **values,
        }
    )

    resource = _document_by_kind(documents, expected_kind)
    statefulset = _document_by_kind(documents, "StatefulSet")

    assert (
        statefulset["metadata"]["labels"]["argocd.argoproj.io/instance"]
        == "foundry-prod"
    )
    assert (
        resource["metadata"]["annotations"]["argocd.argoproj.io/sync-wave"]
        == expected_wave
    )


def _backup_cleanup_job(values=None):
    documents = _render({"backup_cleanup": {"enabled": True, **(values or {})}})
    return _document_by_kind(documents, "CronJob")["spec"]["jobTemplate"]["spec"]


def test_backup_cleanup_runs_as_non_root_without_installing_packages():
    job = _backup_cleanup_job()
    container = job["template"]["spec"]["containers"][0]
    script = " ".join(container["args"])

    # apk needs root; the container runs as uid 1000, so `apk add` fails
    # before the cleanup starts. BusyBox's find has -mtime and -delete.
    assert container["securityContext"]["runAsNonRoot"] is True
    assert "apk" not in script
    assert "find /foundrydata/Backups -type f -mtime +30 -delete" in script


def test_backup_cleanup_keeps_finished_jobs_for_a_day():
    # A 5-minute TTL deleted failed Jobs, and their logs, long before
    # anyone could read them; failedJobsHistoryLimit never got a say.
    assert _backup_cleanup_job()["ttlSecondsAfterFinished"] == 86400
    assert (
        _backup_cleanup_job({"ttlSecondsAfterFinished": 600})["ttlSecondsAfterFinished"]
        == 600
    )


def _backup_cron_job(values=None):
    documents = _render(values)
    return next(
        (
            d
            for d in documents
            if d.get("kind") == "CronJob" and d["metadata"]["name"].endswith("-backup")
        ),
        None,
    )


def test_backup_archives_data_nightly_by_default():
    cron = _backup_cron_job()
    assert cron is not None
    assert cron["spec"]["schedule"] == "0 1 * * *"
    assert cron["spec"]["concurrencyPolicy"] == "Forbid"

    job = cron["spec"]["jobTemplate"]["spec"]
    assert job["ttlSecondsAfterFinished"] == 86400
    pod = job["template"]["spec"]
    container = pod["containers"][0]
    script = " ".join(container["args"])
    assert container["securityContext"]["runAsNonRoot"] is True
    assert "apk" not in script
    assert "tar -czf" in script
    assert "KEEP=7" in script

    mounts = {m["name"]: m["mountPath"] for m in container["volumeMounts"]}
    assert mounts == {"data": "/foundrydata/Data", "backups": "/foundrydata/Backups"}
    claims = {
        v["name"]: v["persistentVolumeClaim"]["claimName"] for v in pod["volumes"]
    }
    assert claims["data"].startswith("data-") and claims["data"].endswith("-0")
    assert claims["backups"].startswith("backups-") and claims["backups"].endswith("-0")


def test_backup_follows_its_values():
    cron = _backup_cron_job({"backup": {"schedule": "30 3 * * *", "keep": 3}})
    assert cron["spec"]["schedule"] == "30 3 * * *"
    script = " ".join(
        cron["spec"]["jobTemplate"]["spec"]["template"]["spec"]["containers"][0]["args"]
    )
    assert "KEEP=3" in script


def test_backup_is_not_rendered_when_disabled_or_without_its_volumes():
    assert _backup_cron_job({"backup": {"enabled": False}}) is None
    assert (
        _backup_cron_job({"volumeClaimTemplates": {"data": {"enabled": False}}}) is None
    )
    assert (
        _backup_cron_job({"volumeClaimTemplates": {"backups": {"enabled": False}}})
        is None
    )
