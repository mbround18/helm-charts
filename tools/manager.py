#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.versioning.charts import (  # noqa: E402
    list_chart_dirs,
    load_chart_type,
    load_chart_version,
    refresh_dependency_locks,
    sync_local_dependency_versions,
    write_chart_version,
)
from tools.versioning.common import append_summary, bump_version, log, parse_semver  # noqa: E402
from tools.versioning.git_ops import GitClient  # noqa: E402
from tools.versioning.github_api import GitHubClient  # noqa: E402
from tools.versioning.models import ChartUpdate, VersionBumpConfig  # noqa: E402


TAG_RE = re.compile(r"^(?P<chart>.+)-(?P<version>\d+\.\d+\.\d+)$")
PR_RE = re.compile(r"#(\d+)")


class VersionBumpManager:
    def __init__(self, config: VersionBumpConfig) -> None:
        self.config = config
        self.git = GitClient(config.repo_root)
        self.github = GitHubClient(config.owner_repo, config.github_token)

    def run(self) -> int:
        if self.config.fetch_tags:
            try:
                self.git.fetch_tags()
            except subprocess.CalledProcessError as exc:
                log("WARNING", f"git fetch --tags failed: {exc}")

        latest_tags = self._build_latest_tag_map()
        updates: list[ChartUpdate] = []

        for chart_dir in list_chart_dirs(self.config.charts_root):
            update = self._plan_chart_update(chart_dir, latest_tags)
            if update is not None:
                updates.append(update)

        if self.config.dry_run:
            return 0

        if not updates:
            log("INFO", "No version updates were required. Skipping commit and push.")
            return 0

        self._apply_updates(updates)
        return 0

    def _build_latest_tag_map(self) -> dict[str, tuple[str, str, tuple[int, int, int]]]:
        latest: dict[str, tuple[str, str, tuple[int, int, int]]] = {}

        for tag in self.git.list_tags("*-*"):
            match = TAG_RE.match(tag)
            if match is None:
                continue

            chart_name = match.group("chart")
            version = match.group("version")
            parsed = parse_semver(version)
            if parsed is None:
                continue

            current = latest.get(chart_name)
            if current is None or parsed > current[2]:
                latest[chart_name] = (tag, version, parsed)

        return latest

    def _plan_chart_update(
        self,
        chart_dir: Path,
        latest_tags: dict[str, tuple[str, str, tuple[int, int, int]]],
    ) -> ChartUpdate | None:
        chart_name = chart_dir.name
        chart_yaml = chart_dir / "Chart.yaml"
        log("INFO", f"Processing chart: {chart_name}")
        log("INFO", f"Chart path: {chart_yaml}")

        if not chart_yaml.exists():
            log("WARNING", f"Chart.yaml not found for {chart_name}, skipping.")
            return None

        if load_chart_type(chart_yaml) == "library":
            message = f"Chart: {chart_name} - Library chart, skipping version bump."
            log("INFO", message)
            append_summary(self.config.summary_file, f"- {message}")
            return None

        latest = latest_tags.get(chart_name)
        if latest is None:
            message = (
                f"Chart: {chart_name} - No previous tag found, skipping version bump."
            )
            log("WARNING", message)
            append_summary(self.config.summary_file, f"- {message}")
            return None

        latest_tag, latest_version, latest_tuple = latest
        log("INFO", f"Latest tag found: {latest_tag} (version: {latest_version})")

        if not self.git.has_changes(f"{latest_tag}..HEAD", chart_dir):
            message = f"Chart: {chart_name} - No changes since last release, skipping version bump."
            log("INFO", message)
            append_summary(self.config.summary_file, f"- {message}")
            return None

        bump = self._determine_bump(latest_tag, chart_dir)
        current_version = load_chart_version(chart_yaml)
        current_tuple = parse_semver(current_version or "0.0.0") or (0, 0, 0)
        base_version = (
            latest_version
            if current_tuple < latest_tuple
            else (current_version or latest_version)
        )
        new_version = bump_version(base_version, bump)

        log("INFO", f"Current Chart.yaml version: {current_version}")
        log("INFO", f"Determined bump type: {bump}")
        log("INFO", f"Target version: {new_version}")

        append_summary(
            self.config.summary_file,
            f"- Chart: {chart_name} - Bump type: {bump} - New version: {new_version}",
        )

        if self.config.dry_run:
            return None

        if current_version and (parse_semver(current_version) or (0, 0, 0)) >= (
            parse_semver(new_version) or (0, 0, 0)
        ):
            log(
                "INFO",
                f"{chart_name} already at version {current_version} >= target {new_version}, skipping update.",
            )
            return None

        return ChartUpdate(
            chart_name=chart_name,
            chart_dir=chart_dir,
            chart_yaml=chart_yaml,
            current_version=current_version,
            new_version=new_version,
            bump=bump,
        )

    def _determine_bump(self, latest_tag: str, chart_dir: Path) -> str:
        bump = "patch"
        commit_text = self.git.log_text(f"{latest_tag}..HEAD", chart_dir, "%s %b")
        pull_requests = {int(match.group(1)) for match in PR_RE.finditer(commit_text)}

        for pull_request in pull_requests:
            labels = self.github.get_pr_labels(pull_request)
            lowered = {label.lower() for label in labels}
            if "major" in lowered:
                return "major"
            if "minor" in lowered:
                bump = "minor"

        return bump

    def _apply_updates(self, updates: list[ChartUpdate]) -> None:
        for update in updates:
            log(
                "INFO",
                f"Updating chart version in {update.chart_yaml} to {update.new_version}",
            )
            write_chart_version(update.chart_yaml, update.new_version)

        bumped_versions = {update.chart_name: update.new_version for update in updates}
        dependency_chart_dirs = sync_local_dependency_versions(
            self.config.charts_root, bumped_versions
        )
        refreshed_lockfiles = refresh_dependency_locks(dependency_chart_dirs)

        staged_paths = {update.chart_yaml for update in updates}
        for chart_dir in dependency_chart_dirs:
            staged_paths.add(chart_dir / "Chart.yaml")
        staged_paths.update(refreshed_lockfiles)
        self.git.stage_paths(staged_paths)

        summary = ", ".join(
            f"{update.chart_name}:{update.new_version}" for update in updates
        )
        commit_message = f"[skip ci] Robot commit: Bump chart versions ({summary})"
        self.git.commit(commit_message)

        if not self.config.push_changes:
            log("INFO", "Push disabled; leaving committed changes in the local branch.")
            return

        branch = os.environ.get("GITHUB_REF", "")
        branch_name = (
            branch.split("/heads/")[-1]
            if "/heads/" in branch
            else self.git.current_branch()
        )
        log("INFO", f"Pushing changes to branch: {branch_name}")
        self.git.push(branch_name)


