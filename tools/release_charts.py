#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tarfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error, parse, request

import yaml
from packaging.version import InvalidVersion, Version


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACKAGE_DIR = REPO_ROOT / ".cr-release-packages"
DEFAULT_INDEX_WORKTREE = REPO_ROOT / ".cr-index"
DEFAULT_PAGES_BRANCH = "gh-pages"
DEFAULT_INDEX_PATH = Path("index.yaml")


@dataclass(frozen=True)
class ChartPackage:
    path: Path
    name: str
    version: str
    metadata: dict[str, Any]
    digest: str
    created: str

    @property
    def tag_name(self) -> str:
        return f"{self.name}-{self.version}"

    @property
    def filename(self) -> str:
        return self.path.name


def log(message: str) -> None:
    print(message, flush=True)


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return data if isinstance(data, dict) else {}


def dump_yaml(path: Path, data: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False)


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_chart_yaml_from_archive(package_path: Path) -> dict[str, Any]:
    with tarfile.open(package_path, mode="r:gz") as archive:
        chart_member = next(
            (
                member
                for member in archive.getmembers()
                if member.name.endswith("/Chart.yaml") or member.name == "Chart.yaml"
            ),
            None,
        )
        if chart_member is None:
            raise FileNotFoundError(f"Chart.yaml not found in {package_path}")

        extracted = archive.extractfile(chart_member)
        if extracted is None:
            raise FileNotFoundError(f"Failed to extract Chart.yaml from {package_path}")

        data = yaml.safe_load(extracted.read().decode("utf-8")) or {}
        if not isinstance(data, dict):
            raise ValueError(f"Chart.yaml in {package_path} did not parse as a mapping")
        return data


def load_chart_package(package_path: Path) -> ChartPackage:
    metadata = read_chart_yaml_from_archive(package_path)
    name = metadata.get("name")
    version = metadata.get("version")
    if not isinstance(name, str) or not isinstance(version, str):
        raise ValueError(f"Invalid chart metadata in {package_path}")

    return ChartPackage(
        path=package_path,
        name=name,
        version=version,
        metadata=metadata,
        digest=file_digest(package_path),
        created=utc_timestamp(),
    )


def discover_packages(package_dir: Path) -> list[ChartPackage]:
    packages = [load_chart_package(path) for path in sorted(package_dir.glob("*.tgz"))]
    if not packages:
        log(f"No chart packages found in {package_dir}")
    return packages


def semver_key(version: str) -> tuple[int, Version | str]:
    try:
        return (1, Version(version))
    except InvalidVersion:
        return (0, version)


def merge_index(
    existing_index: dict[str, Any],
    packages: list[ChartPackage],
    owner: str,
    repo: str,
) -> dict[str, Any]:
    entries = existing_index.get("entries")
    merged_entries: dict[str, list[dict[str, Any]]] = {}

    if isinstance(entries, dict):
        for chart_name, versions in entries.items():
            if isinstance(chart_name, str) and isinstance(versions, list):
                merged_entries[chart_name] = [
                    version for version in versions if isinstance(version, dict)
                ]

    for package in packages:
        chart_versions = merged_entries.setdefault(package.name, [])
        filtered_versions = [
            version_info
            for version_info in chart_versions
            if version_info.get("version") != package.version
        ]
        entry = dict(package.metadata)
        entry["digest"] = package.digest
        entry["created"] = package.created
        entry["urls"] = [
            f"https://github.com/{owner}/{repo}/releases/download/{package.tag_name}/{package.filename}"
        ]
        filtered_versions.append(entry)
        filtered_versions.sort(
            key=lambda version_info: semver_key(str(version_info.get("version", ""))),
            reverse=True,
        )
        merged_entries[package.name] = filtered_versions

    return {
        "apiVersion": existing_index.get("apiVersion", "v1"),
        "entries": dict(sorted(merged_entries.items())),
        "generated": utc_timestamp(),
    }


