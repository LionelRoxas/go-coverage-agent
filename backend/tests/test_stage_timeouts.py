# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
"""Separate timeouts for the compile, vet and test stages, and baseline failures that name the stage."""
import asyncio
from pathlib import Path

import pytest

from app.config import Settings
import app.engine.setup as baseline_setup  # not "setup"/"setup_module": pytest would run those as fixtures
from app.engine.setup import JobFailed, prepare
from app.gotools import CommandResult, GoPackage, GoTools
from app.models import JobRequest
from app.validator import ValidationKind, Validator
from app.workspace import Workspace


def test_stage_timeouts_have_defaults_and_read_the_env(monkeypatch):
    s = Settings()
    assert (s.compile_timeout_s, s.vet_timeout_s, s.test_timeout_s) == (300.0, 180.0, 300.0)
    monkeypatch.setenv("COMPILE_TIMEOUT_S", "11")
    monkeypatch.setenv("VET_TIMEOUT_S", "12")
    monkeypatch.setenv("TEST_TIMEOUT_S", "13")
    s = Settings()
    assert (s.compile_timeout_s, s.vet_timeout_s, s.test_timeout_s) == (11.0, 12.0, 13.0)


async def test_each_stage_runs_with_its_own_timeout(monkeypatch, tmp_path):
    seen = []

    async def fake_run(argv, cwd, timeout, env, cancel=None, max_chars=0):
        seen.append((argv[1], timeout))
        return CommandResult(argv=argv, exit_code=0, stdout="", stderr="", duration_ms=1)

    monkeypatch.setattr("app.gotools.run", fake_run)
    tools = GoTools(tmp_path, Settings(compile_timeout_s=1, vet_timeout_s=2, test_timeout_s=3, command_timeout_s=4))
    pkgs = [GoPackage("m", ".", "m")]
    await tools.compile(pkgs)
    await tools.vet(pkgs)
    await tools.test(pkgs, tmp_path / "c.out")
    assert seen == [("test", 1), ("vet", 2), ("test", 3)]


def _result(timed_out=False, code=0, ms=1):
    return CommandResult(argv=[], exit_code=-1 if timed_out else code, stdout="", stderr="", duration_ms=ms,
                         timed_out=timed_out)


class FakeTools:
    """GoTools stand-in for prepare(): every stage succeeds unless told to time out."""
    def __init__(self, slow: str, settings: Settings):
        self.slow, self.settings = slow, settings

    async def list_packages(self, exclude):
        if self.slow == "list":
            from app.gotools import GoToolError
            raise GoToolError("go list failed", _result(timed_out=True))
        return [GoPackage("example.com/m", ".", "m")]

    async def funcs(self):
        return []

    async def symbols(self):
        return []

    async def compile(self, pkgs):
        return _result(timed_out=self.slow == "compile")

    async def vet(self, pkgs):
        return _result(timed_out=self.slow == "vet")

    async def test(self, pkgs, profile: Path):
        if self.slow != "test":
            profile.write_text("mode: set\n")
        return _result(timed_out=self.slow == "test")


@pytest.mark.parametrize("slow, words", [
    ("list", ["go list", "COMMAND_TIMEOUT_S"]),
    ("compile", ["compile", "COMPILE_TIMEOUT_S"]),
    ("test", ["go test", "TEST_TIMEOUT_S"]),
    ("vet", ["go vet", "VET_TIMEOUT_S"]),
])
async def test_a_baseline_timeout_names_the_stage(monkeypatch, tmp_path, slow, words):
    repo = tmp_path / "repos" / "m"
    repo.mkdir(parents=True)
    (repo / "go.mod").write_text("module example.com/m\n")
    (repo / "m.go").write_text("package m\n")
    settings = Settings(repos_dir=tmp_path / "repos", work_dir=tmp_path / "work", output_dir=tmp_path / "out")
    monkeypatch.setattr(baseline_setup, "GoTools", lambda root, s, cancel: FakeTools(slow, s))

    async def emit(t, d): pass

    with pytest.raises(JobFailed) as exc:
        await prepare("j1", JobRequest(repo_path="m"), settings, None, emit, asyncio.Event())
    assert exc.value.reason == "baseline_timeout"
    for w in words:
        assert w in exc.value.message, exc.value.message


async def test_a_candidate_test_timeout_names_the_stage_not_a_fixed_60s(tmp_path):
    (tmp_path / "repo").mkdir()
    (tmp_path / "scratch").mkdir()
    ws = Workspace(tmp_path / "repo", tmp_path / "scratch")
    tools = FakeTools("test", Settings(test_timeout_s=300))
    v = Validator(ws, tools, [GoPackage("example.com/m", ".", "m")], [], "example.com/m")
    result = await v.check(prev=None, new_tests=["TestX"])  # prev is not reached on a failure
    assert result.kind is ValidationKind.TEST_FAILURE
    assert result.output.startswith("go test timed out after 300 s (TEST_TIMEOUT_S)")
