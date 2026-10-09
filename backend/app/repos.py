# AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
from __future__ import annotations

import os
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
    candidates = [d for d in repos_dir.iterdir() if d.is_dir() and not d.name.startswith(".")]
    candidates += [g for d in list(candidates) if not (d / "go.mod").exists()
                   for g in d.iterdir() if g.is_dir() and not g.name.startswith(".")]
    found = []
    for d in candidates:
        if not (d / "go.mod").is_file():
            continue
        try:
            module, _ = read_module_info(d)
        except ValueError:
            continue
        go, tests = _count(d)
        found.append(RepoInfo(path=d.relative_to(repos_dir).as_posix(), module=module, go_files=go, test_files=tests))
    return sorted(found, key=lambda r: r.path)


async def clone_sample(settings: Settings) -> RepoInfo:
    dest = settings.repos_dir / "stats"
    if not (dest / "go.mod").exists():
        env = {"PATH": os.environ.get("PATH", ""), "HOME": os.environ.get("HOME", "/tmp"), "GIT_TERMINAL_PROMPT": "0"}
        r = await run(["git", "clone", "--depth", "1", settings.sample_repo_url, str(dest)],
                      cwd=settings.repos_dir, timeout=120, env=env)
        if r.exit_code != 0:
            raise RuntimeError(f"git clone failed: {r.combined[:500]}")
    return next(info for info in list_repos(settings.repos_dir) if info.path == "stats")
