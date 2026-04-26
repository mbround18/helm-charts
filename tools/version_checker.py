#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

import yaml


def log(level: str, msg: str) -> None:
    print(f"{level}: {msg}")


def run(cmd: List[str], cwd: Optional[Path] = None) -> str:
    out = subprocess.check_output(cmd, cwd=str(cwd) if cwd else None)
    return out.decode().strip()


def git(args: List[str]) -> str:
    return run(["git", *args])


def list_chart_dirs(charts_root: Path) -> List[Path]:
    return [p for p in charts_root.iterdir() if p.is_dir()]


SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def parse_semver(v: str) -> Optional[Tuple[int, int, int]]:
    m = SEMVER_RE.match(v)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def bump_version(v: str, bump: str) -> str:
    t = parse_semver(v)
    if not t:
        raise ValueError(f"Not a semver: {v}")
    major, minor, patch = t
    if bump == "major":
        return f"{major + 1}.0.0"
    if bump == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def build_latest_tag_map() -> Dict[str, Tuple[str, str, Tuple[int, int, int]]]:
    """Build a chart -> latest tag map using a single tag query for speed."""
    out = git(["tag", "-l", "*-*"])
    latest: Dict[str, Tuple[str, str, Tuple[int, int, int]]] = {}
    for raw_tag in out.splitlines():
        tag = raw_tag.strip()
        if not tag:
            continue
        m = re.match(r"^(?P<chart>.+)-(?P<version>\d+\.\d+\.\d+)$", tag)
        if not m:
            continue
        chart_name = m.group("chart")
        version = m.group("version")
        parsed = parse_semver(version)
        if parsed is None:
            continue
        current = latest.get(chart_name)
        if current is None or parsed > current[2]:
            latest[chart_name] = (tag, version, parsed)
    return latest


def get_commits_since(tag: str, path: Path) -> List[str]:
    rng = f"{tag}..HEAD"
    out = git(["log", "--format=%H", rng, "--", str(path)])
    return [line for line in out.splitlines() if line]


def has_changes_since(tag: str, path: Path) -> bool:
    rng = f"{tag}..HEAD"
    proc = subprocess.run(
        ["git", "diff", "--quiet", rng, "--", str(path)],
        check=False,
    )
    # exit code 1 means there are differences, 0 means no differences
    return proc.returncode == 1


def read_commit_message(commit: str) -> str:
    return git(["log", "--format=%B", "-n", "1", commit])


def find_pr_number(text: str) -> Optional[int]:
    m = re.search(r"#(\d+)", text)
    return int(m.group(1)) if m else None


def get_pr_labels(owner_repo: str, pr_number: int, token: Optional[str]) -> List[str]:
    # Use GitHub REST API: issues endpoint returns PR labels too
    import json
    import urllib.request

    url = f"https://api.github.com/repos/{owner_repo}/issues/{pr_number}"
    req = urllib.request.Request(url)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("X-GitHub-Api-Version", "2022-11-28")
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        log("WARNING", f"Failed to fetch PR #{pr_number} labels: {e}")
        return []
    labels = data.get("labels", [])
    names = []
    for lab in labels:
        name = lab.get("name")
        if isinstance(name, str):
            names.append(name)
    return names


def determine_bump(
    commits: Iterable[str],
    owner_repo: str,
    token: Optional[str],
    commit_message_cache: Dict[str, str],
    pr_labels_cache: Dict[int, List[str]],
) -> str:
    bump = "patch"
    seen_prs: Set[int] = set()
    for c in commits:
        if c not in commit_message_cache:
            commit_message_cache[c] = read_commit_message(c)
        msg = commit_message_cache[c]
        prn = find_pr_number(msg)
        if prn is None or prn in seen_prs:
            continue
        seen_prs.add(prn)

        labels: List[str] = []
        if owner_repo:
            if prn not in pr_labels_cache:
                pr_labels_cache[prn] = get_pr_labels(owner_repo, prn, token)
            labels = pr_labels_cache[prn]
        if any(label.lower() == "major" for label in labels):
            return "major"
        if any(label.lower() == "minor" for label in labels):
            bump = "minor"
        # otherwise default patch
    return bump


def load_chart_version(chart_yaml: Path) -> Optional[str]:
    with chart_yaml.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
        v = data.get("version")
        if isinstance(v, str):
            return v
    return None


