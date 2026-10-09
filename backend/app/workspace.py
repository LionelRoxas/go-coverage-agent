# AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
"""A throwaway copy of the user's repo. The only place generated files are ever written."""
from __future__ import annotations

import os
import posixpath
import re
import shutil
from pathlib import Path, PurePosixPath, PureWindowsPath

SEED_FILE = "zz_coverage_seed_test.go"
_RESTORABLE = {"go.mod", "go.sum"}
_PKG_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


class WorkspaceError(ValueError):
    pass


def _looks_absolute(repo_path: str) -> bool:
    # Check both path flavours: tests run on a Windows host, the app runs on Linux.
    return (repo_path.startswith(("/", "\\", "~")) or PurePosixPath(repo_path).is_absolute()
            or PureWindowsPath(repo_path).is_absolute())


def _looks_host_path(repo_path: str) -> bool:
    # Windows drive, UNC share or home-relative path: never valid inside the container,
    # and on Linux these would otherwise resolve as harmless relative names under root.
    return (bool(PureWindowsPath(repo_path).drive) or repo_path.startswith("\\\\")
            or repo_path.startswith("~"))


def _host_path_error(repo_path: str) -> WorkspaceError:
    return WorkspaceError(
        f"{repo_path!r} looks like a path on your machine, which the container cannot see. "
        "Put the repo under ./repos (or set HOST_REPOS_DIR in .env) and pick it from the list."
    )


def _skip_git_and_links(directory: str, names: list[str]) -> set[str]:
    # Symlinks are skipped: copytree would otherwise follow them out of the repo (or loop).
    return {n for n in names if n == ".git" or os.path.islink(os.path.join(directory, n))}


def resolve_repo(repos_dir: Path, repo_path: str) -> Path:
    root = repos_dir.resolve()
    candidate = (root / repo_path).resolve()
    inside = candidate.is_relative_to(root)
    # On Linux "C:\\x" or "~/x" is a harmless relative name under root, so only accept
    # such input when it really exists there; otherwise explain the host path.
    if _looks_host_path(repo_path) and not (inside and candidate.exists()):
        raise _host_path_error(repo_path)
    if not inside:
        if _looks_absolute(repo_path):
            raise _host_path_error(repo_path)
        raise WorkspaceError("repo_path must point inside the repos folder")
    if not (candidate / "go.mod").is_file():
        raise WorkspaceError(f"no go.mod found in {repo_path!r}; choose the module root")
    return candidate


def test_path_for(source_file: str) -> str:
    stem, _ = posixpath.splitext(source_file)
    return f"{stem}_test.go"


test_path_for.__test__ = False  # imported by test modules; not a pytest test


class Workspace:
    def __init__(self, root: Path, scratch: Path):
        self.root = root.resolve()
        self.scratch = scratch.resolve()

    @classmethod
    def create(cls, work_dir: Path, job_id: str, source: Path) -> Workspace:
        base = work_dir / job_id
        root = base / "repo"
        try:
            shutil.copytree(source, root, ignore=_skip_git_and_links)
            (base / "scratch").mkdir(parents=True, exist_ok=True)
        except Exception:
            shutil.rmtree(base, ignore_errors=True)
            raise
        return cls(root, base / "scratch")

    def path(self, rel: str) -> Path:
        p = (self.root / rel).resolve()
        if not p.is_relative_to(self.root):
            raise WorkspaceError(f"path escapes workspace: {rel!r}")
        return p

    def _rel(self, p: Path) -> str:
        return p.relative_to(self.root).as_posix()

    def test_files(self, include_seeds: bool = False) -> list[str]:
        files = sorted(self._rel(p) for p in self.root.rglob("*_test.go"))
        return files if include_seeds else [f for f in files if posixpath.basename(f) != SEED_FILE]

    def delete_existing_tests(self) -> list[str]:
        removed = self.test_files(include_seeds=True)
        for rel in removed:
            self.path(rel).unlink()
        return removed

    def seed_packages(self, packages: list[tuple[str, str]]) -> list[str]:
        seeded = []
        for rel_dir, name in packages:
            if not _PKG_NAME.fullmatch(name):
                raise WorkspaceError(f"invalid Go package name: {name!r}")
            directory = self.path(rel_dir)
            if any(directory.glob("*_test.go")):
                continue
            rel = posixpath.normpath(posixpath.join(rel_dir, SEED_FILE))
            self.path(rel).write_text(f"package {name}\n", encoding="utf-8")
            seeded.append(rel)
        return seeded

    def read(self, rel: str) -> str | None:
        p = self.path(rel)
        return p.read_text(encoding="utf-8") if p.exists() else None

    def write_test(self, rel: str, content: str) -> None:
        if not rel.endswith("_test.go"):
            raise WorkspaceError(f"only *_test.go files may be written: {rel!r}")
        self._write(self.path(rel), content)

    def snapshot(self, rels: list[str]) -> dict[str, str | None]:
        return {rel: self.read(rel) for rel in rels}

    def restore(self, snap: dict[str, str | None]) -> None:
        for rel, content in snap.items():
            if not (rel.endswith("_test.go") or rel in _RESTORABLE):
                raise WorkspaceError(f"refusing to restore non-test file {rel!r}")
            p = self.path(rel)
            if content is None:
                p.unlink(missing_ok=True)
            else:
                self._write(p, content)

    @staticmethod
    def _write(p: Path, content: str) -> None:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(p.name + ".tmp")
        tmp.write_text(content, encoding="utf-8")
        os.replace(tmp, p)
