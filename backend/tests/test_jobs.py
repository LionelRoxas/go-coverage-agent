# AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
import asyncio

import pytest

from app.config import Settings
from app.engine.run import JobFailed
from app.jobs import JobConflict, JobManager, JobRejected
from app.models import JobRequest, JobStatus, StopReason, Summary, TokenUsage


def summary(reason=StopReason.TARGET_REACHED) -> Summary:
    return Summary(stop_reason=reason, message="m", target=80, baseline_percent=0, final_percent=80,
                   iterations=[], test_files=[], tests_added=[], suspected_bugs=[], per_file=[],
                   tokens=TokenUsage(), duration_s=0.1)


def manager(tmp_path, runner, key="k"):
    s = Settings(groq_api_key=key, output_dir=tmp_path)
    return JobManager(s, runner=runner)


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
    assert [e.type for e in job.events] == ["job_started", "iteration_started", "job_completed"]
    assert [e.seq for e in job.events] == [0, 1, 2]


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

    early, late = asyncio.create_task(collect()), None
    await asyncio.sleep(0)
    gate.set()
    await finish(job)
    late = [e.type async for e in job.stream()]  # subscribe after completion
    assert await early == late == ["job_started", "a", "b", "job_completed"]


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
    assert job.status is JobStatus.CANCELLED and job.events[-1].type == "job_cancelled"

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
