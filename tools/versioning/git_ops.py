from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Iterable, Optional


class GitClient:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root

    def _normalize_path(self, path: Path) -> str:
        try:
            return str(path.relative_to(self.repo_root))
        except ValueError:
            return str(path)

    def run(self, args: list[str], cwd: Optional[Path] = None) -> str:
        output = subprocess.check_output(args, cwd=str(cwd or self.repo_root))
        return output.decode().strip()

    def fetch_tags(self) -> None:
        self.run(["git", "fetch", "--tags"])

    def list_tags(self, pattern: str) -> list[str]:
        output = self.run(["git", "tag", "-l", pattern])
        return [line.strip() for line in output.splitlines() if line.strip()]

    def log_text(self, revision_range: str, path: Path, fmt: str) -> str:
        return self.run(
            [
                "git",
                "log",
                f"--format={fmt}",
                revision_range,
                "--",
                self._normalize_path(path),
            ]
        )

    def has_changes(self, revision_range: str, path: Path) -> bool:
        result = subprocess.run(
            [
                "git",
                "diff",
                "--quiet",
                revision_range,
                "--",
                self._normalize_path(path),
            ],
            check=False,
            cwd=str(self.repo_root),
        )
        return result.returncode == 1

    def stage_paths(self, paths: Iterable[Path]) -> None:
        normalized_paths = sorted({self._normalize_path(path) for path in paths})
        if not normalized_paths:
            return

        subprocess.check_call(
            ["git", "add", *normalized_paths], cwd=str(self.repo_root)
        )

    def commit(self, message: str) -> None:
        subprocess.check_call(["git", "commit", "-m", message], cwd=str(self.repo_root))

    def current_branch(self) -> str:
        return self.run(["git", "symbolic-ref", "--short", "HEAD"])

    def push(self, branch: str) -> None:
        subprocess.check_call(
            ["git", "push", "origin", f"HEAD:{branch}"], cwd=str(self.repo_root)
        )

    @classmethod
    def discover_repo_root(cls) -> Path:
        output = subprocess.check_output(["git", "rev-parse", "--show-toplevel"])
        return Path(output.decode().strip())
