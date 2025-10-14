#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

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
        return f"{major+1}.0.0"
    if bump == "minor":
        return f"{major}.{minor+1}.0"
    return f"{major}.{minor}.{patch+1}"


def find_latest_chart_tag(chart_name: str) -> Optional[Tuple[str, str]]:
    tags = git(["tag", "-l", f"{chart_name}-*"]).splitlines()
    best: Optional[Tuple[int, int, int]] = None
    best_tag: Optional[str] = None
    best_ver: Optional[str] = None
    for t in tags:
        ver = t.split("-", 1)[1] if "-" in t else ""
        st = parse_semver(ver)
        if st is None:
            continue
        if best is None or st > best:
            best = st
            best_tag = t
            best_ver = ver
    if best_tag and best_ver:
        return best_tag, best_ver
    return None


def get_commits_since(tag: str, path: Path) -> List[str]:
    rng = f"{tag}..HEAD"
    out = git(["log", "--format=%H", rng, "--", str(path)])
    return [line for line in out.splitlines() if line]


def get_changed_files_since(tag: str, path: Path) -> List[str]:
    rng = f"{tag}..HEAD"
    out = git(["diff", "--name-only", rng, "--", str(path)])
    return [line for line in out.splitlines() if line]


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


def determine_bump(commits: Iterable[str], chart_path: Path, owner_repo: str, token: Optional[str]) -> str:
    bump = "patch"
    for c in commits:
        msg = read_commit_message(c)
        prn = find_pr_number(msg)
        if prn is not None:
            labels: List[str] = []
            if owner_repo:
                labels = get_pr_labels(owner_repo, prn, token)
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

    for chart_dir in list_chart_dirs(charts_root):
        chart_name = chart_dir.name
        chart_yaml = chart_dir / "Chart.yaml"
        log("INFO", f"Processing chart: {chart_name}")
        log("INFO", f"Chart path: {chart_yaml}")
        if not chart_yaml.exists():
            log("WARNING", f"Chart.yaml not found for {chart_name}, skipping.")
            continue

        latest = find_latest_chart_tag(chart_name)
        if latest is None:
            msg = f"No previous tag found for {chart_name}, skipping version bump."
            log("WARNING", msg)
            if summary_file:
                with open(summary_file, "a", encoding="utf-8") as sf:
                    sf.write(f"- Chart: {chart_name} - {msg}\n")
            continue

        latest_tag, latest_ver = latest
        log("INFO", f"Latest tag found: {latest_tag} (version: {latest_ver})")
        # last tag commit only for log parity
        last_tag_commit = git(["rev-list", "-n", "1", latest_tag])
        log("INFO", f"Last tag commit: {last_tag_commit}")

        changed = get_changed_files_since(latest_tag, chart_dir)
        if not changed:
            msg = f"No changes found for {chart_name} since last release, skipping version bump."
            log("INFO", msg)
            if summary_file:
                with open(summary_file, "a", encoding="utf-8") as sf:
                    sf.write(f"- Chart: {chart_name} - No changes since last release, skipping version bump.\n")
            continue

        log("INFO", f"Changes detected for {chart_name} since the last release. Determining version bump type...")
        commits = get_commits_since(latest_tag, chart_dir)
        bump = determine_bump(commits, chart_dir, owner_repo, token)
        log("INFO", f"Determined bump type: {bump}")

        # Determine base version to bump from: max(current Chart.yaml, latest tag)
        current_version = load_chart_version(chart_yaml)
        log("INFO", f"Current Chart.yaml version: {current_version}")
        latest_tuple = parse_semver(latest_ver) or (0, 0, 0)
        current_tuple = parse_semver(current_version or "0.0.0") or (0, 0, 0)
        base_version = (current_version or latest_ver)
        if current_tuple < latest_tuple:
            base_version = latest_ver
        if base_version != latest_ver:
            log("INFO", f"Using current Chart.yaml as base for bump: {base_version}")
        new_version = bump_version(base_version, bump)

        if dry_run:
            if summary_file:
                with open(summary_file, "a", encoding="utf-8") as sf:
                    sf.write(f"- Chart: {chart_name} - Bump type: {bump} - New version: {new_version}\n")
            continue

        # Skip downgrade or no-op
        if current_version and (parse_semver(current_version) or (0, 0, 0)) >= (parse_semver(new_version) or (0, 0, 0)):
            log("INFO", f"{chart_name} already at version {current_version} >= target {new_version}, skipping update.")
            continue

        log("INFO", f"Updating chart version in {chart_yaml} to {new_version}")
        write_chart_version(chart_yaml, new_version)

        # Stage and commit if changed
        try:
            subprocess.check_call(["git", "add", str(chart_yaml)])
            # If nothing changed, commit will fail; ignore
            subprocess.check_call([
                "git",
                "commit",
                "-m",
                f"[skip ci] Robot commit: Bumping chart version for {chart_name} to {new_version}",
            ])
            log("INFO", f"Version bump commit created for {chart_name}")
        except subprocess.CalledProcessError as e:
            log("WARNING", f"Git commit failed (possibly no changes); continuing. {e}")

    if not dry_run:
        # Push to current branch
        ref = os.environ.get("GITHUB_REF", "")
        branch = ref.split("/heads/")[-1] if "/heads/" in ref else run(["git", "symbolic-ref", "--short", "HEAD"])  # type: ignore[arg-type]
        log("INFO", f"Pushing changes to branch: {branch}")
        subprocess.check_call(["git", "push", "origin", f"HEAD:{branch}"])

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as e:
        log("ERROR", f"Subprocess failed: {e}")
        raise SystemExit(1)