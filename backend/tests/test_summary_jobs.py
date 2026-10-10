# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
"""The end-of-run AI summary: emitted after job_completed / job_cancelled, saved to report.json and SUMMARY.md."""
import asyncio
import json

import httpx
import pytest

from app.config import Settings
from app.engine.run import JobFailed
from app.jobs import JobConflict, JobManager, JobRejected
from app.llm.client import LLMBudgetExhausted, LLMCancelled, LLMError, LLMTimeout
from app.main import create_app
from app.models import JobOptions, JobRequest, JobStatus, StopReason, Summary, TokenUsage
from app.summary.report import NOTE
from tests.fakes import FakeLLM, run_summary


TOKENS = TokenUsage(prompt_tokens=1000, completion_tokens=500)


def summary(reason=StopReason.TARGET_REACHED, tokens=TOKENS):
    return Summary(stop_reason=reason, message="m", target=80, baseline_percent=0, final_percent=80, iterations=[],
                   test_files=["mean_test.go"], tests_added=["TestMean"], suspected_bugs=[], per_file=[],
                   tokens=tokens, duration_s=0.1)


def setup(tmp_path, responses=None, reason=StopReason.TARGET_REACHED, **settings):
    llms: list[FakeLLM] = []

    def factory(emit, cancel):
        llms.append(FakeLLM(list(responses) if responses is not None else [run_summary()]))
        return llms[-1]

    async def runner(job, emit, cancel):
        await emit("baseline_measured", {"report": {"percent": 0.0, "files": []}})
        return summary(reason)

    m = JobManager(Settings(groq_api_key="k", output_dir=tmp_path, **settings), runner=runner, llm_factory=factory)
    return m, llms


def types(job):
    return [e.type for e in job.events]


async def run(m, **options):
    job = m.start(JobRequest(repo_path="stats", options=JobOptions(**options)))
    await job.task
    return job


async def test_summary_follows_job_completed_and_is_saved(tmp_path):
    m, llms = setup(tmp_path)
    job = await run(m)
    assert job.status is JobStatus.COMPLETED
    assert types(job)[-3:] == ["job_completed", "llm_request", "summary_generated"]
    assert job.events[-2].data == {"role": "summarizer", "reasoning_effort": "medium"}
    data = job.events[-1].data
    assert data["business"] == run_summary().business.model_dump() and data["dropped_sentences"] == 0
    assert data["tokens"] == {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}
    assert "cost_usd" not in data
    assert llms[0].calls[0]["role"] == "summarizer" and '"repo":"stats"' in llms[0].calls[0]["user"]

    report = json.loads((tmp_path / job.id / "report.json").read_text(encoding="utf-8"))
    assert report["final_percent"] == 80 and report["ai_summary"]["technical"] == data["technical"]
    assert report["ai_summary"]["model"] == "openai/gpt-oss-120b" and "ai_summary_error" not in report
    md = (tmp_path / job.id / "SUMMARY.md").read_text(encoding="utf-8")
    assert md.startswith("# AI summary: stats\n") and NOTE in md and "openai/gpt-oss-120b" in md
    assert "## For stakeholders" in md and "## For engineering teams" in md


async def test_stream_stays_open_until_the_summary_is_written(tmp_path):
    m, _ = setup(tmp_path)
    job = m.start(JobRequest(repo_path="stats"))
    await asyncio.sleep(0)
    collected = asyncio.create_task(_collect(job))
    await job.task
    assert (await asyncio.wait_for(collected, 1))[-2:] == ["llm_request", "summary_generated"]


async def _collect(job):
    return [e.type async for e in job.stream()]


async def test_summary_after_a_cancelled_run(tmp_path):
    m, _ = setup(tmp_path, reason=StopReason.CANCELLED)
    job = await run(m)
    assert job.status is JobStatus.CANCELLED
    assert types(job)[-3:] == ["job_cancelled", "llm_request", "summary_generated"]


