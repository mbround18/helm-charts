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


def read_values_yaml_from_archive(package_path: Path) -> str:
    with tarfile.open(package_path, mode="r:gz") as archive:
        member = next(
            (
                m
                for m in archive.getmembers()
                if m.name.endswith("/values.yaml") or m.name == "values.yaml"
            ),
            None,
        )
        if member is None:
            return ""
        extracted = archive.extractfile(member)
        if extracted is None:
            return ""
        return extracted.read().decode("utf-8")


def load_charts_data(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return data if isinstance(data, dict) else {}


def merge_charts_data(
    existing: dict[str, Any], packages: list[ChartPackage]
) -> dict[str, Any]:
    merged: dict[str, Any] = {k: dict(v) for k, v in existing.items() if isinstance(v, dict)}
    for package in packages:
        chart_versions = merged.setdefault(package.name, {})
        chart_versions[package.version] = read_values_yaml_from_archive(package.path)
    return merged


def generate_index_html(
    merged_index: dict[str, Any],
    charts_data: dict[str, Any],
    owner: str,
    repo: str,
) -> str:
    entries: dict[str, list[dict[str, Any]]] = merged_index.get("entries", {})

    charts_json_list = []
    for chart_name, versions in sorted(entries.items()):
        if not versions:
            continue
        latest = versions[0]
        all_versions = [v.get("version", "") for v in versions]
        values_by_version = charts_data.get(chart_name, {})
        charts_json_list.append({
            "name": chart_name,
            "description": latest.get("description", ""),
            "appVersion": latest.get("appVersion", ""),
            "latestVersion": latest.get("version", ""),
            "icon": latest.get("icon", ""),
            "home": latest.get("home", ""),
            "keywords": latest.get("keywords", []),
            "versions": all_versions,
            "valuesByVersion": values_by_version,
        })

    charts_json = json.dumps(charts_json_list, indent=None, separators=(",", ":"))
    repo_url = f"https://github.com/{owner}/{repo}"
    helm_repo_url = f"https://{owner}.github.io/{repo}"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{repo} — Helm Charts</title>
  <script src="https://cdn.jsdelivr.net/npm/flexsearch@0.7.43/dist/flexsearch.bundle.js"></script>
  <style>
    :root {{
      --bg: #0d1117;
      --bg2: #161b22;
      --bg3: #21262d;
      --border: #30363d;
      --text: #e6edf3;
      --text2: #8b949e;
      --accent: #58a6ff;
      --accent2: #1f6feb;
      --green: #3fb950;
      --tag-bg: #1f2f3f;
      --tag-text: #79c0ff;
      --code-bg: #161b22;
      --shadow: 0 4px 24px rgba(0,0,0,0.4);
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
      min-height: 100vh;
    }}
    header {{
      background: var(--bg2);
      border-bottom: 1px solid var(--border);
      padding: 1.25rem 2rem;
      display: flex;
      align-items: center;
      gap: 1.5rem;
      position: sticky;
      top: 0;
      z-index: 100;
    }}
    header h1 {{
      font-size: 1.25rem;
      font-weight: 600;
      color: var(--text);
      white-space: nowrap;
    }}
    header h1 a {{ color: inherit; text-decoration: none; }}
    header h1 a:hover {{ color: var(--accent); }}
    .helm-add {{
      font-size: 0.78rem;
      color: var(--text2);
      background: var(--bg3);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 0.35rem 0.75rem;
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      cursor: pointer;
      white-space: nowrap;
      display: flex;
      align-items: center;
      gap: 0.5rem;
      transition: border-color 0.15s;
    }}
    .helm-add:hover {{ border-color: var(--accent); color: var(--accent); }}
    .copy-icon {{ font-size: 0.9rem; }}
    #search-wrap {{
      flex: 1;
      max-width: 480px;
    }}
    #search {{
      width: 100%;
      padding: 0.5rem 0.85rem;
      background: var(--bg3);
      border: 1px solid var(--border);
      border-radius: 6px;
      color: var(--text);
      font-size: 0.9rem;
      outline: none;
      transition: border-color 0.15s;
    }}
    #search::placeholder {{ color: var(--text2); }}
    #search:focus {{ border-color: var(--accent); }}
    .stats {{
      color: var(--text2);
      font-size: 0.8rem;
      white-space: nowrap;
    }}
    main {{
      max-width: 1280px;
      margin: 0 auto;
      padding: 2rem 1.5rem;
    }}
    #results-count {{
      color: var(--text2);
      font-size: 0.85rem;
      margin-bottom: 1.25rem;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
      gap: 1rem;
    }}
    .card {{
      background: var(--bg2);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 1.25rem;
      display: flex;
      flex-direction: column;
      gap: 0.75rem;
      cursor: pointer;
      transition: border-color 0.15s, box-shadow 0.15s;
    }}
    .card:hover {{ border-color: var(--accent2); box-shadow: var(--shadow); }}
    .card.open {{ border-color: var(--accent); }}
    .card-header {{
      display: flex;
      align-items: flex-start;
      gap: 0.85rem;
    }}
    .card-icon {{
      width: 40px;
      height: 40px;
      border-radius: 8px;
      object-fit: contain;
      background: var(--bg3);
      padding: 4px;
      flex-shrink: 0;
    }}
    .card-icon-placeholder {{
      width: 40px;
      height: 40px;
      border-radius: 8px;
      background: var(--bg3);
      border: 1px solid var(--border);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 1.2rem;
      flex-shrink: 0;
    }}
    .card-title {{ font-size: 1rem; font-weight: 600; color: var(--text); }}
    .card-title a {{ color: inherit; text-decoration: none; }}
    .card-title a:hover {{ color: var(--accent); }}
    .card-version {{ font-size: 0.78rem; color: var(--text2); margin-top: 2px; }}
    .card-desc {{
      font-size: 0.85rem;
      color: var(--text2);
      line-height: 1.5;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }}
    .card-tags {{
      display: flex;
      flex-wrap: wrap;
      gap: 0.4rem;
    }}
    .tag {{
      font-size: 0.72rem;
      background: var(--tag-bg);
      color: var(--tag-text);
      border-radius: 4px;
      padding: 0.15rem 0.5rem;
    }}
    .card-detail {{
      display: none;
      flex-direction: column;
      gap: 0.75rem;
      border-top: 1px solid var(--border);
      padding-top: 0.75rem;
    }}
    .card.open .card-detail {{ display: flex; }}
    .version-row {{
      display: flex;
      align-items: center;
      gap: 0.6rem;
    }}
    .version-label {{ font-size: 0.8rem; color: var(--text2); }}
    .version-select {{
      background: var(--bg3);
      border: 1px solid var(--border);
      color: var(--text);
      border-radius: 4px;
      padding: 0.25rem 0.5rem;
      font-size: 0.8rem;
      cursor: pointer;
      outline: none;
    }}
    .version-select:focus {{ border-color: var(--accent); }}
    .install-cmd {{
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 0.78rem;
      background: var(--code-bg);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 0.5rem 0.75rem;
      color: var(--green);
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 0.5rem;
      word-break: break-all;
    }}
    .copy-btn {{
      background: none;
      border: none;
      color: var(--text2);
      cursor: pointer;
      font-size: 0.85rem;
      padding: 0;
      flex-shrink: 0;
      transition: color 0.15s;
    }}
    .copy-btn:hover {{ color: var(--accent); }}
    .values-toggle {{
      font-size: 0.78rem;
      color: var(--accent);
      background: none;
      border: none;
      cursor: pointer;
      padding: 0;
      text-align: left;
    }}
    .values-toggle:hover {{ text-decoration: underline; }}
    .values-block {{
      display: none;
      background: var(--code-bg);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 0.75rem;
      max-height: 320px;
      overflow-y: auto;
    }}
    .values-block.open {{ display: block; }}
    .values-block pre {{
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 0.72rem;
      color: var(--text2);
      white-space: pre;
      line-height: 1.55;
    }}
    .no-results {{
      text-align: center;
      color: var(--text2);
      padding: 4rem 0;
      font-size: 1rem;
    }}
    footer {{
      text-align: center;
      padding: 2rem;
      color: var(--text2);
      font-size: 0.8rem;
      border-top: 1px solid var(--border);
      margin-top: 3rem;
    }}
    footer a {{ color: var(--accent); text-decoration: none; }}
    .badge {{
      display: inline-flex;
      align-items: center;
      gap: 0.3rem;
      background: var(--bg3);
      border: 1px solid var(--border);
      border-radius: 4px;
      padding: 0.15rem 0.5rem;
      font-size: 0.72rem;
      color: var(--text2);
    }}
    .badge .dot {{ width: 7px; height: 7px; border-radius: 50%; background: var(--green); display: inline-block; }}
    @media (max-width: 640px) {{
      header {{ flex-wrap: wrap; padding: 1rem; }}
      #search-wrap {{ order: 3; flex: 0 0 100%; max-width: 100%; }}
      .helm-add {{ display: none; }}
      .grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1><a href="{repo_url}">{repo}</a></h1>
    <div id="search-wrap">
      <input id="search" type="search" placeholder="Search charts…" autocomplete="off" />
    </div>
    <button class="helm-add" onclick="copyHelmRepo(this)" title="Copy helm repo add command">
      <span class="copy-icon">⎘</span>
      <span>helm repo add {owner} {helm_repo_url}</span>
    </button>
    <span class="stats" id="stats"></span>
  </header>
  <main>
    <div id="results-count"></div>
    <div class="grid" id="grid"></div>
    <div class="no-results" id="no-results" style="display:none">No charts match your search.</div>
  </main>
  <footer>
    Helm repository hosted on <a href="{repo_url}">GitHub</a> &middot;
    <code>helm repo add {owner} {helm_repo_url}</code>
  </footer>
  <script>
  const CHARTS = {charts_json};
  const HELM_REPO_URL = "{helm_repo_url}";

  const index = new FlexSearch.Document({{
    document: {{
      id: "name",
      index: ["name", "description", "keywords"],
    }},
    tokenize: "forward",
  }});

  CHARTS.forEach(c => index.add({{ ...c, keywords: (c.keywords || []).join(" ") }}));

  function escapeHtml(s) {{
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }}

  function buildCard(chart) {{
    const iconHtml = chart.icon
      ? `<img class="card-icon" src="${{escapeHtml(chart.icon)}}" alt="" loading="lazy" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'">`
        + `<div class="card-icon-placeholder" style="display:none">⎈</div>`
      : `<div class="card-icon-placeholder">⎈</div>`;

    const tagsHtml = (chart.keywords || []).slice(0, 5)
      .map(k => `<span class="tag">${{escapeHtml(k)}}</span>`).join("");

    const versionOptions = (chart.versions || [])
      .map(v => `<option value="${{escapeHtml(v)}}">${{escapeHtml(v)}}</option>`).join("");

    const homeLink = chart.home
      ? `<a href="${{escapeHtml(chart.home)}}" target="_blank" rel="noopener" onclick="event.stopPropagation()">${{escapeHtml(chart.name)}}</a>`
      : escapeHtml(chart.name);

    return `
      <div class="card" id="card-${{escapeHtml(chart.name)}}" onclick="toggleCard(this, '${{escapeHtml(chart.name)}}')">
        <div class="card-header">
          ${{iconHtml}}
          <div style="flex:1;min-width:0">
            <div class="card-title">${{homeLink}}</div>
            <div class="card-version">
              <span class="badge"><span class="dot"></span>v${{escapeHtml(chart.latestVersion)}}</span>
              ${{chart.appVersion ? `<span class="badge" style="margin-left:4px">app ${{escapeHtml(String(chart.appVersion))}}</span>` : ""}}
            </div>
          </div>
        </div>
        ${{chart.description ? `<div class="card-desc">${{escapeHtml(chart.description)}}</div>` : ""}}
        ${{tagsHtml ? `<div class="card-tags">${{tagsHtml}}</div>` : ""}}
        <div class="card-detail">
          <div class="version-row">
            <span class="version-label">Version:</span>
            <select class="version-select" id="sel-${{escapeHtml(chart.name)}}" onclick="event.stopPropagation()" onchange="onVersionChange('${{escapeHtml(chart.name)}}', this.value)">
              ${{versionOptions}}
            </select>
          </div>
          <div class="install-cmd" id="cmd-${{escapeHtml(chart.name)}}">
            <span id="cmdtext-${{escapeHtml(chart.name)}}">helm install ${{escapeHtml(chart.name)}} ${{escapeHtml(HELM_REPO_URL)}}/${{escapeHtml(chart.name)}} --version ${{escapeHtml(chart.latestVersion)}}</span>
            <button class="copy-btn" onclick="copyCmd('${{escapeHtml(chart.name)}}', event)" title="Copy">⎘</button>
          </div>
          <button class="values-toggle" onclick="toggleValues('${{escapeHtml(chart.name)}}', event)">Show values.yaml ▾</button>
          <div class="values-block" id="vals-${{escapeHtml(chart.name)}}">
            <pre id="valspre-${{escapeHtml(chart.name)}}"></pre>
          </div>
        </div>
      </div>`;
  }}

  function toggleCard(el, name) {{
    el.classList.toggle("open");
  }}

  function onVersionChange(name, version) {{
    const cmdText = document.getElementById(`cmdtext-${{name}}`);
    if (cmdText) {{
      cmdText.textContent = `helm install ${{name}} ${{HELM_REPO_URL}}/${{name}} --version ${{version}}`;
    }}
    const valsBlock = document.getElementById(`vals-${{name}}`);
    const valsPre = document.getElementById(`valspre-${{name}}`);
    if (valsBlock && valsBlock.classList.contains("open") && valsPre) {{
      const chart = CHARTS.find(c => c.name === name);
      valsPre.textContent = (chart && chart.valuesByVersion && chart.valuesByVersion[version]) || "# values.yaml not available for this version";
    }}
  }}

  function toggleValues(name, event) {{
    event.stopPropagation();
    const btn = event.currentTarget;
    const block = document.getElementById(`vals-${{name}}`);
    const pre = document.getElementById(`valspre-${{name}}`);
    if (!block) return;
    const opening = !block.classList.contains("open");
    block.classList.toggle("open");
    btn.textContent = opening ? "Hide values.yaml ▴" : "Show values.yaml ▾";
    if (opening && pre && !pre.textContent) {{
      const sel = document.getElementById(`sel-${{name}}`);
      const version = sel ? sel.value : "";
      const chart = CHARTS.find(c => c.name === name);
      pre.textContent = (chart && chart.valuesByVersion && chart.valuesByVersion[version]) || "# values.yaml not available for this version";
    }}
  }}

  function copyCmd(name, event) {{
    event.stopPropagation();
    const cmdText = document.getElementById(`cmdtext-${{name}}`);
    if (cmdText) navigator.clipboard.writeText(cmdText.textContent).catch(() => {{}});
  }}

  function copyHelmRepo(btn) {{
    navigator.clipboard.writeText(`helm repo add {owner} ${{HELM_REPO_URL}}`).then(() => {{
      const orig = btn.querySelector("span:last-child").textContent;
      btn.querySelector("span:last-child").textContent = "Copied!";
      setTimeout(() => {{ btn.querySelector("span:last-child").textContent = orig; }}, 1500);
    }}).catch(() => {{}});
  }}

  let currentCards = CHARTS.map(c => c.name);

  function render(names) {{
    const grid = document.getElementById("grid");
    const noResults = document.getElementById("no-results");
    const count = document.getElementById("results-count");
    if (!names || names.length === 0) {{
      grid.innerHTML = "";
      noResults.style.display = "";
      count.textContent = "";
    }} else {{
      noResults.style.display = "none";
      const filtered = CHARTS.filter(c => names.includes(c.name));
      grid.innerHTML = filtered.map(buildCard).join("");
      count.textContent = `Showing ${{filtered.length}} of ${{CHARTS.length}} charts`;
    }}
  }}

  document.getElementById("stats").textContent = `${{CHARTS.length}} charts`;
  render(CHARTS.map(c => c.name));

  let debounceTimer;
  document.getElementById("search").addEventListener("input", e => {{
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {{
      const q = e.target.value.trim();
      if (!q) {{
        render(CHARTS.map(c => c.name));
        return;
      }}
      const results = index.search(q, {{ enrich: true }});
      const names = [...new Set(results.flatMap(r => r.result.map(x => x.id)))];
      render(names.length ? names : []);
    }}, 150);
  }});
  </script>
</body>
</html>"""


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
        charts_data_path = worktree_path / "charts-data.json"
        html_path = worktree_path / "index.html"

        existing_index = load_yaml(index_path)
        existing_charts_data = load_charts_data(charts_data_path)

        merged_index = merge_index(existing_index, packages, owner, repo)
        merged_charts_data = merge_charts_data(existing_charts_data, packages)

        index_path.parent.mkdir(parents=True, exist_ok=True)
        dump_yaml(index_path, merged_index)

        with charts_data_path.open("w", encoding="utf-8") as handle:
            json.dump(merged_charts_data, handle, separators=(",", ":"))

        html_content = generate_index_html(merged_index, merged_charts_data, owner, repo)
        with html_path.open("w", encoding="utf-8") as handle:
            handle.write(html_content)

        changed_files = [
            str(index_relative_path),
            "charts-data.json",
            "index.html",
        ]
        status = git(
            "status", "--porcelain", "--", *changed_files, cwd=worktree_path
        )
        if not status:
            log("No gh-pages changes detected")
            return

        git("add", *changed_files, cwd=worktree_path)
        git("commit", "-m", "Update index.yaml and index.html", cwd=worktree_path)
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
