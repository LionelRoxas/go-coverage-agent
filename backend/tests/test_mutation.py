# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
""""Run mutation test" on a finished run: sampling, classification, restoring the file, and the post-run job flow."""
import asyncio
import json

import httpx
import pytest

from app import mutation
from app.config import Settings
from app.gotools import CommandResult, GoPackage
from app.jobs import JobConflict, JobManager, JobRejected
from app.main import create_app
from app.models import Block, JobRequest, JobStatus, StopReason, Summary, TokenUsage
from app.mutation import MutationFailed, run_mutation, sample, try_mutant
from app.saved_runs import load_run
from app.workspace import Workspace

SRC = "package calc\n\nfunc Less(a, b int) bool {\n\treturn a < b\n}\n\nfunc Sum(a, b int) int {\n\treturn a + b\n}\n"
PKG = GoPackage(import_path="m", rel_dir=".", name="calc")


def site(file="calc.go", line=4, col=11, offset=None, original="<", mutated="<=", op="boundary"):
    off = SRC.index(f"a {original} b") + 2 if offset is None else offset
    return {"file": file, "line": line, "col": col, "offset": off, "original": original, "mutated": mutated, "op": op}


def block(file, sl, el, sc=1, ec=99):
    return Block(file=file, start_line=sl, start_col=sc, end_line=el, end_col=ec, statements=1)


def result(exit_code=0, out="", timed_out=False, cancelled=False):
    return CommandResult(argv=[], exit_code=exit_code, stdout=out, stderr="", duration_ms=1, timed_out=timed_out,
                         cancelled=cancelled)


def test_sample_is_limited_to_covered_sites_and_deterministic():
    sites = [site(file=f"f{i % 3}.go", line=i, col=5, offset=i) for i in range(1, 200)]
    blocks = [block("f0.go", 1, 120), block("f1.go", 50, 60, sc=6)]  # f1: line 50 col 5 is before the block
    picked = sample(sites, blocks, 10)
    assert len(picked) == 10 and picked == sample(list(reversed(sites)), blocks, 10)
    assert all(mutation.covered(s, blocks) for s in picked)
    assert picked == sorted(picked, key=lambda s: (s["file"], s["offset"]))
    eligible = [s for s in sites if mutation.covered(s, blocks)]
    assert not any(s["file"] == "f2.go" for s in eligible) and not any(s["line"] == 50 for s in eligible)
    assert sample(sites, blocks, 1000) == sorted(eligible, key=lambda s: (s["file"], s["offset"]))


class FakeTools:
    """Records the source each mutant was tested with; answers with the queued results."""

    def __init__(self, ws, *results):
        self.ws, self.results, self.seen = ws, list(results), []

    async def test_package(self, pkg, timeout_s):
        self.seen.append(self.ws.path("calc.go").read_text())
        item = self.results.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def workspace(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "go.mod").write_text("module m\n")
    (src / "calc.go").write_text(SRC)
    return Workspace.create(tmp_path / "work", "j", src)


@pytest.mark.parametrize("r,status", [
    (result(0, "ok  m 0.01s"), "survived"),
    (result(1, "--- FAIL: TestLess\nFAIL\tm\t0.01s"), "killed"),
    (result(1, "panic: test timed out after 30s\nFAIL\tm\t30.0s"), "timeout"),
    (result(-1, "", timed_out=True), "timeout"),
    (result(1, "./calc.go:4:11: invalid operation\nFAIL\tm [build failed]"), "invalid"),
    (result(1, "FAIL\tm [setup failed]"), "invalid"),
    (result(-1, "", cancelled=True), None),
])
async def test_try_mutant_classifies_and_restores_the_file(tmp_path, r, status):
    ws = workspace(tmp_path)
    tools = FakeTools(ws, r)
    assert await try_mutant(ws, tools, site(), PKG, 30) == status
    assert "return a <= b" in tools.seen[0]
    assert ws.path("calc.go").read_text() == SRC


async def test_try_mutant_restores_the_file_when_the_run_raises(tmp_path):
    ws = workspace(tmp_path)
    with pytest.raises(RuntimeError):
        await try_mutant(ws, FakeTools(ws, RuntimeError("boom")), site(), PKG, 30)
    assert ws.path("calc.go").read_text() == SRC


async def test_try_mutant_skips_a_site_whose_operator_moved(tmp_path):
    ws = workspace(tmp_path)
    tools = FakeTools(ws)
    assert await try_mutant(ws, tools, site(offset=0), PKG, 30) == "invalid" and tools.seen == []