async def test_no_summary_when_turned_off_or_when_setup_failed(tmp_path):
    m, llms = setup(tmp_path)
    job = await run(m, write_summary=False)
    assert types(job)[-1] == "job_completed" and llms == []
    assert not (tmp_path / job.id / "SUMMARY.md").exists()

    async def failing(job, emit, cancel):
        raise JobFailed("repo_does_not_build", "nope")

    m._runner = failing
    job = await run(m)
    assert types(job)[-1] == "job_failed" and llms == []


@pytest.mark.parametrize("error, reason", [(LLMError("Groq returned 500"), "llm_error"),
                                           (LLMTimeout("Groq did not answer"), "timeout"),
                                           (LLMBudgetExhausted("The daily Groq token budget is used up."),
                                            "budget_exhausted")])
async def test_failure_is_reported_and_the_job_still_completes(tmp_path, error, reason):
    m, _ = setup(tmp_path, responses=[error])
    job = await run(m)
    assert job.status is JobStatus.COMPLETED and job.finished
    assert types(job)[-3:] == ["job_completed", "llm_request", "summary_failed"]
    assert job.events[-1].data == {"reason": reason, "message": str(error)}
    report = json.loads((tmp_path / job.id / "report.json").read_text(encoding="utf-8"))
    assert report["ai_summary_error"] == {"reason": reason, "message": str(error)} and "ai_summary" not in report
    assert not (tmp_path / job.id / "SUMMARY.md").exists()


async def test_unexpected_crash_is_an_internal_error(tmp_path):
    m, _ = setup(tmp_path, responses=[RuntimeError("boom")])
    job = await run(m)
    assert job.status is JobStatus.COMPLETED
    assert job.events[-1].type == "summary_failed" and job.events[-1].data["reason"] == "internal_error"


async def test_job_token_budget_is_checked_before_calling(tmp_path):
    m, llms = setup(tmp_path)
    m._runner = lambda job, emit, cancel: _done(summary(tokens=TokenUsage(prompt_tokens=8000, completion_tokens=2000)))
    job = await run(m, max_llm_tokens=10_000)
    assert types(job)[-2:] == ["job_completed", "summary_failed"]
    assert job.events[-1].data["reason"] == "budget_exhausted" and llms == []


async def _done(value):
    return value


async def test_cost_separates_the_run_and_the_summary_call(tmp_path):
    class BigLLM(FakeLLM):
        async def complete(self, **kw):
            out, _ = await super().complete(**kw)
            return out, TokenUsage(prompt_tokens=10_000, completion_tokens=5_000)

    m, _ = setup(tmp_path, groq_price_input_per_m=0.15, groq_price_output_per_m=0.60)
    m._llm_factory = lambda emit, cancel: BigLLM([run_summary()])
    m._runner = lambda job, emit, cancel: _done(summary(tokens=TokenUsage(prompt_tokens=100_000, completion_tokens=50_000)))
    job = await run(m)
    # run 0.015 + 0.03; summary 0.0015 + 0.003; together input 110000 * 0.15 / 1e6, output 55000 * 0.60 / 1e6
    assert job.events[-1].data["cost_usd"] == {"run": 0.045, "summary": 0.0045, "input": 0.0165, "output": 0.033,
                                               "total": 0.0495}
    md = (tmp_path / job.id / "SUMMARY.md").read_text(encoding="utf-8")
    assert "Run cost $0.0450 · this summary call $0.0045 · run + this call $0.0495 (input $0.0165, output $0.0330)" in md
    report = json.loads((tmp_path / job.id / "report.json").read_text(encoding="utf-8"))
    assert report["tokens"] == {"prompt_tokens": 100_000, "completion_tokens": 50_000}  # the run's own
    assert report["summary_tokens"] == {"prompt_tokens": 10_000, "completion_tokens": 5_000, "total_tokens": 15_000}


