from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


REPO_URL = "https://github.com/operaciones-mcparking/scraping-google-restaurantes"
ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class AppVersion:
    branch: str
    commit: str
    repo_url: str = REPO_URL

    @property
    def known(self) -> bool:
        return bool(self.branch and self.commit)

    @property
    def label(self) -> str:
        if not self.known:
            return "Version desconocida"
        return f"{self.branch} · commit {self.commit}"


def _env_first(*names: str) -> str:
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""


def _git_value(*args: str) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except Exception:
        return ""
    return result.stdout.strip()


@lru_cache(maxsize=1)
def current_version() -> AppVersion:
    branch = _env_first("GITHUB_REF_NAME", "BRANCH_NAME", "STREAMLIT_GIT_BRANCH")
    commit = _env_first("GITHUB_SHA", "COMMIT_SHA", "STREAMLIT_GIT_COMMIT")

    if not branch:
        branch = _git_value("rev-parse", "--abbrev-ref", "HEAD")
    if not commit:
        commit = _git_value("rev-parse", "--short", "HEAD")
    else:
        commit = commit[:7]

    if branch == "HEAD":
        branch = "main"
    if commit:
        commit = commit[:7]

    return AppVersion(branch=branch, commit=commit)
