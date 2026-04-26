from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class VersionBumpConfig:
    repo_root: Path
    charts_root: Path
    dry_run: bool
    push_changes: bool
    fetch_tags: bool
    owner_repo: str
    github_token: Optional[str]
    summary_file: Optional[Path]


@dataclass(frozen=True)
class ChartUpdate:
    chart_name: str
    chart_dir: Path
    chart_yaml: Path
    current_version: Optional[str]
    new_version: str
    bump: str
