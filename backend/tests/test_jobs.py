# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
import asyncio
import json
from pathlib import Path

import pytest

from app.config import Settings
from app.engine.run import JobFailed
from app.jobs import JobConflict, JobManager, JobRejected
from app.models import JobRequest, JobStatus, StopReason, Summary, TokenUsage
from tests.fakes import fake_llm


def summary(reason=StopReason.TARGET_REACHED) -> Summary:
    return Summary(stop_reason=reason, message="m", target=80, baseline_percent=0, final_percent=80,
                   iterations=[], test_files=[], tests_added=[], suspected_bugs=[], per_file=[],
                   tokens=TokenUsage(), duration_s=0.1)


def manager(tmp_path, runner, key="k"):
    s = Settings(groq_api_key=key, output_dir=tmp_path)
    return JobManager(s, runner=runner, llm_factory=fake_llm)


async def finish(job):
    await job.task


async def test_successful_job_emits_lifecycle(tmp_path):
    async def runner(job, emit, cancel):
        await emit("iteration_started", {"index": 1, "percent": 0})
        return summary()

    m = manager(tmp_path, runner)
    job = m.start(JobRequest(repo_path="stats"))
    await finish(job)
    assert job.status is JobStatus.COMPLETED
    assert [e.type for e in job.events] == ["job_started", "iteration_started", "job_completed",
                                            "llm_request", "summary_generated"]
    assert [e.seq for e in job.events] == [0, 1, 2, 3, 4]


async def test_stream_replays_and_tails_without_duplicates(tmp_path):
    gate = asyncio.Event()

    async def runner(job, emit, cancel):
        await emit("a", {})
        await gate.wait()
        await emit("b", {})
        return summary()

    m = manager(tmp_path, runner)
    job = m.start(JobRequest(repo_path="stats"))
    await asyncio.sleep(0)  # let job_started + "a" happen
    await asyncio.sleep(0)

    async def collect():
        return [e.type async for e in job.stream()]

    early = asyncio.create_task(collect())
    await asyncio.sleep(0)
    gate.set()
    await finish(job)
    late = [e.type async for e in job.stream()]  # subscribe after completion
    assert await early == late == ["job_started", "a", "b", "job_completed", "llm_request", "summary_generated"]


async def test_rejects_without_key_and_when_running_and_when_budget_low(tmp_path):
    async def slow(job, emit, cancel):
        await cancel.wait()
        return summary(StopReason.CANCELLED)

    with pytest.raises(JobRejected) as exc:
        manager(tmp_path, slow, key="").start(JobRequest(repo_path="stats"))
    assert exc.value.status == 400

    m = manager(tmp_path, slow)
    job = m.start(JobRequest(repo_path="stats"))
    with pytest.raises(JobConflict):
        m.start(JobRequest(repo_path="stats"))
    m.cancel(job.id)
    await finish(job)
    assert job.status is JobStatus.CANCELLED
    assert [e.type for e in job.events][-3:] == ["job_cancelled", "llm_request", "summary_generated"]

    m.ledger.add(m.settings.daily_token_budget)
    with pytest.raises(JobRejected) as exc:
        m.start(JobRequest(repo_path="stats"))
    assert exc.value.status == 429


async def test_failures_become_job_failed_events(tmp_path):
    async def failing(job, emit, cancel):
        raise JobFailed("repo_does_not_build", "nope", "compiler says no")

    m = manager(tmp_path, failing)
    job = m.start(JobRequest(repo_path="stats"))
    await finish(job)
    assert job.status is JobStatus.FAILED
    assert job.events[-1].data == {"reason": "repo_does_not_build", "message": "nope", "output": "compiler says no"}

    async def crashing(job, emit, cancel):
        raise RuntimeError("boom")

    job = manager(tmp_path, crashing).start(JobRequest(repo_path="stats"))
    await finish(job)
    assert job.events[-1].data["reason"] == "internal_error"