def write_chart_version(chart_yaml: Path, new_version: str) -> None:
    with chart_yaml.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    data["version"] = new_version
    with chart_yaml.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, sort_keys=False)


def load_chart_data(chart_yaml: Path) -> dict:
    with chart_yaml.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return data if isinstance(data, dict) else {}


def write_chart_data(chart_yaml: Path, data: dict) -> None:
    with chart_yaml.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, sort_keys=False)


def sync_local_dependency_versions(
    charts_root: Path,
    bumped_versions: Dict[str, str],
) -> List[Path]:
    """Propagate local file:// dependency version bumps to consumer Chart.yaml files.

    Returns chart directories that were modified.
    """
    updated_chart_dirs: List[Path] = []

    for chart_dir in list_chart_dirs(charts_root):
        chart_yaml = chart_dir / "Chart.yaml"
        if not chart_yaml.exists():
            continue

        data = load_chart_data(chart_yaml)
        dependencies = data.get("dependencies")
        if not isinstance(dependencies, list):
            continue

        changed = False
        for dep in dependencies:
            if not isinstance(dep, dict):
                continue

            repository = dep.get("repository")
            dep_name = dep.get("name")
            dep_version = dep.get("version")
            if not (
                isinstance(repository, str)
                and repository.startswith("file://")
                and isinstance(dep_name, str)
                and isinstance(dep_version, str)
            ):
                continue

            target_version = bumped_versions.get(dep_name)
            if target_version and dep_version != target_version:
                log(
                    "INFO",
                    (
                        f"Updating local dependency version in {chart_yaml}: "
                        f"{dep_name} {dep_version} -> {target_version}"
                    ),
                )
                dep["version"] = target_version
                changed = True

        if changed:
            write_chart_data(chart_yaml, data)
            updated_chart_dirs.append(chart_dir)

    return updated_chart_dirs


def refresh_dependency_locks(chart_dirs: Iterable[Path]) -> List[Path]:
    """Regenerate Chart.lock files for updated consumer charts."""
    updated_lockfiles: List[Path] = []
    for chart_dir in chart_dirs:
        chart_yaml = chart_dir / "Chart.yaml"
        data = load_chart_data(chart_yaml)
        dependencies = data.get("dependencies") or []
        if not dependencies:
            continue

        lock_path = chart_dir / "Chart.lock"
        if not lock_path.exists():
            continue

        try:
<<<<<<< HEAD
            run(["helm", "dependency", "build", "--skip-refresh", str(chart_dir)])
=======
            run(
                ["helm", "dependency", "build", "--skip-refresh", str(chart_dir)]
            )
>>>>>>> a120b2965bea440ea3079b1e0f8c44a2377687c5
            updated_lockfiles.append(lock_path)
        except subprocess.CalledProcessError as e:
            log(
                "WARNING",
                f"Failed to refresh lockfile for {chart_dir.name}: {e}",
            )
    return updated_lockfiles


def get_repo_root() -> Path:
    try:
        return Path(run(["git", "rev-parse", "--show-toplevel"]))
    except Exception:
        return Path(__file__).resolve().parents[1]


