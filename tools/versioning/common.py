from __future__ import annotations

import re
from pathlib import Path
from typing import Optional


SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def log(level: str, message: str) -> None:
    print(f"{level}: {message}")


def append_summary(summary_file: Optional[Path], message: str) -> None:
    if summary_file is None:
        return

    with summary_file.open("a", encoding="utf-8") as handle:
        handle.write(f"{message}\n")


def parse_semver(version: str) -> Optional[tuple[int, int, int]]:
    match = SEMVER_RE.match(version)
    if not match:
        return None

    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def bump_version(version: str, bump: str) -> str:
    parsed = parse_semver(version)
    if parsed is None:
        raise ValueError(f"Not a semver: {version}")

    major, minor, patch = parsed
    if bump == "major":
        return f"{major + 1}.0.0"
    if bump == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"
