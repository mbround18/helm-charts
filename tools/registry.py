"""Query container registries for the tags a chart could move to.

Why this exists
---------------
``tools/upgrade.py`` asks Docker Hub for tags anonymously. Anonymous
``hub.docker.com`` quota is per-IP and small, and a sweep of this repo
burns it: ``library/postgres`` alone paginates to ~1400 tags. When the
quota runs out Hub answers 403, which is indistinguishable from "this
image has no newer tag" unless somebody is reading stderr. So an
upgrade run can silently skip exactly the images it failed to reach.

This module authenticates instead, and it loads the credential itself so
no caller ever has to handle it. Nothing here prints, logs or returns the
secret: ``whoami`` reports the source and username only.

Credential resolution, first hit wins:

  1. ``$DOCKERHUB_USERNAME`` + ``$DOCKERHUB_TOKEN``
  2. ``~/.docker/config.json`` -> ``auths["https://index.docker.io/v1/"]``
     (what ``docker login`` writes)
  3. anonymous -- still works, just rate limited, and says so

Usage
-----
  uv run python -m tools.registry whoami
  uv run python -m tools.registry tags mongo --match '^\\d+$'
  uv run python -m tools.registry latest mongo --current 9
  uv run python -m tools.registry scan charts/mongo charts/postgres
  uv run python -m tools.registry scan            # every chart in the repo
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import requests

HUB = "https://hub.docker.com"
DOCKER_AUTH_KEY = "https://index.docker.io/v1/"
TIMEOUT = 30
REPO_ROOT = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------
# credentials
# --------------------------------------------------------------------------
@dataclass
class Credential:
    """A Docker Hub credential. ``secret`` is never printed or returned."""

    username: str | None
    secret: str | None
    source: str

    @property
    def anonymous(self) -> bool:
        return not (self.username and self.secret)

    def describe(self) -> str:
        if self.anonymous:
            return f"anonymous (source: {self.source})"
        return f"{self.username} (source: {self.source})"


def _docker_config_credential(key: str) -> Credential | None:
    """Read one `auths` entry out of the file `docker login` writes."""
    cfg = Path(os.environ.get("DOCKER_CONFIG", Path.home() / ".docker")) / "config.json"
    if not cfg.is_file():
        return None
    try:
        entry = ((json.loads(cfg.read_text()) or {}).get("auths") or {}).get(key) or {}
        if entry.get("auth"):
            decoded = base64.b64decode(entry["auth"]).decode("utf-8", "replace")
            if ":" in decoded:
                u, _, pw = decoded.partition(":")
                if u and pw:
                    return Credential(u, pw, str(cfg))
        if entry.get("username") and entry.get("password"):
            return Credential(entry["username"], entry["password"], str(cfg))
    except (ValueError, OSError) as exc:
        print(f"warning: could not read {cfg}: {exc}", file=sys.stderr)
    return None


def load_host_credential(host: str) -> Credential | None:
    """A credential for a non-Hub registry, if one has been logged into.

    ghcr.io rate limits even its anonymous *token* endpoint -- an
    unauthenticated tag listing there can 403 outright -- and a private repo
    is simply invisible without this. Anonymous stays the fallback, since
    most of what this repo pulls is public.
    """
    stem = re.sub(r"[^A-Z0-9]", "_", host.upper())
    env_user, env_token = (
        os.environ.get(f"{stem}_USERNAME"),
        os.environ.get(f"{stem}_TOKEN"),
    )
    if env_user and env_token:
        return Credential(env_user, env_token, f"env {stem}_USERNAME/{stem}_TOKEN")
    return _docker_config_credential(host)


def load_credential(allow_anonymous: bool = True) -> Credential:
    """The Docker Hub credential. Env wins so CI can override a stale login."""
    user, token = (
        os.environ.get("DOCKERHUB_USERNAME"),
        os.environ.get("DOCKERHUB_TOKEN"),
    )
    if user and token:
        return Credential(user, token, "env DOCKERHUB_USERNAME/DOCKERHUB_TOKEN")

    found = _docker_config_credential(DOCKER_AUTH_KEY)
    if found:
        return found

    if not allow_anonymous:
        raise SystemExit(
            "no Docker Hub credential found. Set DOCKERHUB_USERNAME and "
            "DOCKERHUB_TOKEN, or run `docker login`, or drop --require-auth."
        )
    return Credential(None, None, "no credential found")


# --------------------------------------------------------------------------
# registries
# --------------------------------------------------------------------------
class Registry:
    """Tag listings. One session, one Hub token, reused across lookups."""

    def __init__(self, credential: Credential | None = None):
        self.credential = credential or load_credential()
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "helm-charts-tools/registry"
        self._hub_jwt: str | None = None
        self._hub_login_failed = False

    # -- Docker Hub ------------------------------------------------------
    def _hub_token(self) -> str | None:
        if self.credential.anonymous or self._hub_login_failed:
            return None
        if self._hub_jwt:
            return self._hub_jwt
        try:
            r = self.session.post(
                f"{HUB}/v2/users/login",
                json={
                    "username": self.credential.username,
                    "password": self.credential.secret,
                },
                timeout=TIMEOUT,
            )
            r.raise_for_status()
            self._hub_jwt = r.json().get("token")
        except requests.RequestException as exc:
            # Never echo the response body -- it can contain the request.
            print(
                f"warning: Docker Hub login failed ({exc.__class__.__name__}); "
                "continuing anonymously and rate limited",
                file=sys.stderr,
            )
            self._hub_login_failed = True
            return None
        return self._hub_jwt

    def _hub_tags(self, repo: str) -> list[str]:
        if "/" not in repo:
            repo = f"library/{repo}"
        headers = {}
        tok = self._hub_token()
        if tok:
            headers["Authorization"] = f"JWT {tok}"
        tags: list[str] = []
        url = f"{HUB}/v2/repositories/{repo}/tags/?page_size=100"
        while url:
            r = self.session.get(url, headers=headers, timeout=TIMEOUT)
            if r.status_code == 403:
                raise RegistryError(
                    f"Docker Hub returned 403 for {repo} after {len(tags)} tags. "
                    + (
                        "Authenticated quota exhausted."
                        if tok
                        else "This is the anonymous per-IP limit -- authenticate."
                    )
                )
            r.raise_for_status()
            body = r.json()
            tags += [t["name"] for t in body.get("results") or []]
            url = body.get("next")
        return tags

    # -- token-auth registries (ghcr, codeberg, forgejo, ...) ------------
    def _bearer_tags(self, host: str, repo: str) -> list[str]:
        url = f"https://{host}/v2/{repo}/tags/list?n=1000"
        r = self.session.get(url, timeout=TIMEOUT)
        if r.status_code in (401, 403):
            realm = re.search(r'realm="([^"]+)"', r.headers.get("Www-Authenticate", ""))
            svc = re.search(r'service="([^"]+)"', r.headers.get("Www-Authenticate", ""))
            if not realm:
                raise RegistryError(f"{host} wants auth but advertised no realm")
            turl = f"{realm.group(1)}?scope=repository:{repo}:pull"
            if svc:
                turl += f"&service={svc.group(1)}"
            cred = load_host_credential(host)
            auth = (cred.username, cred.secret) if cred and not cred.anonymous else None
            tr = self.session.get(turl, auth=auth, timeout=TIMEOUT)
            tr.raise_for_status()
            body = tr.json()
            tok = body.get("token") or body.get("access_token")
            r = self.session.get(
                url, headers={"Authorization": f"Bearer {tok}"}, timeout=TIMEOUT
            )
        r.raise_for_status()
        return r.json().get("tags") or []

    # -- quay -----------------------------------------------------------
    def _quay_tags(self, repo: str) -> list[str]:
        tags, page = [], 1
        while page <= 20:
            r = self.session.get(
                f"https://quay.io/api/v1/repository/{repo}/tag/"
                f"?limit=100&page={page}&onlyActiveTags=true",
                timeout=TIMEOUT,
            )
            r.raise_for_status()
            body = r.json()
            tags += [t["name"] for t in body.get("tags") or []]
            if not body.get("has_additional"):
                break
            page += 1
        return tags

    def tags(self, image: str) -> list[str]:
        if image.startswith("ghcr.io/"):
            return self._bearer_tags("ghcr.io", image[len("ghcr.io/") :])
        if image.startswith("quay.io/"):
            return self._quay_tags(image[len("quay.io/") :])
        head = image.split("/")[0]
        if "." in head or ":" in head:  # some other registry host
            host, _, repo = image.partition("/")
            return self._bearer_tags(host, repo)
        return self._hub_tags(image)


class RegistryError(RuntimeError):
    pass


# --------------------------------------------------------------------------
# tag shapes
#
# "Newest" only means something relative to how a tag is already written.
# `16` and `v1.2.3` and `8-alpine` are three different numbering schemes in
# one repo, and comparing across them is how you end up proposing `latest`
# as an upgrade from `2.37.1`. A shape is (prefix, component count, suffix);
# a candidate has to match it exactly to be comparable.
# --------------------------------------------------------------------------
TAG_RE = re.compile(r"(v?)(\d+(?:\.\d+)*)([-.a-zA-Z0-9_]*)")


def shape_of(tag: str) -> tuple[str, int, str] | None:
    m = TAG_RE.fullmatch(str(tag))
    if not m:
        return None
    return m.group(1), len(m.group(2).split(".")), m.group(3)


def version_key(tag: str, shape: tuple[str, int, str]) -> tuple[int, ...] | None:
    m = TAG_RE.fullmatch(str(tag))
    if not m:
        return None
    if (m.group(1), len(m.group(2).split(".")), m.group(3)) != shape:
        return None
    return tuple(int(p) for p in m.group(2).split("."))


def newest_same_shape(tags: list[str], current: str) -> tuple[str | None, str]:
    shape = shape_of(current)
    if shape is None:
        return None, f"{current!r} is not a numeric tag -- nothing to compare"
    ranked = [(version_key(t, shape), t) for t in tags]
    ranked = [(k, t) for k, t in ranked if k is not None]
    if not ranked:
        return None, f"no tag shaped like {current!r} among {len(tags)}"
    best = max(ranked)[1]
    return best, f"{len(tags)} tags, {len(ranked)} comparable"


# --------------------------------------------------------------------------
# chart scanning
# --------------------------------------------------------------------------
def find_images(node, path=()) -> list[tuple[str, str, str]]:
    """Yield (dotted.path, repository, tag) for every image in a values tree."""
    found = []
    if isinstance(node, dict):
        repo, tag = node.get("repository"), node.get("tag")
        if isinstance(repo, str) and tag is not None:
            found.append((".".join(path) or ".", repo, str(tag)))
        for k, v in node.items():
            found += find_images(v, path + (str(k),))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            found += find_images(v, path + (f"[{i}]",))
    return found


def chart_values_files(chart_dirs: list[Path]) -> list[Path]:
    if not chart_dirs:
        chart_dirs = sorted(
            p.parent for p in (REPO_ROOT / "charts").glob("*/Chart.yaml")
        )
    out = []
    for d in chart_dirs:
        f = d / "values.yaml"
        if f.is_file():
            out.append(f)
        else:
            print(f"warning: no values.yaml in {d}", file=sys.stderr)
    return out


# --------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------
def cmd_whoami(args) -> int:
    cred = load_credential(allow_anonymous=not args.require_auth)
    print(f"docker hub: {cred.describe()}")
    if cred.anonymous:
        print("  -> per-IP rate limits apply; large scans will hit 403")
        return 0
    reg = Registry(cred)
    print("  -> login:", "ok" if reg._hub_token() else "FAILED (see warning above)")
    for host in ("ghcr.io", "quay.io"):
        hc = load_host_credential(host)
        print(f"{host}: {hc.describe() if hc else 'anonymous (no credential found)'}")
    return 0


def cmd_tags(args) -> int:
    reg = Registry(load_credential(allow_anonymous=not args.require_auth))
    try:
        tags = reg.tags(args.image)
    except (RegistryError, requests.RequestException) as exc:
        print(f"error: {args.image}: {exc}", file=sys.stderr)
        return 1
    if args.shape_of:
        shape = shape_of(args.shape_of)
        tags = [t for t in tags if shape and version_key(t, shape)]
    if args.match:
        pat = re.compile(args.match)
        tags = [t for t in tags if pat.search(t)]
    ranked = sorted(
        tags, key=lambda t: (version_key(t, shape_of(t)) or (), t), reverse=True
    )
    if args.limit:
        ranked = ranked[: args.limit]
    if args.json:
        print(json.dumps({"image": args.image, "tags": ranked}, indent=2))
    else:
        for t in ranked:
            print(t)
    return 0


def cmd_latest(args) -> int:
    reg = Registry(load_credential(allow_anonymous=not args.require_auth))
    try:
        tags = reg.tags(args.image)
    except (RegistryError, requests.RequestException) as exc:
        print(f"error: {args.image}: {exc}", file=sys.stderr)
        return 1
    newest, note = newest_same_shape(tags, args.current)
    if args.json:
        print(
            json.dumps(
                {
                    "image": args.image,
                    "current": args.current,
                    "newest": newest,
                    "behind": bool(newest and newest != args.current),
                    "note": note,
                },
                indent=2,
            )
        )
    else:
        state = "up to date" if newest == args.current else f"-> {newest}"
        print(f"{args.image}:{args.current} {state}  ({note})")
    return 0


def cmd_scan(args) -> int:
    import yaml  # pyyaml, already a dependency

    reg = Registry(load_credential(allow_anonymous=not args.require_auth))
    rows, failures, behind = [], 0, 0
    for vf in chart_values_files([Path(p) for p in args.chart_paths]):
        try:
            data = yaml.safe_load(vf.read_text()) or {}
        except yaml.YAMLError as exc:
            print(f"warning: {vf}: {exc}", file=sys.stderr)
            continue
        for path, repo, tag in find_images(data, ()):
            # A sweep of this repo paginates tens of thousands of tags and the
            # table only prints at the end, so say what is in flight.
            print(f"  querying {repo}:{tag} ...", file=sys.stderr, flush=True)
            try:
                newest, note = newest_same_shape(reg.tags(repo), tag)
            except (RegistryError, requests.RequestException) as exc:
                newest, note = None, f"{exc.__class__.__name__}: {exc}"
                failures += 1
            is_behind = bool(newest and newest != tag)
            behind += is_behind
            rows.append(
                {
                    "chart": vf.parent.name,
                    "values_path": path,
                    "image": repo,
                    "current": tag,
                    "newest": newest,
                    "behind": is_behind,
                    "note": note,
                }
            )

    if args.json:
        print(json.dumps(rows, indent=2))
    else:
        width = max([len(r["image"]) for r in rows] + [5])
        for r in rows:
            mark = "BEHIND" if r["behind"] else ("ERROR" if not r["newest"] else "ok")
            print(
                f"{mark:<7} {r['chart']:<24} {r['image']:<{width}} "
                f"{r['current']:<14} {r['newest'] or '-':<14} {r['note']}"
            )
        print(
            f"\n{len(rows)} images: {behind} behind, {failures} unresolved, "
            f"{len(rows) - behind - failures} current"
        )

    # Unresolved is a failure, not a pass. That conflation is the bug this
    # module exists to fix: a 403 must never read as "nothing newer".
    if failures:
        return 2
    return 1 if (behind and args.exit_code) else 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="tools.registry",
        description="Find container tags, authenticating to Docker Hub if it can.",
    )
    p.add_argument(
        "--require-auth",
        action="store_true",
        help="fail rather than fall back to anonymous (use in CI)",
    )
    p.add_argument("--json", action="store_true", help="machine-readable output")
    sub = p.add_subparsers(dest="command", required=True)

    w = sub.add_parser("whoami", help="show which credential would be used")
    w.set_defaults(func=cmd_whoami)

    t = sub.add_parser("tags", help="list tags for an image, newest first")
    t.add_argument("image", help="e.g. mongo, ghcr.io/advplyr/audiobookshelf")
    t.add_argument("--match", help="keep only tags matching this regex")
    t.add_argument("--shape-of", metavar="TAG", help="keep only tags shaped like TAG")
    t.add_argument("--limit", type=int, default=20, help="0 for all (default 20)")
    t.set_defaults(func=cmd_tags)

    nw = sub.add_parser("latest", help="newest tag shaped like the one you have")
    nw.add_argument("image")
    nw.add_argument("--current", required=True, help="the tag in your values.yaml")
    nw.set_defaults(func=cmd_latest)

    s = sub.add_parser("scan", help="compare every chart image against its registry")
    s.add_argument(
        "chart_paths", nargs="*", help="chart dirs (default: every chart in the repo)"
    )
    s.add_argument(
        "--exit-code",
        action="store_true",
        help="exit 1 if anything is behind (exit 2 on unresolved regardless)",
    )
    s.set_defaults(func=cmd_scan)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