async def test_cancel_during_setup_marks_job_cancelled(tmp_path):
    async def cancelled(job, emit, cancel):
        raise JobFailed("cancelled", "Cancelled before the baseline finished.")

    job = manager(tmp_path, cancelled).start(JobRequest(repo_path="stats"))
    await finish(job)
    assert job.status is JobStatus.CANCELLED
    assert job.events[-1].type == "job_failed" and job.events[-1].data["reason"] == "cancelled"


async def test_events_jsonl_ends_with_terminal_and_summary_events(tmp_path):
    async def runner(job, emit, cancel):
        return summary()

    job = manager(tmp_path, runner).start(JobRequest(repo_path="stats"))
    await finish(job)
    lines = (tmp_path / job.id / "events.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["type"] for line in lines[-3:]] == ["job_completed", "llm_request", "summary_generated"]


async def test_write_failure_still_closes_job(tmp_path, monkeypatch):
    async def runner(job, emit, cancel):
        return summary()

    def boom(self, *a, **k):
        raise UnicodeEncodeError("cp1252", "x", 0, 1, "bad")

    monkeypatch.setattr(Path, "write_text", boom)
    job = manager(tmp_path, runner).start(JobRequest(repo_path="stats"))
    stream = asyncio.create_task(_collect(job))
    await finish(job)
    assert job.finished and job.status is JobStatus.COMPLETED
    assert (await asyncio.wait_for(stream, 1))[-3:] == ["job_completed", "llm_request", "summary_generated"]


async def _collect(job):
    return [e.type async for e in job.stream()]


async def test_early_stream_close_removes_subscriber(tmp_path):
    gate = asyncio.Event()

    async def runner(job, emit, cancel):
        await gate.wait()
        return summary()

    job = manager(tmp_path, runner).start(JobRequest(repo_path="stats"))
    await asyncio.sleep(0)
    gen = job.stream()
    assert (await gen.__anext__()).type == "job_started"
    assert len(job._subscribers) == 1
    await gen.aclose()
    assert job._subscribers == []
    gate.set()
    await finish(job)


def test_clean_work_dir_removes_stale_job_workspaces_but_not_a_running_one(tmp_path):
    from app.config import Settings
    from app.jobs import Job, JobManager
    from app.models import JobRequest
    work = tmp_path / "work"
    stale, running, other = work / "0123456789ab", work / "ba9876543210", work / "keep-me"
    for d in (stale / "repo", running / "repo", other):
        d.mkdir(parents=True)
    (work / "abcdefabcdef").write_text("a file, not a workspace")
    manager = JobManager(Settings(work_dir=work, output_dir=tmp_path / "out"))
    manager.jobs["ba9876543210"] = Job("ba9876543210", JobRequest(repo_path="x"))  # status running
    manager.clean_work_dir()
    assert not stale.exists()
    assert running.is_dir() and other.is_dir() and (work / "abcdefabcdef").is_file()


def test_clean_work_dir_without_work_dir_is_a_no_op(tmp_path):
    from app.config import Settings
    from app.jobs import JobManager
    JobManager(Settings(work_dir=tmp_path / "missing", output_dir=tmp_path / "out")).clean_work_dir()


@pytest.mark.parametrize("setting", [False, True])
async def test_parallel_writers_comes_from_the_server_setting_and_is_recorded(tmp_path, setting):
    async def runner(job, emit, cancel):
        return summary()

    m = JobManager(Settings(groq_api_key="k", output_dir=tmp_path, parallel_writers=setting), runner=runner,
                   llm_factory=fake_llm)
    request = JobRequest.model_validate({"repo_path": "stats", "options": {"parallel_writers": not setting}})
    job = m.start(request)
    await finish(job)
    assert job.request.options.parallel_writers is setting  # a client cannot choose it
    assert job.events[0].type == "job_started" and job.events[0].data["options"]["parallel_writers"] is setting