def test_result_counts_timeouts_as_killed_and_skips_invalid():
    statuses = ["killed", "timeout", "survived", "invalid", "killed"]
    mutants = [{"file": "a.go" if i < 3 else "b.go", "status": s} for i, s in enumerate(statuses)]
    r = mutation.result(mutants)
    assert (r["total"], r["killed"], r["survived"], r["invalid"], r["timeouts"]) == (5, 3, 1, 1, 1)
    assert r["score"] == 75.0
    assert r["per_file"] == [{"file": "a.go", "killed": 2, "survived": 1, "score": 66.7},
                             {"file": "b.go", "killed": 1, "survived": 0, "score": 100.0}]
    assert mutation.result([{"file": "a.go", "status": "invalid"}])["score"] is None


# run_mutation with the Go tools faked: the profile covers Less (line 4) only.
PROFILE = "mode: set\nm/calc.go:3.27,5.2 1 1\nm/calc.go:7.26,9.2 1 0\n"


class FakeGoTools:
    instances: list["FakeGoTools"] = []

    def __init__(self, root, settings, cancel=None, tmp_dir=None):
        self.root, self.cancel, self.tested = root, cancel, []
        FakeGoTools.instances.append(self)
        self.baseline_ok, self.answers = FakeGoTools.baseline_ok, list(FakeGoTools.answers)

    async def list_packages(self, exclude):
        return [PKG]

    async def test(self, pkgs, profile):
        if not self.baseline_ok:
            return result(1, "--- FAIL: TestLess")
        profile.write_text(PROFILE)
        return result(0)

    async def mutate(self, rel):
        assert rel == "calc.go"
        return [site(), site(line=8, original="+", mutated="-", op="arithmetic")]

    async def test_package(self, pkg, timeout_s):
        self.tested.append(((self.root / "calc.go").read_text(), timeout_s))
        answer = self.answers.pop(0)
        if answer == "cancel":
            self.cancel.set()
            return result(-1, cancelled=True)
        return answer


def setup_run(tmp_path, monkeypatch, *answers, baseline_ok=True, **settings):
    repos = tmp_path / "repos"
    (repos / "stats").mkdir(parents=True)
    (repos / "stats" / "go.mod").write_text("module m\n")
    (repos / "stats" / "calc.go").write_text(SRC)
    (repos / "stats" / "calc_test.go").write_text("package calc\n")  # deleted, as the run did
    tests = tmp_path / "out" / "j" / "tests"
    tests.mkdir(parents=True)
    (tests / "calc_test.go").write_text("package calc\n// kept\n")
    FakeGoTools.instances, FakeGoTools.baseline_ok, FakeGoTools.answers = [], baseline_ok, answers
    monkeypatch.setattr(mutation, "GoTools", FakeGoTools)
    return Settings(repos_dir=repos, work_dir=tmp_path / "work", output_dir=tmp_path / "out", **settings)


async def test_run_mutation_tests_covered_sites_only_and_reports(tmp_path, monkeypatch):
    s = setup_run(tmp_path, monkeypatch, result(1, "--- FAIL: TestLess"), mutation_timeout_s=7)
    events = []

    async def emit(t, d):
        events.append((t, d))

    r = await run_mutation("j", JobRequest(repo_path="stats"), s, emit, asyncio.Event())
    tools = FakeGoTools.instances[0]
    assert [t for t, _ in events] == ["mutation_started", "mutant_result"]
    assert events[0][1] == {"total": 1}  # Sum (line 8) is not covered
    assert events[1][1] == {"index": 1, "file": "calc.go", "line": 4, "original": "<", "mutated": "<=",
                            "op": "boundary", "status": "killed"}
    assert tools.tested == [(SRC.replace("a < b", "a <= b"), 7)]
    assert (r["killed"], r["survived"], r["score"]) == (1, 0, 100.0) and r["mutants"] == [events[1][1]]
    assert not (s.work_dir / "j-mutation").exists()


async def test_run_mutation_copies_the_kept_tests_into_a_fresh_copy(tmp_path, monkeypatch):
    s = setup_run(tmp_path, monkeypatch, result(0))
    seen = {}

    async def emit(t, d):
        if t == "mutation_started":
            root = FakeGoTools.instances[0].root
            seen.update(tests=sorted(p.name for p in root.glob("*_test.go")),
                        kept=(root / "calc_test.go").read_text())

    await run_mutation("j", JobRequest(repo_path="stats"), s, emit, asyncio.Event())
    assert seen == {"tests": ["calc_test.go", "zz_coverage_seed_test.go"], "kept": "package calc\n// kept\n"}


