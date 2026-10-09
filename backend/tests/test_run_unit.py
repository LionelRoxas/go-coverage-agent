# AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
import asyncio
import json

import pytest

from app.config import Settings
from app.engine import run as run_module
from app.engine.run import JobFailed, prepare, run_job, write_artifacts
from app.llm.client import LLMFatal
from app.models import Event, JobRequest, StopReason, Summary, TokenUsage
from app.workspace import SEED_FILE, Workspace


async def test_prepare_rejects_bad_repo_path(tmp_path):
    (tmp_path / "repos").mkdir()
    settings = Settings(repos_dir=tmp_path / "repos", work_dir=tmp_path / "work")

    async def emit(t, d): pass

    with pytest.raises(JobFailed) as exc:
        await prepare("j1", JobRequest(repo_path="missing"), settings, llm=None, emit=emit, cancel=asyncio.Event())
    assert exc.value.reason == "invalid_repo"


def test_write_artifacts_exports_tests_report_and_events(tmp_path):
    (tmp_path / "repo").mkdir()
    (tmp_path / "scratch").mkdir()
    ws = Workspace(tmp_path / "repo", tmp_path / "scratch")
    ws.write_test("mean_test.go", "package stats\n")
    ws.write_test(SEED_FILE, "package stats\n")
    summary = Summary(stop_reason=StopReason.TARGET_REACHED, message="ok", target=80, baseline_percent=0,
                      final_percent=81, iterations=[], test_files=["mean_test.go"], tests_added=["TestMean"],
                      suspected_bugs=[], per_file=[], tokens=TokenUsage(), duration_s=1.0)
    events = [Event(seq=0, ts=1.0, type="job_started", data={})]
    dest = tmp_path / "out" / "j1"
    write_artifacts(dest, ws, summary, events)
    assert (dest / "tests" / "mean_test.go").read_text() == "package stats\n"
    assert not (dest / "tests" / SEED_FILE).exists()
    assert json.loads((dest / "report.json").read_text())["final_percent"] == 81
    assert (dest / "events.jsonl").read_text().count("\n") == 1


def test_write_artifacts_without_summary_exports_tests_but_not_seed(tmp_path):
    (tmp_path / "repo").mkdir()
    (tmp_path / "scratch").mkdir()
    ws = Workspace(tmp_path / "repo", tmp_path / "scratch")
    ws.write_test("mean_test.go", "package stats\n")
    ws.write_test(SEED_FILE, "package stats\n")
    dest = tmp_path / "out"
    write_artifacts(dest, ws, None, [])
    assert (dest / "tests" / "mean_test.go").exists()
    assert not (dest / "tests" / SEED_FILE).exists()
    assert not (dest / "report.json").exists()


class _Prepared:
    class deps:
        ws = None
    baseline = None


def _patch(monkeypatch, tmp_path, *, orchestrator_error=None):
    async def fake_prepare(*a, **k):
        return _Prepared()

    class FakeOrchestrator:
        def __init__(self, *a): pass

        async def run(self, baseline):
            raise orchestrator_error

    monkeypatch.setattr(run_module, "prepare", fake_prepare)
    monkeypatch.setattr(run_module, "Orchestrator", FakeOrchestrator)
    return Settings(repos_dir=tmp_path, work_dir=tmp_path, output_dir=tmp_path / "out")


async def test_llm_fatal_becomes_llm_auth(monkeypatch, tmp_path):
    settings = _patch(monkeypatch, tmp_path, orchestrator_error=LLMFatal("bad key"))

    async def emit(t, d): pass

    with pytest.raises(JobFailed) as exc:
        await run_job("j1", JobRequest(repo_path="x"), settings, None, emit, asyncio.Event(), lambda: [])
    assert exc.value.reason == "llm_auth"


async def test_artifact_failure_does_not_mask_job_failure(monkeypatch, tmp_path):
    settings = _patch(monkeypatch, tmp_path, orchestrator_error=LLMFatal("bad key"))

    def boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(run_module, "write_artifacts", boom)

    async def emit(t, d): pass

    with pytest.raises(JobFailed) as exc:
        await run_job("j1", JobRequest(repo_path="x"), settings, None, emit, asyncio.Event(), lambda: [])
    assert exc.value.reason == "llm_auth"
