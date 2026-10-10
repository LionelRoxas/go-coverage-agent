# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
import asyncio

import pytest

from app.config import Settings
from app.gotools import CommandResult
from app.repos import SAMPLES, clone_sample, list_repos, list_samples


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


async def test_concurrent_clones_run_git_once(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    calls = []

    async def slow(argv, cwd, **k):
        calls.append(argv)
        await asyncio.sleep(0.05)
        (settings.repos_dir / "stats").mkdir()
        (settings.repos_dir / "stats" / "go.mod").write_text("module example.com/stats\n")
        return _result(0)

    monkeypatch.setattr("app.repos.run", slow)
    a, b = await asyncio.gather(clone_sample(settings), clone_sample(settings))
    assert len(calls) == 1 and a.path == b.path == "stats"


def test_allowlist_shape():
    assert list(SAMPLES) == ["stats", "semver", "xstrings", "humanize", "btree", "decimal"]
    for sid, s in SAMPLES.items():
        assert s.id == sid and s.url == f"https://github.com/{s.name}" and s.description and s.license
        assert s.ref is None or s.ref.startswith("v")
    assert SAMPLES["btree"].license == "Apache-2.0"


def test_list_samples_downloaded_flag(tmp_path):
    (tmp_path / "semver").mkdir()
    (tmp_path / "semver" / "go.mod").write_text("module x\n")
    (tmp_path / "btree").mkdir()  # exists but is not a module
    flags = {s["id"]: s["downloaded"] for s in list_samples(tmp_path)}
    assert flags["semver"] is True and flags["btree"] is False and flags["stats"] is False
    assert list_samples(tmp_path)[1]["path"] == "semver"


async def test_clone_command_arguments(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    seen = {}

    async def fake(argv, cwd, timeout, env):
        seen.update(argv=argv, timeout=timeout, env=env)
        (settings.repos_dir / "semver").mkdir()
        (settings.repos_dir / "semver" / "go.mod").write_text("module x\n\ngo 1.21\n")
        return _result(0)

    monkeypatch.setattr("app.repos.run", fake)
    info = await clone_sample(settings, "semver")
    assert info.path == "semver"
    assert seen["argv"] == ["git", "clone", "--depth", "1", "--branch", SAMPLES["semver"].ref, "--no-recurse-submodules", "--",
                            "https://github.com/Masterminds/semver", str(settings.repos_dir / "semver")]
    assert seen["env"]["GIT_TERMINAL_PROMPT"] == "0" and set(seen["env"]) == {"PATH", "HOME", "GIT_TERMINAL_PROMPT"}


async def test_stats_clones_default_branch(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    seen = {}

    async def fake(argv, cwd, **k):
        seen["argv"] = argv
        (settings.repos_dir / "stats").mkdir()
        (settings.repos_dir / "stats" / "go.mod").write_text("module x\n")
        return _result(0)

    monkeypatch.setattr("app.repos.run", fake)
    await clone_sample(settings)
    assert "--branch" not in seen["argv"] and "--no-recurse-submodules" in seen["argv"]


async def test_clone_rejects_go_mod_with_require_and_removes_it(tmp_path, monkeypatch):
    settings = _settings(tmp_path)

    async def fake(argv, cwd, **k):
        (settings.repos_dir / "decimal").mkdir()
        (settings.repos_dir / "decimal" / "go.mod").write_text("// header\nmodule x\n\nrequire (\n	github.com/a/b v1.0.0\n)\n")
        return _result(0)

    monkeypatch.setattr("app.repos.run", fake)
    with pytest.raises(RuntimeError, match="dependencies"):
        await clone_sample(settings, "decimal")
    assert not (settings.repos_dir / "decimal").exists()


async def test_clone_unknown_sample_is_key_error(tmp_path):
    with pytest.raises(KeyError):
        await clone_sample(_settings(tmp_path), "nope")


async def test_existing_non_module_error_names_the_sample(tmp_path):
    settings = _settings(tmp_path)
    (settings.repos_dir / "btree").mkdir()
    with pytest.raises(RuntimeError, match=r"repos/btree exists but is not a Go module"):
        await clone_sample(settings, "btree")


def _module(d, module):
    d.mkdir(parents=True)
    (d / "go.mod").write_text(f"module {module}\n")


def test_list_repos_adds_host_modules_read_only_under_host_prefix(tmp_path):
    repos, host = tmp_path / "repos", tmp_path / "host-repos"
    _module(repos / "stats", "github.com/montanaflynn/stats")
    _module(host / "mine", "example.com/mine")
    _module(host / "team" / "svc", "example.com/svc")
    found = list_repos(repos, host)
    assert [(r.path, r.module, r.read_only) for r in found] == [
        ("host/mine", "example.com/mine", True),
        ("host/team/svc", "example.com/svc", True),
        ("stats", "github.com/montanaflynn/stats", False),
    ]


def test_list_repos_hides_an_app_folder_named_host(tmp_path):
    """`host/...` always means the read-only host folder, so ./repos/host could never be picked."""
    repos = tmp_path / "repos"
    _module(repos / "host" / "x", "example.com/x")
    assert list_repos(repos, tmp_path / "missing") == []


def test_list_repos_without_host_dir_lists_only_app_repos(tmp_path):
    _module(tmp_path / "repos" / "a", "example.com/a")
    assert [r.path for r in list_repos(tmp_path / "repos", tmp_path / "nope")] == ["a"]
