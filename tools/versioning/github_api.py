from __future__ import annotations

import json
import urllib.request
from typing import Optional

from tools.versioning.common import log


class GitHubClient:
    def __init__(self, owner_repo: str, token: Optional[str]) -> None:
        self.owner_repo = owner_repo
        self.token = token
        self._label_cache: dict[int, list[str]] = {}

    def get_pr_labels(self, pr_number: int) -> list[str]:
        if not self.owner_repo:
            return []

        if pr_number in self._label_cache:
            return self._label_cache[pr_number]

        url = f"https://api.github.com/repos/{self.owner_repo}/issues/{pr_number}"
        request = urllib.request.Request(url)
        if self.token:
            request.add_header("Authorization", f"Bearer {self.token}")
            request.add_header("Accept", "application/vnd.github+json")
            request.add_header("X-GitHub-Api-Version", "2022-11-28")

        try:
            with urllib.request.urlopen(request) as response:
                payload = json.loads(response.read().decode())
        except Exception as exc:  # noqa: BLE001
            log("WARNING", f"Failed to fetch PR #{pr_number} labels: {exc}")
            self._label_cache[pr_number] = []
            return []

        labels = []
        for item in payload.get("labels", []):
            name = item.get("name")
            if isinstance(name, str):
                labels.append(name)

        self._label_cache[pr_number] = labels
        return labels
