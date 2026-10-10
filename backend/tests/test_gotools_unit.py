# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
from pathlib import Path

from app.config import Settings
from app.gotools import GoTools, go_env, is_excluded, iter_json, read_module_info


def test_iter_json_reads_concatenated_objects():
    assert [o["a"] for o in iter_json('{"a": 1}\n{"a": 2}\n  ')] == [1, 2]


def test_is_excluded_matches_dir_and_children():
    pats = ["examples/**", "testdata/**"]
    assert is_excluded("examples", pats)
    assert is_excluded("examples/functions", pats)
    assert not is_excluded(".", pats)
    assert not is_excluded("sub", pats)


def test_read_module_info(tmp_path: Path):
    (tmp_path / "go.mod").write_text('module github.com/montanaflynn/stats\n\ngo 1.17\n')
    assert read_module_info(tmp_path) == ("github.com/montanaflynn/stats", "1.17")
    (tmp_path / "go.mod").write_text("module x\n")
    assert read_module_info(tmp_path) == ("x", "1.16")


def test_go_env_is_an_allowlist(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "secret")
    monkeypatch.setenv("PATH", "/usr/bin")
    env = go_env(Settings())
    assert "GROQ_API_KEY" not in env
    assert env["GOFLAGS"] == "-mod=readonly"
    assert env["GOTOOLCHAIN"] == "local"
    assert env["CGO_ENABLED"] == "0"
    assert env["PATH"] == "/usr/bin"


def test_go_temp_dirs_go_to_the_jobs_folder_when_given(tmp_path):
    assert "GOTMPDIR" not in GoTools(tmp_path, Settings())._env
    tools = GoTools(tmp_path, Settings(), tmp_dir=tmp_path / "scratch" / "gotmp")
    assert tools._env["GOTMPDIR"] == str(tmp_path / "scratch" / "gotmp")
    assert (tmp_path / "scratch" / "gotmp").is_dir()