async def test_baseline_failure_stops_with_a_clear_error(tmp_path, monkeypatch):
    s = setup_run(tmp_path, monkeypatch, baseline_ok=False)

    async def emit(t, d):
        raise AssertionError("no event before the baseline passes")

    with pytest.raises(MutationFailed) as exc:
        await run_mutation("j", JobRequest(repo_path="stats"), s, emit, asyncio.Event())
    assert exc.value.reason == "baseline_failed" and "do not pass in a fresh copy" in exc.value.message
    assert "TestLess" in exc.value.output and not (s.work_dir / "j-mutation").exists()


async def test_cancel_restores_the_file_and_stops(tmp_path, monkeypatch):
    s = setup_run(tmp_path, monkeypatch, "cancel")

    async def emit(t, d):
        pass

    with pytest.raises(MutationFailed) as exc:
        await run_mutation("j", JobRequest(repo_path="stats"), s, emit, asyncio.Event())
    assert exc.value.reason == "cancelled" and not (s.work_dir / "j-mutation").exists()


async def test_missing_repo_or_tests_fail_clearly(tmp_path, monkeypatch):
    s = setup_run(tmp_path, monkeypatch)

    async def emit(t, d):
        pass

    with pytest.raises(MutationFailed) as exc:
        await run_mutation("j", JobRequest(repo_path="gone"), s, emit, asyncio.Event())
    assert exc.value.reason == "invalid_repo" and "'gone'" in exc.value.message
    with pytest.raises(MutationFailed) as exc:
        await run_mutation("other", JobRequest(repo_path="stats"), s, emit, asyncio.Event())
    assert exc.value.reason == "no_tests"


def test_save_replaces_the_mutation_and_keeps_the_report(tmp_path):
    (tmp_path / "report.json").write_text(json.dumps({"final_percent": 80, "mutation": {"score": 1}}))
    mutation.save(tmp_path, {"score": 50.0}, None)
    assert json.loads((tmp_path / "report.json").read_text()) == {"final_percent": 80, "mutation": {"score": 50.0}}
    (tmp_path / "report.json").unlink()
    mutation.save(tmp_path, {"score": 50.0}, None)  # an interrupted run: its events hold the result
    assert not (tmp_path / "report.json").exists()
    mutation.save(tmp_path, {"score": 50.0}, summary())
    report = json.loads((tmp_path / "report.json").read_text())
    assert report["final_percent"] == 80 and report["mutation"] == {"score": 50.0}


# The post-run job flow (JobManager), with the mutation test itself faked.
PAYLOAD = {"total": 1, "killed": 0, "survived": 1, "invalid": 0, "timeouts": 0, "score": 0.0, "per_file": [],
           "mutants": []}


def summary():
    return Summary(stop_reason=StopReason.TARGET_REACHED, message="m", target=80, baseline_percent=0, final_percent=80,
                   iterations=[], test_files=["calc_test.go"], tests_added=["TestLess"], suspected_bugs=[],
                   per_file=[], tokens=TokenUsage(), duration_s=0.1)


def manager(tmp_path, gate=None, fail=None, accepted=True):
    repos = tmp_path / "repos"
    (repos / "stats").mkdir(parents=True, exist_ok=True)
    (repos / "stats" / "go.mod").write_text("module m\n")
    settings = Settings(groq_api_key="k", repos_dir=repos, work_dir=tmp_path / "work", output_dir=tmp_path / "out")
    calls = []

    async def runner(job, emit, cancel):
        if accepted:
            await emit("candidate_accepted", {"index": 1, "file": "calc.go", "test_file": "calc_test.go",
                                              "tests": ["TestLess"], "percent": 80.0, "gain": 80.0})
        (settings.output_dir / job.id / "report.json").write_text(summary().model_dump_json())  # as run_job does
        return summary()

    async def mutation_runner(job, emit, cancel):
        calls.append(job.id)
        await emit("mutation_started", {"total": 1})
        if gate is not None:
            await asyncio.wait([asyncio.ensure_future(gate.wait()), asyncio.ensure_future(cancel.wait())],
                               return_when=asyncio.FIRST_COMPLETED)
            if cancel.is_set():
                raise MutationFailed("cancelled", "Cancelled before the mutation test finished.")
        if fail is not None:
            raise fail
        return PAYLOAD

    return JobManager(settings, runner=runner, mutation_runner=mutation_runner), settings, calls


async def finished(m):
    job = m.start(JobRequest(repo_path="stats", options={"write_summary": False}))
    await job.task
    return job