class GitHubClient:
    def __init__(self, owner: str, repo: str, token: str, api_base_url: str) -> None:
        self.owner = owner
        self.repo = repo
        self.token = token
        self.api_base_url = api_base_url.rstrip("/")
        parsed = parse.urlparse(self.api_base_url)
        if parsed.netloc == "api.github.com":
            self.upload_base_url = "https://uploads.github.com"
        else:
            self.upload_base_url = f"{parsed.scheme}://{parsed.netloc}"

    def _request(
        self,
        method: str,
        url: str,
        *,
        payload: bytes | None = None,
        content_type: str | None = "application/json",
        accept: str = "application/vnd.github+json",
    ) -> tuple[int, Any]:
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": accept,
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if content_type:
            headers["Content-Type"] = content_type

        req = request.Request(url, data=payload, headers=headers, method=method)
        try:
            with request.urlopen(req) as response:
                body = response.read()
                if not body:
                    return response.status, None
                if "application/json" in response.headers.get("Content-Type", ""):
                    return response.status, json.loads(body.decode("utf-8"))
                return response.status, body
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            if exc.code == 404:
                return exc.code, None
            raise RuntimeError(
                f"GitHub API error {exc.code} for {url}: {body}"
            ) from exc

    def get_release_by_tag(self, tag: str) -> dict[str, Any] | None:
        status, payload = self._request(
            "GET",
            f"{self.api_base_url}/repos/{self.owner}/{self.repo}/releases/tags/{tag}",
            payload=None,
            content_type=None,
        )
        return payload if status == 200 and isinstance(payload, dict) else None

    def create_release(self, tag: str, target_commitish: str) -> dict[str, Any]:
        payload = {
            "tag_name": tag,
            "name": tag,
            "target_commitish": target_commitish,
            "draft": False,
            "prerelease": False,
            "generate_release_notes": False,
        }
        _, created = self._request(
            "POST",
            f"{self.api_base_url}/repos/{self.owner}/{self.repo}/releases",
            payload=json.dumps(payload).encode("utf-8"),
        )
        if not isinstance(created, dict):
            raise RuntimeError(f"Failed to create release for {tag}")
        return created

    def ensure_release(self, tag: str, target_commitish: str) -> dict[str, Any]:
        release = self.get_release_by_tag(tag)
        if release is not None:
            return release

        log(f"Creating GitHub release {tag}")
        return self.create_release(tag, target_commitish)

    def upload_release_asset(
        self, release: dict[str, Any], package: ChartPackage
    ) -> None:
        assets = release.get("assets")
        if isinstance(assets, list):
            for asset in assets:
                if isinstance(asset, dict) and asset.get("name") == package.filename:
                    log(
                        f"Asset already present for {package.tag_name}: {package.filename}"
                    )
                    return

        upload_url = release.get("upload_url")
        release_id = release.get("id")
        if not isinstance(upload_url, str) and isinstance(release_id, int):
            upload_url = f"{self.upload_base_url}/repos/{self.owner}/{self.repo}/releases/{release_id}/assets{{?name,label}}"
        if not isinstance(upload_url, str):
            raise RuntimeError(f"Missing upload URL for release {package.tag_name}")

        upload_base = upload_url.split("{", 1)[0]
        url = f"{upload_base}?{parse.urlencode({'name': package.filename})}"
        log(f"Uploading asset for {package.tag_name}: {package.filename}")
        self._request(
            "POST",
            url,
            payload=package.path.read_bytes(),
            content_type="application/gzip",
        )