async def test_no_cost_without_prices(tmp_path):
    m, _ = setup(tmp_path, groq_price_input_per_m=0.15)
    job = await run(m)
    assert "cost_usd" not in job.events[-1].data


async def test_grounding_drops_invented_sentences(tmp_path):
    m, _ = setup(tmp_path, responses=[run_summary("Coverage rose from 0% to 80%. It saved 37 hours.")])
    job = await run(m)
    data = job.events[-1].data
    assert data["business"]["headline"] == "Coverage rose from 0% to 80%." and data["dropped_sentences"] == 1


async def test_write_again_reopens_the_stream_and_replaces_the_summary(tmp_path):
    m, llms = setup(tmp_path)
    job = await run(m, write_summary=False)
    assert job.finished
    m.write_summary_again(job.id)
    assert not job.finished
    with pytest.raises(JobRejected) as exc:  # one at a time
        m.write_summary_again(job.id)
    assert exc.value.status == 409
    collected = asyncio.create_task(_collect(job))
    await job.summary_task
    assert job.finished and len(llms) == 1
    assert (await asyncio.wait_for(collected, 1))[-3:] == ["job_completed", "llm_request", "summary_generated"]
    assert (tmp_path / job.id / "SUMMARY.md").exists()
    lines = (tmp_path / job.id / "events.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(lines[-1])["type"] == "summary_generated"


async def test_write_again_counts_earlier_summary_calls_toward_the_job_budget(tmp_path):
    m, llms = setup(tmp_path)
    m._runner = lambda job, emit, cancel: _done(summary(tokens=TokenUsage(prompt_tokens=9900, completion_tokens=0)))
    job = await run(m, max_llm_tokens=10_000)  # 9900 < 10000: the first summary is written; then 9900 + 150
    assert job.events[-1].type == "summary_generated"
    m.write_summary_again(job.id)
    await job.summary_task
    assert job.events[-1].type == "summary_failed" and job.events[-1].data["reason"] == "budget_exhausted"


async def test_write_again_keeps_an_earlier_summary_when_it_fails(tmp_path):
    m, _ = setup(tmp_path)
    job = await run(m)
    m._llm_factory = lambda emit, cancel: FakeLLM([LLMError("Groq returned 500")])
    m.write_summary_again(job.id)
    await job.summary_task
    report = json.loads((tmp_path / job.id / "report.json").read_text(encoding="utf-8"))
    assert "ai_summary" in report and report["ai_summary_error"]["reason"] == "llm_error"
    assert (tmp_path / job.id / "SUMMARY.md").exists()


async def test_write_again_refuses_running_and_failed_jobs(tmp_path):
    gate = asyncio.Event()

    async def slow(job, emit, cancel):
        await gate.wait()
        raise JobFailed("repo_does_not_build", "nope")

    m, _ = setup(tmp_path)
    m._runner = slow
    job = m.start(JobRequest(repo_path="stats"))
    await asyncio.sleep(0)
    with pytest.raises(JobRejected) as exc:
        m.write_summary_again(job.id)
    assert (exc.value.status, exc.value.code) == (409, "job_running")
    gate.set()
    await job.task
    with pytest.raises(JobRejected) as exc:
        m.write_summary_again(job.id)
    assert (exc.value.status, exc.value.code) == (409, "no_report")


async def test_summary_endpoint(tmp_path):
    repos = tmp_path / "repos"
    (repos / "stats").mkdir(parents=True)
    (repos / "stats" / "go.mod").write_text("module m\n")
    settings = Settings(groq_api_key="k", repos_dir=repos, work_dir=tmp_path / "work", output_dir=tmp_path / "out")

    async def runner(job, emit, cancel):
        return summary()

    gate = asyncio.Event()

    class GatedLLM(FakeLLM):
        async def complete(self, **kw):
            await gate.wait()
            return await super().complete(**kw)

    m = JobManager(settings, runner=runner, llm_factory=lambda emit, cancel: GatedLLM([run_summary()]))
    app = create_app(settings, m)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.post("/api/jobs/nope/summary")).status_code == 404
        job_id = (await client.post("/api/jobs", json={"repo_path": "stats",
                                                       "options": {"write_summary": False}})).json()["job_id"]
        job = m.get(job_id)
        assert job.request.options.write_summary is False
        await job.task
        blocked = await client.post(f"/api/jobs/{job_id}/summary", headers={"origin": "http://evil.example"})
        assert blocked.status_code == 403
        r = await client.post(f"/api/jobs/{job_id}/summary", headers={"origin": "http://localhost:3000"})
        assert r.status_code == 202 and r.json()["id"] == job_id
        again = await client.post(f"/api/jobs/{job_id}/summary")
        assert again.status_code == 409 and again.json()["error"]["code"] == "job_running"
        gate.set()
        await job.summary_task
        assert job.events[-1].type == "summary_generated"


