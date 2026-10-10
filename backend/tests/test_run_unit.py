# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
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


def test_write_artifacts_exports_tests_and_report_but_not_events(tmp_path):
    (tmp_path / "repo").mkdir()
    (tmp_path / "scratch").mkdir()
    ws = Workspace(tmp_path / "repo", tmp_path / "scratch")
    ws.write_test("mean_test.go", "package stats\n")
    ws.write_test(SEED_FILE, "package stats\n")
    summary = Summary(stop_reason=StopReason.TARGET_REACHED, message="ok", target=80, baseline_percent=0,
                      final_percent=81, iterations=[], test_files=["mean_test.go"], tests_added=["TestMean"],
                      suspected_bugs=[], per_file=[], tokens=TokenUsage(), duration_s=1.0)
    dest = tmp_path / "out" / "j1"
    write_artifacts(dest, ws, summary)
    assert (dest / "tests" / "mean_test.go").read_text() == "package stats\n"
    assert not (dest / "tests" / SEED_FILE).exists()
    assert json.loads((dest / "report.json").read_text())["final_percent"] == 81
    assert not (dest / "events.jsonl").exists()  # the job appends it as events are emitted (app.jobs)


def test_write_artifacts_without_summary_exports_tests_but_not_seed(tmp_path):
    (tmp_path / "repo").mkdir()
    (tmp_path / "scratch").mkdir()
    ws = Workspace(tmp_path / "repo", tmp_path / "scratch")
    ws.write_test("mean_test.go", "package stats\n")
    ws.write_test(SEED_FILE, "package stats\n")
    dest = tmp_path / "out"
    write_artifacts(dest, ws, None)
    assert (dest / "tests" / "mean_test.go").exists()
    assert not (dest / "tests" / SEED_FILE).exists()
    assert not (dest / "report.json").exists()


def test_write_artifacts_failure_path_exports_only_accepted_files(tmp_path):
    (tmp_path / "repo").mkdir()
    (tmp_path / "scratch").mkdir()
    ws = Workspace(tmp_path / "repo", tmp_path / "scratch")
    ws.write_test("mean_test.go", "package stats" + chr(10))
    ws.write_test("half_baked_test.go", "package stats" + chr(10))
    dest = tmp_path / "out"
    write_artifacts(dest, ws, None, accepted=["mean_test.go"])
    assert (dest / "tests" / "mean_test.go").exists()
    assert not (dest / "tests" / "half_baked_test.go").exists()


class _Prepared:
    class deps:
        ws = None
    baseline = None


def _patch(monkeypatch, tmp_path, *, orchestrator_error=None):
    async def fake_prepare(*a, **k):
        return _Prepared()

    class FakeOrchestrator:
        def __init__(self, *a, **k): pass

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


def _summary(test_files):
    return Summary(stop_reason=StopReason.TARGET_REACHED, message="ok", target=80, baseline_percent=0,
                   final_percent=81, iterations=[], test_files=test_files, tests_added=["TestMean"],
                   suspected_bugs=[], per_file=[], tokens=TokenUsage(), duration_s=1.0)


def _patch_with_workspace(monkeypatch, tmp_path):
    source = tmp_path / "repos" / "stats"
    source.mkdir(parents=True)
    (source / "go.mod").write_text("module m\n")
    ws = Workspace.create(tmp_path / "work", "j1", source)
    ws.write_test("mean_test.go", "package stats\n")

    async def fake_prepare(*a, **k):
        prepared = _Prepared()
        prepared.deps = type("deps", (), {"ws": ws})
        return prepared

    class FakeOrchestrator:
        def __init__(self, *a, **k): pass

        async def run(self, baseline):
            return _summary(["mean_test.go"])

    monkeypatch.setattr(run_module, "prepare", fake_prepare)
    monkeypatch.setattr(run_module, "Orchestrator", FakeOrchestrator)
    return Settings(repos_dir=tmp_path / "repos", work_dir=tmp_path / "work", output_dir=tmp_path / "out")


async def test_workspace_is_deleted_once_the_tests_are_exported(monkeypatch, tmp_path):
    settings = _patch_with_workspace(monkeypatch, tmp_path)

    async def emit(t, d): pass

    await run_job("j1", JobRequest(repo_path="stats"), settings, None, emit, asyncio.Event(), lambda: [])
    assert (settings.output_dir / "j1" / "tests" / "mean_test.go").read_text() == "package stats\n"
    assert not (settings.work_dir / "j1").exists()


async def test_workspace_is_kept_when_the_export_fails(monkeypatch, tmp_path):
    settings = _patch_with_workspace(monkeypatch, tmp_path)

    def boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(run_module, "write_artifacts", boom)

    async def emit(t, d): pass

    await run_job("j1", JobRequest(repo_path="stats"), settings, None, emit, asyncio.Event(), lambda: [])
    assert (settings.work_dir / "j1" / "repo" / "mean_test.go").is_file()


async def test_a_refuted_suspected_bug_never_reaches_the_report(monkeypatch, tmp_path):
    from pathlib import Path
    from app.models import SuspectedBug
    settings = _patch_with_workspace(monkeypatch, tmp_path)
    bugs = [SuspectedBug(function="Mode", description="returns the value twice"),
            SuspectedBug(function="Median", description="not refuted")]

    class Orch:
        def __init__(self, *a, **k): pass

        async def run(self, baseline):
            return _summary(["mean_test.go"]).model_copy(update={"suspected_bugs": bugs})

    monkeypatch.setattr(run_module, "Orchestrator", Orch)
    fixture = Path(__file__).parent / "fixtures" / "run_f910d155f3cd" / "events.jsonl"
    events = [Event.model_validate_json(line) for line in fixture.read_text(encoding="utf-8").splitlines() if line]
    run_events = [e for e in events if e.type != "job_completed"]

    async def emit(t, d): pass

    summary = await run_job("j1", JobRequest(repo_path="stats"), settings, None, emit, asyncio.Event(),
                            lambda: run_events)
    assert [b.function for b in summary.suspected_bugs] == ["Median"]
    report = json.loads((settings.output_dir / "j1" / "report.json").read_text())
    assert [b["function"] for b in report["suspected_bugs"]] == ["Median"]
