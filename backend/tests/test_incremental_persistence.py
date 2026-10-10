# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
"""A run is on disk while it runs: each event is appended to events.jsonl as it is emitted and each accepted test file
is exported when it is accepted, so a process killed outright mid-run reloads as interrupted with its tests."""
import asyncio
import json

import httpx

from app.config import Settings
from app.engine import run as run_module
from app.engine.run import run_job
from app.jobs import JobManager
from app.main import create_app
from app.models import JobRequest, JobStatus, StopReason, Summary, TokenUsage
from app.workspace import Workspace
from tests.fakes import fake_llm

CODE = "package stats\n\nfunc TestMean(t *testing.T) {}\n"


def summary(test_files=("mean_test.go",)) -> Summary:
    return Summary(stop_reason=StopReason.TARGET_REACHED, message="ok", target=80, baseline_percent=0,
                   final_percent=81, iterations=[], test_files=list(test_files), tests_added=["TestMean"],
                   suspected_bugs=[], per_file=[], tokens=TokenUsage(), duration_s=1.0)


def settings_for(tmp_path) -> Settings:
    return Settings(groq_api_key="k", repos_dir=tmp_path / "repos", work_dir=tmp_path / "work",
                    output_dir=tmp_path / "out")


def saved_types(settings: Settings, job_id: str) -> list[str]:
    path = settings.output_dir / job_id / "events.jsonl"
    return [json.loads(line)["type"] for line in path.read_text(encoding="utf-8").splitlines()]


def fake_engine(monkeypatch, tmp_path, gate: asyncio.Event, accepted: asyncio.Event):
    """run_job with a fake setup and an orchestrator that accepts mean_test.go, then waits for `gate`."""
    source = tmp_path / "repos" / "stats"
    source.mkdir(parents=True)
    (source / "go.mod").write_text("module m\n")

    class Prepared:
        baseline = None

    async def fake_prepare(job_id, *a, **k):
        prepared = Prepared()
        prepared.deps = type("deps", (), {"ws": Workspace.create(tmp_path / "work", job_id, source)})
        return prepared

    class Orchestrator:
        def __init__(self, deps, request, emit, cancel, **k):
            self.ws, self.emit = deps.ws, emit

        async def run(self, baseline):
            await self.emit("baseline_measured", {"report": {"percent": 10.0, "files": []}})
            self.ws.write_test("mean_test.go", CODE)
            await self.emit("candidate_accepted", {"index": 1, "file": "mean.go", "test_file": "mean_test.go",
                                                   "tests": ["TestMean"], "percent": 55.0, "gain": 45.0})
            accepted.set()
            await gate.wait()
            return summary()

    monkeypatch.setattr(run_module, "prepare", fake_prepare)
    monkeypatch.setattr(run_module, "Orchestrator", Orchestrator)


def manager_running_the_engine(settings: Settings) -> JobManager:
    m = JobManager(settings, llm_factory=fake_llm)

    async def runner(job, emit, cancel):
        return await run_job(job.id, job.request, settings, None, emit, cancel, lambda: job.events)

    m._runner = runner
    return m


async def test_events_are_appended_as_they_are_emitted(tmp_path):
    gate = asyncio.Event()
    settings = settings_for(tmp_path)

    async def runner(job, emit, cancel):
        await emit("iteration_started", {"index": 1, "percent": 0})
        await gate.wait()
        return summary()

    m = JobManager(settings, runner=runner, llm_factory=fake_llm)
    job = m.start(JobRequest(repo_path="stats"))
    while len(job.events) < 2:
        await asyncio.sleep(0)
    assert saved_types(settings, job.id) == ["job_started", "iteration_started"]  # mid-run, before any terminal event
    gate.set()
    await job.task
    assert saved_types(settings, job.id) == [e.type for e in job.events]