class CancellableLLM(FakeLLM):
    """Waits like a Groq request until the summary's cancel event is set, then fails like GroqLLM does."""

    def __init__(self, cancel):
        super().__init__([run_summary()])
        self.cancel, self.started = cancel, asyncio.Event()

    async def complete(self, *, on_request=None, **kw):
        if on_request is not None:
            await on_request("medium")
        self.started.set()
        await self.cancel.wait()
        raise LLMCancelled("cancelled during an LLM request")


async def test_the_terminal_event_is_saved_before_the_summary_is_written(tmp_path):
    """A restart while the summary is written must reload the run as completed, so its file holds job_completed."""
    m, _ = setup(tmp_path)
    llms = []
    m._llm_factory = lambda emit, cancel: llms.append(CancellableLLM(cancel)) or llms[-1]
    job = m.start(JobRequest(repo_path="stats"))
    while not llms:
        await asyncio.sleep(0)
    await llms[0].started.wait()
    saved = [json.loads(line)["type"] for line in (tmp_path / job.id / "events.jsonl").read_text("utf-8").splitlines()]
    assert saved[-2:] == ["job_completed", "llm_request"] and job.writing_summary
    m.cancel(job.id)
    await asyncio.wait_for(job.task, 1)
    saved = [json.loads(line)["type"] for line in (tmp_path / job.id / "events.jsonl").read_text("utf-8").splitlines()]
    assert saved[-3:] == ["job_completed", "llm_request", "summary_failed"]
    assert not (tmp_path / job.id / "events.jsonl.tmp").exists()


async def test_the_job_is_busy_until_its_summary_is_written_and_cancel_stops_the_summary(tmp_path):
    m, _ = setup(tmp_path)
    llms = []
    m._llm_factory = lambda emit, cancel: llms.append(CancellableLLM(cancel)) or llms[-1]
    job = m.start(JobRequest(repo_path="stats"))
    while not llms:
        await asyncio.sleep(0)
    await llms[0].started.wait()
    assert job.status is JobStatus.COMPLETED and job.writing_summary and job.snapshot()["writing_summary"]
    assert m.running() is job
    with pytest.raises(JobConflict):
        m.start(JobRequest(repo_path="stats"))
    m.cancel(job.id)
    await asyncio.wait_for(job.task, 1)
    assert job.status is JobStatus.COMPLETED and not job.writing_summary and m.running() is None
    assert types(job)[-3:] == ["job_completed", "llm_request", "summary_failed"]
    assert job.events[-1].data == {"reason": "cancelled", "message": "Cancelled while the summary was being written."}
    assert not job.cancel.is_set()  # the run's own cancel event is untouched


async def test_write_again_waits_for_another_busy_job(tmp_path):
    m, _ = setup(tmp_path)
    first = await run(m)
    gate = asyncio.Event()

    async def slow(job, emit, cancel):
        await gate.wait()
        return summary()

    m._runner = slow
    second = m.start(JobRequest(repo_path="stats", options=JobOptions(write_summary=False)))
    with pytest.raises(JobRejected) as exc:
        m.write_summary_again(first.id)
    assert (exc.value.status, exc.value.code) == (409, "job_running") and second.id in exc.value.message
    gate.set()
    await second.task