def build_config(args: argparse.Namespace) -> VersionBumpConfig:
    repo_root = args.repo_root
    if repo_root is None:
        try:
            repo_root = GitClient.discover_repo_root()
        except subprocess.CalledProcessError:
            repo_root = REPO_ROOT

    dry_run = args.dry_run or os.environ.get("GITHUB_EVENT_NAME") == "pull_request"
    push_changes = args.push or os.environ.get("GITHUB_ACTIONS") == "true"
    summary_path = args.summary_file
    if summary_path is None and dry_run:
        summary_env = os.environ.get("GITHUB_STEP_SUMMARY")
        summary_path = Path(summary_env) if summary_env else None

    return VersionBumpConfig(
        repo_root=repo_root,
        charts_root=repo_root / "charts",
        dry_run=dry_run,
        push_changes=push_changes and not dry_run,
        fetch_tags=not args.skip_fetch_tags,
        owner_repo=os.environ.get("GITHUB_REPOSITORY", ""),
        github_token=os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN"),
        summary_file=summary_path,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage chart version bumps.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report planned bumps without editing files.",
    )
    parser.add_argument(
        "--push",
        action="store_true",
        help="Push the generated commit to the current branch.",
    )
    parser.add_argument(
        "--skip-fetch-tags",
        action="store_true",
        help="Skip refreshing git tags before scanning chart releases.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Override the repository root used for chart discovery.",
    )
    parser.add_argument(
        "--summary-file",
        type=Path,
        default=None,
        help="Optional GitHub Actions summary file to append dry-run output to.",
    )
    return parser.parse_args()


def main() -> int:
    config = build_config(parse_args())
    manager = VersionBumpManager(config)
    return manager.run()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        log("ERROR", f"Subprocess failed: {exc}")
        raise SystemExit(1)