def main() -> int:
    repo_root = get_repo_root()
    charts_root = repo_root / "charts"

    # Ensure tags are up to date
    try:
        git(["fetch", "--tags"])
    except subprocess.CalledProcessError as e:
        log("WARNING", f"git fetch --tags failed: {e}")

    event_name = os.environ.get("GITHUB_EVENT_NAME", "")
    dry_run = event_name == "pull_request"
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY") if dry_run else None
    owner_repo = os.environ.get("GITHUB_REPOSITORY", "")
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    latest_tags = build_latest_tag_map()
    commit_message_cache: Dict[str, str] = {}
    pr_labels_cache: Dict[int, List[str]] = {}
    updated_charts: List[Tuple[str, str, Path]] = []

    for chart_dir in list_chart_dirs(charts_root):
        chart_name = chart_dir.name
        chart_yaml = chart_dir / "Chart.yaml"
        log("INFO", f"Processing chart: {chart_name}")
        log("INFO", f"Chart path: {chart_yaml}")
        if not chart_yaml.exists():
            log("WARNING", f"Chart.yaml not found for {chart_name}, skipping.")
            continue

        latest = latest_tags.get(chart_name)
        if latest is None:
            msg = f"No previous tag found for {chart_name}, skipping version bump."
            log("WARNING", msg)
            if summary_file:
                with open(summary_file, "a", encoding="utf-8") as sf:
                    sf.write(f"- Chart: {chart_name} - {msg}\n")
            continue

        latest_tag, latest_ver, _ = latest
        log("INFO", f"Latest tag found: {latest_tag} (version: {latest_ver})")

        if not has_changes_since(latest_tag, chart_dir):
            msg = f"No changes found for {chart_name} since last release, skipping version bump."
            log("INFO", msg)
            if summary_file:
                with open(summary_file, "a", encoding="utf-8") as sf:
                    sf.write(
                        f"- Chart: {chart_name} - No changes since last release, skipping version bump.\n"
                    )
            continue

        log(
            "INFO",
            f"Changes detected for {chart_name} since the last release. Determining version bump type...",
        )
        commits = get_commits_since(latest_tag, chart_dir)
        bump = determine_bump(
            commits,
            owner_repo,
            token,
            commit_message_cache,
            pr_labels_cache,
        )
        log("INFO", f"Determined bump type: {bump}")

        # Determine base version to bump from: max(current Chart.yaml, latest tag)
        current_version = load_chart_version(chart_yaml)
        log("INFO", f"Current Chart.yaml version: {current_version}")
        latest_tuple = parse_semver(latest_ver) or (0, 0, 0)
        current_tuple = parse_semver(current_version or "0.0.0") or (0, 0, 0)
        base_version = current_version or latest_ver
        if current_tuple < latest_tuple:
            base_version = latest_ver
        if base_version != latest_ver:
            log("INFO", f"Using current Chart.yaml as base for bump: {base_version}")
        new_version = bump_version(base_version, bump)

        if dry_run:
            if summary_file:
                with open(summary_file, "a", encoding="utf-8") as sf:
                    sf.write(
                        f"- Chart: {chart_name} - Bump type: {bump} - New version: {new_version}\n"
                    )
            continue

        # Skip downgrade or no-op
        if current_version and (parse_semver(current_version) or (0, 0, 0)) >= (
            parse_semver(new_version) or (0, 0, 0)
        ):
            log(
                "INFO",
                f"{chart_name} already at version {current_version} >= target {new_version}, skipping update.",
            )
            continue

        log("INFO", f"Updating chart version in {chart_yaml} to {new_version}")
        write_chart_version(chart_yaml, new_version)
        updated_charts.append((chart_name, new_version, chart_yaml))

    if not dry_run:
        if not updated_charts:
            log("INFO", "No version updates were required. Skipping commit and push.")
            return 0

        bumped_versions = {name: version for name, version, _ in updated_charts}
        dependency_updated_chart_dirs = sync_local_dependency_versions(
            charts_root,
            bumped_versions,
        )
        updated_lockfiles = refresh_dependency_locks(dependency_updated_chart_dirs)

        # Batch all chart version bumps into one commit for faster CI and cleaner history.
        staged_paths = [str(chart_yaml) for _, _, chart_yaml in updated_charts]
        staged_paths.extend(
            str(chart_dir / "Chart.yaml") for chart_dir in dependency_updated_chart_dirs
        )
        staged_paths.extend(str(lockfile) for lockfile in updated_lockfiles)
        subprocess.check_call(["git", "add", *staged_paths])

        summary = ", ".join(f"{name}:{version}" for name, version, _ in updated_charts)
        commit_message = f"[skip ci] Robot commit: Bump chart versions ({summary})"
        subprocess.check_call(["git", "commit", "-m", commit_message])

        # Push to current branch
        ref = os.environ.get("GITHUB_REF", "")
        branch = (
            ref.split("/heads/")[-1]
            if "/heads/" in ref
            else run(["git", "symbolic-ref", "--short", "HEAD"])
        )  # type: ignore[arg-type]
        log("INFO", f"Pushing changes to branch: {branch}")
        subprocess.check_call(["git", "push", "origin", f"HEAD:{branch}"])

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as e:
        log("ERROR", f"Subprocess failed: {e}")
        raise SystemExit(1)