async def test_no_duplicate_lines_after_a_normal_finish(tmp_path):
    settings = settings_for(tmp_path)

    async def runner(job, emit, cancel):
        await emit("iteration_started", {"index": 1, "percent": 0})
        return summary()

    m = JobManager(settings, runner=runner, llm_factory=fake_llm)
    job = m.start(JobRequest(repo_path="stats"))
    await job.task
    lines = (settings.output_dir / job.id / "events.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["seq"] for line in lines] == list(range(len(job.events)))
    assert [json.loads(line)["type"] for line in lines] == ["job_started", "iteration_started", "job_completed",
                                                            "llm_request", "summary_generated"]


async def test_accepted_tests_are_exported_when_accepted(tmp_path, monkeypatch):
    gate, accepted = asyncio.Event(), asyncio.Event()
    fake_engine(monkeypatch, tmp_path, gate, accepted)
    settings = settings_for(tmp_path)
    m = manager_running_the_engine(settings)
    job = m.start(JobRequest(repo_path="stats", options={"write_summary": False}))
    await asyncio.wait_for(accepted.wait(), 2)
    exported = settings.output_dir / job.id / "tests" / "mean_test.go"
    assert exported.read_text() == CODE and job.status is JobStatus.RUNNING
    gate.set()
    await job.task
    assert exported.read_text() == CODE  # the final export copies it again, unchanged
    assert saved_types(settings, job.id).count("candidate_accepted") == 1


async def test_a_hard_kill_reloads_as_interrupted_with_its_accepted_tests(tmp_path, monkeypatch):
    gate, accepted = asyncio.Event(), asyncio.Event()
    fake_engine(monkeypatch, tmp_path, gate, accepted)
    settings = settings_for(tmp_path)
    live = manager_running_the_engine(settings)
    job = live.start(JobRequest(repo_path="stats", options={"write_summary": False}))
    await asyncio.wait_for(accepted.wait(), 2)
    # The process dies here: no finally, no terminal event. A new process starts on the same folders.
    restarted = JobManager(settings, llm_factory=fake_llm)
    restarted.load_history()
    restarted.clean_work_dir()  # the dead run's working copy goes: its tests are served from output/<id>/tests
    saved = restarted.get(job.id)
    assert saved is not None and saved.status is JobStatus.INTERRUPTED
    assert saved.accepted_test_files() == ["mean_test.go"] and saved.percent == 55.0
    app = create_app(settings, restarted)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get(f"/api/jobs/{job.id}/files/mean_test.go")).text == CODE
        r = await client.post(f"/api/jobs/{job.id}/summary")
    assert r.status_code == 409 and r.json()["error"]["code"] == "no_report"
    gate.set()  # let the first manager's job end before the test does
    await job.task


async def test_the_live_job_is_listed_once_and_as_running(tmp_path):
    gate = asyncio.Event()
    settings = settings_for(tmp_path)

    async def runner(job, emit, cancel):
        await gate.wait()
        return summary()

    m = JobManager(settings, runner=runner, llm_factory=fake_llm)
    job = m.start(JobRequest(repo_path="stats"))
    await asyncio.sleep(0)
    assert (settings.output_dir / job.id / "events.jsonl").is_file()  # on disk, like a run killed at this point
    m.load_history()
    assert [j.id for j in m.list()] == [job.id] and m.get(job.id) is job
    assert job.snapshot()["status"] == "running"
    gate.set()
    await job.task
    assert job.status is JobStatus.COMPLETED


async def test_a_cut_last_line_does_not_swallow_the_next_event(tmp_path):
    """Write again on a run whose file ends in a partial line (a kill mid-write): the new events start a line."""
    from tests.test_saved_runs import run_events, summary_data, write_run
    out = tmp_path / "out"
    folder = write_run(out, "aaaaaaaaaaa1", run_events(("job_completed", summary_data())), tail='{"seq": 4, "ts"')
    m = JobManager(settings_for(tmp_path), llm_factory=fake_llm)
    m.load_history()
    job = m.write_summary_again("aaaaaaaaaaa1")
    await job.summary_task
    lines = (folder / "events.jsonl").read_text(encoding="utf-8").splitlines()
    assert lines[4] == '{"seq": 4, "ts"'
    assert [json.loads(line)["type"] for line in lines[5:]] == ["llm_request", "summary_generated"]