async def test_mutation_events_follow_on_the_stream_and_are_saved(tmp_path):
    m, settings, _ = manager(tmp_path)
    job = await finished(m)
    m.mutation_test(job.id)
    assert job.mutating and not job.finished and m.running() is job and not job.writing_summary
    await job.mutation_task
    assert [e.type for e in job.events][-2:] == ["mutation_started", "mutation_completed"]
    assert job.finished and not job.mutating and job.events[-1].data == PAYLOAD
    report = json.loads((settings.output_dir / job.id / "report.json").read_text())
    assert report["mutation"] == PAYLOAD and report["final_percent"] == 80
    saved = [json.loads(line)["type"] for line in (settings.output_dir / job.id / "events.jsonl").open()]
    assert saved[-2:] == ["mutation_started", "mutation_completed"]


@pytest.mark.parametrize("error,reason", [(MutationFailed("baseline_failed", "no", "out"), "baseline_failed"),
                                          (RuntimeError("boom"), "internal_error")])
async def test_a_failure_is_an_event_and_nothing_is_saved(tmp_path, error, reason):
    m, settings, _ = manager(tmp_path, fail=error)
    job = await finished(m)
    m.mutation_test(job.id)
    await job.mutation_task
    assert job.events[-1].type == "mutation_failed" and job.events[-1].data["reason"] == reason
    assert "mutation" not in json.loads((settings.output_dir / job.id / "report.json").read_text())
    assert job.finished and m.running() is None


async def test_busy_rule_both_ways_and_cancel(tmp_path):
    gate = asyncio.Event()
    m, _, _ = manager(tmp_path, gate=gate)
    job = await finished(m)
    m.mutation_test(job.id)
    with pytest.raises(JobConflict):  # no new job while the mutation test runs
        m.start(JobRequest(repo_path="stats"))
    with pytest.raises(JobRejected) as exc:
        m.mutation_test(job.id)
    assert (exc.value.status, exc.value.code) == (409, "job_running")
    with pytest.raises(JobRejected) as exc:
        m.write_summary_again(job.id)
    assert exc.value.status == 409
    m.cancel(job.id)
    await asyncio.wait_for(job.mutation_task, 1)
    assert job.events[-1].type == "mutation_failed" and job.events[-1].data["reason"] == "cancelled"
    assert job.status is JobStatus.COMPLETED  # the run keeps its result

    running = m.start(JobRequest(repo_path="stats"))  # and no mutation test while a job runs
    with pytest.raises(JobRejected) as exc:
        m.mutation_test(job.id)
    assert (exc.value.status, exc.value.code) == (409, "job_running")
    await running.task


async def test_a_run_without_kept_tests_is_refused(tmp_path):
    m, _, calls = manager(tmp_path, accepted=False)
    job = await finished(m)
    with pytest.raises(JobRejected) as exc:
        m.mutation_test(job.id)
    assert (exc.value.status, exc.value.code) == (409, "no_tests") and calls == []


async def test_a_saved_run_is_mutation_tested_and_goes_back_to_disk(tmp_path):
    m, settings, _ = manager(tmp_path)
    job = await finished(m)
    before = job.events[-1].seq
    saved = load_run(settings.output_dir / job.id)  # a run reloaded after a restart, report.json without mutation
    m2, _, calls = manager(tmp_path)
    m2.jobs[saved.id] = saved
    assert saved.on_disk and saved.status is JobStatus.COMPLETED
    m2.mutation_test(saved.id)
    await saved.mutation_task
    assert calls == [saved.id] and saved.on_disk and saved.finished and saved.saved_event_count == before + 3
    again = load_run(settings.output_dir / job.id)  # and it reloads with the mutation test in its file and report
    assert again.status is JobStatus.COMPLETED and again.summary is not None
    assert [e.type for e in [e async for e in again.stream()]][-2:] == ["mutation_started", "mutation_completed"]


async def test_mutation_endpoint(tmp_path):
    gate = asyncio.Event()
    m, settings, _ = manager(tmp_path, gate=gate)
    app = create_app(settings, m)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.post("/api/jobs/nope/mutation")).status_code == 404
        job_id = (await client.post("/api/jobs", json={"repo_path": "stats",
                                                       "options": {"write_summary": False}})).json()["job_id"]
        await m.get(job_id).task
        r = await client.post(f"/api/jobs/{job_id}/mutation")
        assert r.status_code == 202 and r.json()["mutating"] is True and r.json()["writing_summary"] is False
        busy = await client.post("/api/jobs", json={"repo_path": "stats"})
        assert busy.status_code == 409
        assert busy.json()["error"]["message"] == f"Job {job_id} is still running a mutation test."
        again = await client.post(f"/api/jobs/{job_id}/mutation")
        assert again.status_code == 409 and again.json()["error"]["code"] == "job_running"
        gate.set()
        await m.get(job_id).mutation_task
        assert (await client.get(f"/api/jobs/{job_id}")).json()["mutating"] is False
