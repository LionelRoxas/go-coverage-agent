# AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
from __future__ import annotations

import os
import shutil
from pathlib import Path

from pydantic import BaseModel

from app.config import Settings
from app.gotools import read_module_info, run

_SKIP = {"vendor", "node_modules", "testdata"}


class RepoInfo(BaseModel):
    path: str
    module: str
    go_files: int
    test_files: int


def _count(root: Path) -> tuple[int, int]:
    go = tests = 0
    for p in root.rglob("*.go"):
        if any(part.startswith(".") or part in _SKIP for part in p.relative_to(root).parts[:-1]):
            continue
        if p.name.endswith("_test.go"):
            tests += 1
        else:
            go += 1
    return go, tests


def list_repos(repos_dir: Path) -> list[RepoInfo]:
    if not repos_dir.is_dir():
        return []
    def subdirs(parent: Path) -> list[Path]:
        try:
            return [d for d in parent.iterdir() if d.is_dir() and not d.name.startswith(".")]
        except OSError:
            return []

    candidates = subdirs(repos_dir)
    candidates += [g for d in list(candidates) if not (d / "go.mod").exists() for g in subdirs(d)]
    found = []
    for d in candidates:
        try:
            if not (d / "go.mod").is_file():
                continue
            module, _ = read_module_info(d)
            go, tests = _count(d)
        except (ValueError, OSError):
            continue
        found.append(RepoInfo(path=d.relative_to(repos_dir).as_posix(), module=module, go_files=go, test_files=tests))
    return sorted(found, key=lambda r: r.path)


async def clone_sample(settings: Settings) -> RepoInfo:
    dest = settings.repos_dir / "stats"
    if not (dest / "go.mod").exists():
        env = {"PATH": os.environ.get("PATH", ""), "HOME": os.environ.get("HOME", "/tmp"), "GIT_TERMINAL_PROMPT": "0"}
        try:
            r = await run(["git", "clone", "--depth", "1", settings.sample_repo_url, str(dest)],
                          cwd=settings.repos_dir, timeout=120, env=env)
        except OSError as e:
            raise RuntimeError(f"git clone could not start: {e}") from e
        if r.exit_code != 0:
            shutil.rmtree(dest, ignore_errors=True)
            raise RuntimeError(f"git clone failed: {r.combined[:500]}")
    info = next((i for i in list_repos(settings.repos_dir) if i.path == "stats"), None)
    if info is None:
        raise RuntimeError("cloned repository has no go.mod")
    return info
