# AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
import os
from pathlib import Path

import pytest

from app.workspace import SEED_FILE, Workspace, WorkspaceError, resolve_repo, test_path_for


def make_repo(root: Path) -> Path:
    repo = root / "repos" / "demo"
    (repo / ".git").mkdir(parents=True)
    (repo / ".git" / "HEAD").write_text("ref")
    (repo / "go.mod").write_text("module example.com/demo\n\ngo 1.17\n")
    (repo / "a.go").write_text("package demo\n")
    (repo / "a_test.go").write_text("package demo\n")
    (repo / "sub").mkdir()
    (repo / "sub" / "b.go").write_text("package sub\n")
    return repo


def test_resolve_repo_accepts_relative_and_container_absolute(tmp_path):
    repo = make_repo(tmp_path)
    repos = tmp_path / "repos"
    assert resolve_repo(repos, "demo") == repo.resolve()
    assert resolve_repo(repos, str(repo)) == repo.resolve()


def test_resolve_repo_rejects_traversal(tmp_path):
    make_repo(tmp_path)
    with pytest.raises(WorkspaceError, match="inside"):
        resolve_repo(tmp_path / "repos", "../../etc")


def test_resolve_repo_explains_host_paths(tmp_path):
    make_repo(tmp_path)
    elsewhere = tmp_path / "Users" / "me" / "code" / "stats"
    elsewhere.mkdir(parents=True)
    with pytest.raises(WorkspaceError, match=r"\./repos"):
        resolve_repo(tmp_path / "repos", str(elsewhere))


@pytest.mark.parametrize("host_path", [r"C:\Users\me\code\stats", "~/code/stats"])
def test_resolve_repo_explains_windows_and_home_paths_on_any_os(tmp_path, host_path):
    make_repo(tmp_path)
    with pytest.raises(WorkspaceError, match=r"\./repos"):
        resolve_repo(tmp_path / "repos", host_path)


def test_resolve_repo_requires_go_mod(tmp_path):
    (tmp_path / "repos" / "nomod").mkdir(parents=True)
    with pytest.raises(WorkspaceError, match="go.mod"):
        resolve_repo(tmp_path / "repos", "nomod")


def test_test_path_for():
    assert test_path_for("mean.go") == "mean_test.go"
    assert test_path_for("sub/x.go") == "sub/x_test.go"


def test_create_copies_without_git_and_leaves_source_untouched(tmp_path):
    repo = make_repo(tmp_path)
    ws = Workspace.create(tmp_path / "work", "job1", repo)
    assert (ws.root / "a.go").exists() and not (ws.root / ".git").exists()
    removed = ws.delete_existing_tests()
    assert removed == ["a_test.go"]
    assert (repo / "a_test.go").exists(), "source repo must never be modified"
    assert ws.scratch.is_dir() and not ws.scratch.is_relative_to(ws.root)


def test_create_skips_symlinks_and_cleans_up_on_failure(tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    outside = tmp_path / "outside.txt"
    outside.write_text("secret")
    try:
        os.symlink(outside, repo / "link.txt")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not available on this host")
    ws = Workspace.create(tmp_path / "work", "job1", repo)
    assert not os.path.lexists(ws.root / "link.txt")
    assert (ws.root / "a.go").exists()

    def boom(src, dst, ignore=None):
        Path(dst).mkdir(parents=True)
        raise OSError("disk full")

    monkeypatch.setattr("app.workspace.shutil.copytree", boom)
    with pytest.raises(OSError, match="disk full"):
        Workspace.create(tmp_path / "work", "job2", repo)
    assert not (tmp_path / "work" / "job2").exists()


def test_seed_rejects_invalid_package_name(tmp_path):
    ws = Workspace.create(tmp_path / "work", "job1", make_repo(tmp_path))
    with pytest.raises(WorkspaceError, match="package name"):
        ws.seed_packages([("sub", "bad name; rm")])


def test_seed_packages_only_where_no_tests(tmp_path):
    ws = Workspace.create(tmp_path / "work", "job1", make_repo(tmp_path))
    seeded = ws.seed_packages([(".", "demo"), ("sub", "sub")])  # root still has a_test.go
    assert seeded == [f"sub/{SEED_FILE}"]
    assert ws.read(f"sub/{SEED_FILE}") == "package sub\n"
    assert ws.test_files() == ["a_test.go"]
    assert ws.test_files(include_seeds=True) == ["a_test.go", f"sub/{SEED_FILE}"]


def test_write_test_guards(tmp_path):
    ws = Workspace.create(tmp_path / "work", "job1", make_repo(tmp_path))
    with pytest.raises(WorkspaceError):
        ws.write_test("a.go", "package demo\n")
    with pytest.raises(WorkspaceError):
        ws.write_test("../escape_test.go", "x")
    ws.write_test("sub/b_test.go", "package sub\n")
    assert ws.read("sub/b_test.go") == "package sub\n"


def test_snapshot_restore_handles_absent_files(tmp_path):
    ws = Workspace.create(tmp_path / "work", "job1", make_repo(tmp_path))
    snap = ws.snapshot(["new_test.go", "go.mod"])
    ws.write_test("new_test.go", "package demo\n")
    (ws.root / "go.mod").write_text("module changed\n")
    ws.restore(snap)
    assert ws.read("new_test.go") is None
    assert ws.read("go.mod") == "module example.com/demo\n\ngo 1.17\n"