def git(*args: str, cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def ensure_git_worktree(repo_root: Path, branch: str, worktree_path: Path) -> None:
    if worktree_path.exists():
        git("worktree", "remove", "--force", str(worktree_path), cwd=repo_root)

    git("fetch", "origin", branch, cwd=repo_root)
    try:
        git("show-ref", "--verify", f"refs/remotes/origin/{branch}", cwd=repo_root)
        git(
            "worktree",
            "add",
            "--force",
            "-B",
            branch,
            str(worktree_path),
            f"origin/{branch}",
            cwd=repo_root,
        )
    except subprocess.CalledProcessError:
        git("worktree", "add", "--detach", str(worktree_path), cwd=repo_root)
        git("checkout", "--orphan", branch, cwd=worktree_path)
        for path in worktree_path.iterdir():
            if path.name == ".git":
                continue
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()


def update_pages_index(
    repo_root: Path,
    packages: list[ChartPackage],
    owner: str,
    repo: str,
    branch: str,
    worktree_path: Path,
    index_relative_path: Path,
) -> None:
    ensure_git_worktree(repo_root, branch, worktree_path)
    try:
        index_path = worktree_path / index_relative_path
        existing_index = load_yaml(index_path)
        merged_index = merge_index(existing_index, packages, owner, repo)
        index_path.parent.mkdir(parents=True, exist_ok=True)
        dump_yaml(index_path, merged_index)

        status = git(
            "status", "--porcelain", "--", str(index_relative_path), cwd=worktree_path
        )
        if not status:
            log("No gh-pages index changes detected")
            return

        git("add", str(index_relative_path), cwd=worktree_path)
        git("commit", "-m", "Update index.yaml", cwd=worktree_path)
        git("push", "origin", f"HEAD:{branch}", cwd=worktree_path)
    finally:
        if worktree_path.exists():
            git("worktree", "remove", "--force", str(worktree_path), cwd=repo_root)


def parse_owner_repo(value: str | None) -> tuple[str | None, str | None]:
    if not value or "/" not in value:
        return None, None
    owner, repo = value.split("/", 1)
    return owner, repo


def load_config(path: Path | None) -> dict[str, Any]:
    return load_yaml(path) if path else {}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Publish chart packages to GitHub releases and rebuild gh-pages index.yaml."
    )
    parser.add_argument(
        "--package-path",
        type=Path,
        default=DEFAULT_PACKAGE_DIR,
        help="Directory containing packaged chart .tgz files.",
    )
    parser.add_argument(
        "--pages-branch",
        default=DEFAULT_PAGES_BRANCH,
        help="Git branch that hosts the Helm repository index.",
    )
    parser.add_argument(
        "--index-path",
        type=Path,
        default=DEFAULT_INDEX_PATH,
        help="Path to index.yaml inside the gh-pages worktree.",
    )
    parser.add_argument(
        "--worktree-path",
        type=Path,
        default=DEFAULT_INDEX_WORKTREE,
        help="Temporary git worktree path used for the pages branch.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Optional chart releaser style config file.",
    )
    parser.add_argument(
        "--owner",
        default=None,
        help="GitHub owner/org. Defaults to cr.yaml or GITHUB_REPOSITORY.",
    )
    parser.add_argument(
        "--repo",
        default=None,
        help="GitHub repository name. Defaults to GITHUB_REPOSITORY.",
    )
    parser.add_argument(
        "--git-base-url",
        default=None,
        help="GitHub API base URL. Defaults to cr.yaml or https://api.github.com.",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Accepted for workflow compatibility. Existing assets are always left in place.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config(args.config)

    owner = args.owner or config.get("owner")
    repo = args.repo
    env_owner, env_repo = parse_owner_repo(os.environ.get("GITHUB_REPOSITORY"))
    owner = owner or env_owner
    repo = repo or env_repo
    if not owner or not repo:
        raise SystemExit("Unable to determine GitHub owner/repository")

    api_base_url = (
        args.git_base_url or config.get("git-base-url") or "https://api.github.com"
    )
    token = (
        os.environ.get("GH_TOKEN")
        or os.environ.get("GITHUB_TOKEN")
        or os.environ.get("CR_TOKEN")
    )
    if not token:
        raise SystemExit("GH_TOKEN, GITHUB_TOKEN, or CR_TOKEN must be set")

    packages = discover_packages(args.package_path)
    if not packages:
        return 0

    target_commitish = git("rev-parse", "HEAD", cwd=REPO_ROOT)
    client = GitHubClient(owner, repo, token, api_base_url)

    for package in packages:
        log(f"Publishing {package.filename} as release {package.tag_name}")
        release = client.ensure_release(package.tag_name, target_commitish)
        client.upload_release_asset(release, package)

    update_pages_index(
        repo_root=REPO_ROOT,
        packages=packages,
        owner=owner,
        repo=repo,
        branch=args.pages_branch,
        worktree_path=args.worktree_path,
        index_relative_path=args.index_path,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