async def test_tokens_of_a_failed_summary_call_count_toward_the_job(tmp_path):
    error = LLMError("the model's answer was truncated")
    error.spent = TokenUsage(prompt_tokens=300, completion_tokens=200)
    m, _ = setup(tmp_path, responses=[error])
    job = await run(m)
    assert job.summary_tokens.total == 500
    report = json.loads((tmp_path / job.id / "report.json").read_text(encoding="utf-8"))
    assert report["summary_tokens"]["total_tokens"] == 500


async def test_start_conflict_says_the_summary_is_being_written(tmp_path):
    repos = tmp_path / "repos"
    (repos / "stats").mkdir(parents=True)
    (repos / "stats" / "go.mod").write_text("module m\n")
    settings = Settings(groq_api_key="k", repos_dir=repos, work_dir=tmp_path / "work", output_dir=tmp_path / "out")
    llms = []

    async def runner(job, emit, cancel):
        return summary()

    m = JobManager(settings, runner=runner,
                   llm_factory=lambda emit, cancel: llms.append(CancellableLLM(cancel)) or llms[-1])
    app = create_app(settings, m)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        job_id = (await client.post("/api/jobs", json={"repo_path": "stats"})).json()["job_id"]
        while not llms:
            await asyncio.sleep(0)
        await llms[0].started.wait()
        r = await client.post("/api/jobs", json={"repo_path": "stats"})
        assert r.status_code == 409 and r.json()["error"]["message"] == f"Job {job_id} is still writing its summary."
        assert (await client.get(f"/api/jobs/{job_id}")).json()["writing_summary"] is True
        assert (await client.post(f"/api/jobs/{job_id}/cancel")).status_code == 200
        await asyncio.wait_for(m.get(job_id).task, 1)
        assert m.get(job_id).events[-1].data["reason"] == "cancelled"


async def test_a_summary_that_takes_too_long_fails_as_a_timeout(tmp_path, monkeypatch):
    class HangingLLM(FakeLLM):
        async def complete(self, **kw):
            await asyncio.Event().wait()

    monkeypatch.setattr(JobManager, "summary_deadline_s", 0.05)
    m, _ = setup(tmp_path)
    m._llm_factory = lambda emit, cancel: HangingLLM([])
    job = await asyncio.wait_for(run(m), 2)
    assert job.status is JobStatus.COMPLETED and job.finished
    assert job.events[-1].data == {"reason": "timeout", "message": "The summary was not written within 0.05 s."}


def test_the_deadline_covers_one_timed_out_request_and_its_retry():
    m = JobManager(Settings(groq_api_key="k", groq_timeout_s=240))
    assert m.summary_deadline_s == 510


async def test_a_cancel_right_after_write_again_is_not_lost(tmp_path):
    m, llms = setup(tmp_path)
    job = await run(m, write_summary=False)
    m.write_summary_again(job.id)
    m.cancel(job.id)  # before the summary task has started
    await job.summary_task
    assert job.events[-1].data["reason"] == "cancelled" and llms == []


async def test_no_automatic_summary_call_after_groq_was_unreachable(tmp_path):
    m, llms = setup(tmp_path, reason=StopReason.LLM_UNAVAILABLE)
    job = await run(m)
    assert job.status is JobStatus.COMPLETED and llms == []
    assert types(job)[-2:] == ["job_completed", "summary_failed"]
    assert job.events[-1].data["reason"] == "llm_unavailable"
    assert "Write again" in job.events[-1].data["message"]
    m.write_summary_again(job.id)  # on request it is tried: Groq may be back
    await job.summary_task
    assert len(llms) == 1 and job.events[-1].type == "summary_generated"
