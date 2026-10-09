# AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
import pytest

from app.config import Settings
from app.gotools import CommandResult
from app.repos import clone_sample, list_repos


def test_list_repos_finds_modules_two_levels_deep(tmp_path):
    (tmp_path / "stats").mkdir()
    (tmp_path / "stats" / "go.mod").write_text("module github.com/montanaflynn/stats\n\ngo 1.17\n")
    (tmp_path / "stats" / "mean.go").write_text("package stats\n")
    (tmp_path / "stats" / "mean_test.go").write_text("package stats\n")
    (tmp_path / "org" / "svc").mkdir(parents=True)
    (tmp_path / "org" / "svc" / "go.mod").write_text("module example.com/svc\n")
    (tmp_path / "notgo").mkdir()
    repos = list_repos(tmp_path)
    assert [(r.path, r.module, r.go_files, r.test_files) for r in repos] == [
        ("org/svc", "example.com/svc", 0, 0),
        ("stats", "github.com/montanaflynn/stats", 1, 1),
    ]


def test_list_repos_missing_dir_is_empty(tmp_path):
    assert list_repos(tmp_path / "nope") == []


def _settings(tmp_path):
    repos = tmp_path / "repos"
    repos.mkdir()
    return Settings(groq_api_key="k", repos_dir=repos, work_dir=tmp_path / "w", output_dir=tmp_path / "o")


def _result(code):
    return CommandResult(argv=[], exit_code=code, stdout="", stderr="fatal", duration_ms=1)


async def test_clone_sample_missing_git_is_runtime_error(tmp_path, monkeypatch):
    async def no_git(*a, **k):
        raise FileNotFoundError("git")

    monkeypatch.setattr("app.repos.run", no_git)
    with pytest.raises(RuntimeError, match="could not start"):
        await clone_sample(_settings(tmp_path))


async def test_clone_sample_failure_removes_partial_dest(tmp_path, monkeypatch):
    settings = _settings(tmp_path)

    async def fail(argv, cwd, **k):
        (settings.repos_dir / "stats").mkdir()
        return _result(128)

    monkeypatch.setattr("app.repos.run", fail)
    with pytest.raises(RuntimeError, match="git clone failed"):
        await clone_sample(settings)
    assert not (settings.repos_dir / "stats").exists()


async def test_clone_sample_without_go_mod_is_runtime_error(tmp_path, monkeypatch):
    settings = _settings(tmp_path)

    async def ok(argv, cwd, **k):
        (settings.repos_dir / "stats").mkdir()
        return _result(0)

    monkeypatch.setattr("app.repos.run", ok)
    with pytest.raises(RuntimeError, match="no go.mod"):
        await clone_sample(settings)


async def test_clone_sample_never_touches_existing_non_module_dir(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    (settings.repos_dir / "stats").mkdir()
    (settings.repos_dir / "stats" / "mine.txt").write_text("keep")

    async def must_not_run(*a, **k):
        raise AssertionError("run must not be called")

    monkeypatch.setattr("app.repos.run", must_not_run)
    with pytest.raises(RuntimeError, match="not a Go module"):
        await clone_sample(settings)
    assert (settings.repos_dir / "stats" / "mine.txt").read_text() == "keep"
