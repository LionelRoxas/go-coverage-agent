# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
from __future__ import annotations

import asyncio
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel

from app.config import Settings
from app.gotools import read_module_info, run
from app.workspace import HOST_PREFIX

# Held while a folder under repos_dir is created or replaced (sample clone, upload swap) and while a job copies one.
repo_lock = asyncio.Lock()
_SKIP = {"vendor", "node_modules", "testdata"}
_REQUIRE = re.compile(r"^\s*require\b", re.MULTILINE)


@dataclass(frozen=True)
class Sample:
    id: str
    name: str
    description: str
    license: str
    ref: str | None  # release tag; None = the repository's default branch

    @property
    def url(self) -> str:
        return f"https://github.com/{self.name}"


# Curated allowlist: dependency-free Go libraries, pinned to their latest release tags.
SAMPLES: dict[str, Sample] = {s.id: s for s in (
    Sample("stats", "montanaflynn/stats", "Statistics functions", "MIT", None),
    Sample("semver", "Masterminds/semver", "Semantic version parsing and constraints", "MIT", "v3.5.0"),
    Sample("xstrings", "huandu/xstrings", "String utilities", "MIT", "v1.6.2"),
    Sample("humanize", "dustin/go-humanize", "Human-friendly numbers, sizes and times", "MIT", "v1.1.0"),
    Sample("btree", "google/btree", "In-memory B-tree (generics)", "Apache-2.0", "v1.1.3"),
    Sample("decimal", "shopspring/decimal", "Arbitrary-precision decimals", "MIT", "v1.5.0"),
)}


class RepoInfo(BaseModel):
    path: str
    module: str
    go_files: int
    test_files: int
    read_only: bool = False  # under HOST_REPOS_DIR (mounted read-only; path is `host/<rel>`)


def count_go_files(root: Path) -> tuple[int, int]:
    go = tests = 0
    for p in root.rglob("*.go"):
        if any(part.startswith(".") or part in _SKIP for part in p.relative_to(root).parts[:-1]):
            continue
        if p.name.endswith("_test.go"):
            tests += 1
        else:
            go += 1
    return go, tests


def _list_modules(root: Path, skip: frozenset[str] = frozenset()) -> list[tuple[Path, str, int, int]]:
    """(dir, module, go files, test files) of each Go module up to two levels below root."""
    if not root.is_dir():
        return []
    def subdirs(parent: Path) -> list[Path]:
        try:
            return [d for d in parent.iterdir() if d.is_dir() and not d.name.startswith(".")]
        except OSError:
            return []

    candidates = [d for d in subdirs(root) if d.name not in skip]
    candidates += [g for d in list(candidates) if not (d / "go.mod").exists() for g in subdirs(d)]
    found = []
    for d in candidates:
        try:
            if not (d / "go.mod").is_file():
                continue
            module, _ = read_module_info(d)
            go, tests = count_go_files(d)
        except (ValueError, OSError):
            continue
        found.append((d, module, go, tests))
    return found


def list_repos(repos_dir: Path, host_repos_dir: Path | None = None) -> list[RepoInfo]:
    """Modules in repos_dir (samples, uploads), plus those in host_repos_dir as read-only `host/<rel>`. A folder
    named `host` in repos_dir is not listed: that prefix always means HOST_REPOS_DIR."""
    found = [RepoInfo(path=d.relative_to(repos_dir).as_posix(), module=m, go_files=g, test_files=t)
             for d, m, g, t in _list_modules(repos_dir, frozenset({HOST_PREFIX}))]
    if host_repos_dir is not None:
        found += [RepoInfo(path=f"{HOST_PREFIX}/{d.relative_to(host_repos_dir).as_posix()}", module=m, go_files=g,
                           test_files=t, read_only=True)
                  for d, m, g, t in _list_modules(host_repos_dir)]
    return sorted(found, key=lambda r: r.path)


async def clone_sample(settings: Settings, sample_id: str = "stats") -> RepoInfo:
    sample = SAMPLES[sample_id]
    async with repo_lock:
        return await _clone_sample_locked(settings, sample)


def _is_module(d: Path) -> bool:
    return (d / "go.mod").is_file()


def list_samples(repos_dir: Path) -> list[dict]:
    return [
        {"id": s.id, "name": s.name, "description": s.description, "license": s.license, "ref": s.ref,
         "path": s.id, "downloaded": _is_module(repos_dir / s.id)}
        for s in SAMPLES.values()
    ]


async def _clone_sample_locked(settings: Settings, sample: Sample) -> RepoInfo:
    dest = settings.repos_dir / sample.id
    if not _is_module(dest):
        if dest.exists():
            raise RuntimeError(f"repos/{sample.id} exists but is not a Go module; remove or rename it")
        env = {"PATH": os.environ.get("PATH", ""), "HOME": os.environ.get("HOME", "/tmp"), "GIT_TERMINAL_PROMPT": "0"}
        argv = ["git", "clone", "--depth", "1"]
        if sample.ref:
            argv += ["--branch", sample.ref]
        argv += ["--no-recurse-submodules", "--", sample.url, str(dest)]
        try:
            r = await run(argv, cwd=settings.repos_dir, timeout=120, env=env)
        except OSError as e:
            raise RuntimeError(f"git clone could not start: {e}") from e
        if r.exit_code != 0:
            shutil.rmtree(dest, ignore_errors=True)
            raise RuntimeError(f"git clone failed: {r.combined[:500]}")
        try:
            gomod = (dest / "go.mod").read_text(encoding="utf-8", errors="replace")
        except OSError:
            shutil.rmtree(dest, ignore_errors=True)
            raise RuntimeError("cloned repository has no go.mod") from None
        if _REQUIRE.search(gomod):
            shutil.rmtree(dest, ignore_errors=True)
            raise RuntimeError(f"{sample.name} now has dependencies in go.mod; samples must have none, so it was removed")
    info = next((i for i in list_repos(settings.repos_dir) if i.path == sample.id), None)
    if info is None:
        raise RuntimeError("cloned repository has no go.mod")
    return info
