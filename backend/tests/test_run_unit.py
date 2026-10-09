# AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
import asyncio
import json

import pytest

from app.config import Settings
from app.engine.run import JobFailed, prepare, write_artifacts
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
