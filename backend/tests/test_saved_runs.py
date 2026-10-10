# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
"""Run history reloaded from ./output on startup (app.saved_runs, JobManager.load_history)."""
import json
import logging
import shutil
import uuid
from pathlib import Path

import httpx
import pytest

from app.config import Settings
from app.jobs import JobManager
from app.main import create_app
from app.models import JobStatus
from app.saved_runs import load_runs
from tests.fakes import fake_llm

FIXTURES = Path(__file__).parent / "fixtures"
REAL_RUN = FIXTURES / "run_fc080d7fc500"
OPTIONS = {"max_iterations": 20, "min_gain": 1.0, "patience": 2, "targets_per_iteration": 3, "max_fix_attempts": 2,
           "delete_existing_tests": True, "max_llm_tokens": 1000000, "exclude_patterns": []}


def summary_data(stop_reason="target_reached", final=80.0):
    return {"stop_reason": stop_reason, "message": "m", "target": 80.0, "baseline_percent": 10.0,
            "final_percent": final, "iterations": [], "test_files": ["mean_test.go"], "tests_added": ["TestMean"],
            "suspected_bugs": [], "per_file": [{"file": "mean.go", "before": 10.0, "after": final}],
            "tokens": {"prompt_tokens": 100, "completion_tokens": 50}, "duration_s": 12.0}


def run_events(*tail: tuple[str, dict]) -> list[tuple[str, dict]]:
    base = [("job_started", {"repo_path": "stats", "target_coverage": 80.0, "options": OPTIONS, "model": "m1"}),
            ("baseline_measured", {"report": {"percent": 10.0, "files": []}}),
            ("candidate_accepted", {"index": 1, "file": "mean.go", "test_file": "mean_test.go", "tests": ["TestMean"],
                                    "percent": 55.5, "gain": 45.5})]
    return [*base, *tail]


def write_run(out: Path, job_id: str, events: list[tuple[str, dict]], *, ts: float = 1000.0,
              report: dict | None = None, tail: str = "") -> Path:
    folder = out / job_id
    folder.mkdir(parents=True)
    lines = [json.dumps({"seq": i, "ts": ts + i, "type": t, "data": d}) + "\n" for i, (t, d) in enumerate(events)]
    (folder / "events.jsonl").write_text("".join(lines) + tail, encoding="utf-8")
    if report is not None:
        (folder / "report.json").write_text(json.dumps(report), encoding="utf-8")
    return folder


def settings_for(tmp_path, **kw) -> Settings:
    return Settings(**{"groq_api_key": "k", "repos_dir": tmp_path / "repos", "work_dir": tmp_path / "work",
                       "output_dir": tmp_path / "out", **kw})


def manager_for(tmp_path, **kw) -> JobManager:
    m = JobManager(settings_for(tmp_path, **kw), runner=None, llm_factory=fake_llm)
    m.load_history()
    return m


def client_for(manager: JobManager) -> httpx.AsyncClient:
    app = create_app(manager.settings, manager)
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


@pytest.fixture
def out(tmp_path) -> Path:
    (tmp_path / "out").mkdir()
    return tmp_path / "out"


def test_runs_load_with_their_status_and_numbers(tmp_path, out):
    write_run(out, "aaaaaaaaaaa1", run_events(("job_completed", summary_data(final=81.0))), ts=1000,
              report=summary_data(final=81.0))
    write_run(out, "aaaaaaaaaaa2", run_events(("job_cancelled", summary_data("cancelled", 55.5))), ts=2000)
    write_run(out, "aaaaaaaaaaa3", run_events(("job_failed", {"reason": "baseline_failed", "message": "x",
                                                                 "output": ""})), ts=3000)
    write_run(out, "aaaaaaaaaaa4", run_events(("job_failed", {"reason": "cancelled", "message": "x",
                                                                 "output": ""})), ts=4000)
    write_run(out, "aaaaaaaaaaa5", run_events(("llm_request", {"index": 2, "file": "x.go", "role": "writer"})),
              ts=5000)
    m = manager_for(tmp_path)

    snaps = {j.id: j.snapshot() for j in m.list()}
    assert snaps["aaaaaaaaaaa1"]["status"] == "completed" and snaps["aaaaaaaaaaa1"]["percent"] == 81.0
    assert snaps["aaaaaaaaaaa1"]["summary"]["final_percent"] == 81.0
    assert snaps["aaaaaaaaaaa1"]["request"] == {"repo_path": "stats", "target_coverage": 80.0,
                                                "options": {**OPTIONS, "write_summary": True}}
    assert snaps["aaaaaaaaaaa1"]["created_at"] == 1000 and snaps["aaaaaaaaaaa1"]["event_count"] == 4
    assert snaps["aaaaaaaaaaa1"]["writing_summary"] is False
    # no report.json: the summary and percent come from the events
    assert snaps["aaaaaaaaaaa2"]["status"] == "cancelled" and snaps["aaaaaaaaaaa2"]["summary"]["final_percent"] == 55.5
    assert snaps["aaaaaaaaaaa3"]["status"] == "failed" and snaps["aaaaaaaaaaa3"]["summary"] is None
    assert snaps["aaaaaaaaaaa3"]["percent"] == 55.5
    assert snaps["aaaaaaaaaaa4"]["status"] == "cancelled"
    assert snaps["aaaaaaaaaaa5"]["status"] == "interrupted" and snaps["aaaaaaaaaaa5"]["percent"] == 55.5
    assert m.running() is None


def test_an_interrupted_folder_is_not_modified(tmp_path, out):
    folder = write_run(out, "bbbbbbbbbbb1", run_events(), tail='{"seq": 3, "ts": 1')
    before = {p.name: p.read_bytes() for p in folder.iterdir()}
    m = manager_for(tmp_path)
    assert m.get("bbbbbbbbbbb1").status is JobStatus.INTERRUPTED
    assert {p.name: p.read_bytes() for p in folder.iterdir()} == before


def frames_of(body: str) -> list[dict]:
    return [json.loads(line[len("data: "):]) for line in body.splitlines() if line.startswith("data: ")]


def test_a_finished_run_whose_file_lacks_its_terminal_event_is_not_interrupted(tmp_path, out):
    """report.json holds the result: the app stopped after the run, e.g. while its summary was written."""
    folder = write_run(out, "aaaaaaaaaaa1", run_events(("llm_request", {"role": "summarizer"})), report=summary_data())
    write_run(out, "aaaaaaaaaaa2", run_events(), report=summary_data("cancelled", 55.5), ts=2000)
    write_run(out, "aaaaaaaaaaa3", run_events(), report={"not": "a summary"}, ts=3000)
    before = (folder / "events.jsonl").read_bytes()
    m = manager_for(tmp_path)
    assert [m.get(f"aaaaaaaaaaa{i}").status.value for i in (1, 2, 3)] == ["completed", "cancelled", "interrupted"]
    assert m.get("aaaaaaaaaaa1").snapshot()["event_count"] == 5  # 4 saved + the replayed job_completed
    assert (folder / "events.jsonl").read_bytes() == before


async def test_the_missing_terminal_event_is_replayed_and_write_again_saves_it(tmp_path, out):
    folder = write_run(out, "aaaaaaaaaaa1", run_events(("llm_request", {"role": "summarizer"})), report=summary_data())
    m = manager_for(tmp_path)
    async with client_for(m) as client:
        frames = frames_of((await client.get("/api/jobs/aaaaaaaaaaa1/events")).text)
        assert [f["seq"] for f in frames] == list(range(5))
        assert frames[-1]["type"] == "job_completed" and frames[-1]["data"]["final_percent"] == 80.0
        assert (await client.post("/api/jobs/aaaaaaaaaaa1/summary")).status_code == 202
        await m.get("aaaaaaaaaaa1").summary_task
        frames = frames_of((await client.get("/api/jobs/aaaaaaaaaaa1/events")).text)
    saved = [json.loads(line)["type"] for line in (folder / "events.jsonl").read_text("utf-8").splitlines()]
    assert saved[-4:] == ["llm_request", "job_completed", "llm_request", "summary_generated"]
    assert [f["type"] for f in frames] == saved  # the tail is in the file now, not replayed twice


@pytest.mark.parametrize("name", ["run_e2de1ca387cb", "run_fc080d7fc500"])
@pytest.mark.parametrize("cut", [False, True])
def test_real_runs_load_as_completed(tmp_path, out, name, cut):
    """Copies of real ./output runs (trimmed events). cut: the file stops before job_completed, as run_job wrote it."""
    folder = out / name.removeprefix("run_")
    folder.mkdir()
    lines = (FIXTURES / name / "events.jsonl").read_text("utf-8").splitlines(keepends=True)
    if cut:
        lines = lines[:[json.loads(line)["type"] for line in lines].index("job_completed")]
    (folder / "events.jsonl").write_text("".join(lines), encoding="utf-8")
    shutil.copyfile(FIXTURES / name / "report.json", folder / "report.json")
    report = json.loads((folder / "report.json").read_text("utf-8"))
    job = manager_for(tmp_path).get(folder.name)
    assert job.status is JobStatus.COMPLETED and job.percent == report["final_percent"]
    assert job.summary is not None and job.summary.stop_reason.value == report["stop_reason"]


def test_a_last_line_cut_inside_a_multibyte_character_is_ignored(tmp_path, out):
    folder = write_run(out, "aaaaaaaaaaa1", run_events(("job_completed", summary_data())))
    cut = json.dumps({"seq": 4, "ts": 1, "type": "log", "data": {"m": "a — b"}}, ensure_ascii=False).encode()
    with (folder / "events.jsonl").open("ab") as f:
        f.write(cut[:cut.index("—".encode()) + 1])  # the first byte of the 3-byte dash
    job = manager_for(tmp_path).get("aaaaaaaaaaa1")
    assert job.status is JobStatus.COMPLETED and job.snapshot()["event_count"] == 4


def test_a_truncated_last_line_is_ignored(tmp_path, out):
    write_run(out, "ccccccccccc1", run_events(("job_completed", summary_data())), tail='{"seq": 4, "ts": 12')
    job = manager_for(tmp_path).get("ccccccccccc1")
    assert job.status is JobStatus.COMPLETED and job.snapshot()["event_count"] == 4


def test_junk_is_skipped_and_logged(tmp_path, out, caplog):
    write_run(out, "ddddddddddd1", run_events(("job_completed", summary_data())))
    (out / ".usage.json").write_text("{}")
    (out / ".gitkeep").write_text("")
    (out / "not-a-job").mkdir()
    (out / "not-a-job" / "events.jsonl").write_text("")
    (out / "eeeeeeeeeee1").mkdir()  # no events.jsonl
    (out / "eeeeeeeeeee2").mkdir()
    (out / "eeeeeeeeeee2" / "events.jsonl").write_text("not json\n")
    (out / "eeeeeeeeeee3").mkdir()
    (out / "eeeeeeeeeee3" / "events.jsonl").write_text(json.dumps(
        {"seq": 0, "ts": 1, "type": "job_started", "data": {"repo_path": ""}}) + "\n")  # invalid request
    with caplog.at_level(logging.DEBUG, logger="app.saved_runs"):
        m = manager_for(tmp_path)
    assert [j.id for j in m.list()] == ["ddddddddddd1"]
    skipped = [r.getMessage() for r in caplog.records if "skipped" in r.getMessage()]
    for name in ("not-a-job", "eeeeeeeeeee1", "eeeeeeeeeee2", "eeeeeeeeeee3", ".usage.json"):
        assert sum(name in s for s in skipped) == 1, name


def test_a_missing_output_dir_loads_nothing(tmp_path):
    assert manager_for(tmp_path).list() == []


def test_list_is_newest_first_and_capped(tmp_path, out):
    for i in range(5):
        write_run(out, f"fffffffffff{i}", run_events(("job_completed", summary_data())), ts=1000 + 100 * i)
    m = manager_for(tmp_path, history_max_runs=3)
    assert [j.id for j in m.list()] == ["fffffffffff4", "fffffffffff3", "fffffffffff2"]
    assert len(load_runs(out, 10)) == 5


async def test_the_events_endpoint_replays_from_disk_and_ends(tmp_path, out):
    write_run(out, "aaaaaaaaaaa1", run_events(("job_completed", summary_data())), tail='{"seq"')
    write_run(out, "aaaaaaaaaaa2", run_events(), ts=2000)
    m = manager_for(tmp_path)
    assert m.get("aaaaaaaaaaa1").events == []  # held on disk, not in memory
    async with client_for(m) as client:
        for job_id, n, last in (("aaaaaaaaaaa1", 4, "job_completed"), ("aaaaaaaaaaa2", 3, "candidate_accepted")):
            body = (await client.get(f"/api/jobs/{job_id}/events")).text
            frames = [json.loads(line[len("data: "):]) for line in body.splitlines() if line.startswith("data: ")]
            assert [f["seq"] for f in frames] == list(range(n)) and frames[-1]["type"] == last
            assert (await client.get(f"/api/jobs/{job_id}")).json()["event_count"] == n
        listed = (await client.get("/api/jobs")).json()
        assert [j["id"] for j in listed] == ["aaaaaaaaaaa2", "aaaaaaaaaaa1"]
        assert [j["status"] for j in listed] == ["interrupted", "completed"]


async def test_cancel_on_a_saved_run_is_409(tmp_path, out):
    write_run(out, "aaaaaaaaaaa1", run_events())
    async with client_for(manager_for(tmp_path)) as client:
        r = await client.post("/api/jobs/aaaaaaaaaaa1/cancel")
    assert r.status_code == 409 and r.json()["error"]["code"] == "job_not_running"


async def test_saved_test_files_are_served_from_output(tmp_path, out):
    folder = write_run(out, "aaaaaaaaaaa1", run_events(("job_completed", summary_data())))
    (folder / "tests").mkdir()
    (folder / "tests" / "mean_test.go").write_text("package stats\n")
    async with client_for(manager_for(tmp_path)) as client:
        assert (await client.get("/api/jobs/aaaaaaaaaaa1/files/mean_test.go")).text == "package stats\n"
        assert (await client.get("/api/jobs/aaaaaaaaaaa1/files/other_test.go")).status_code == 404


async def test_saved_file_paths_cannot_leave_the_tests_folder(tmp_path, out):
    """A saved run's file list comes from disk: entries that point elsewhere are refused."""
    folder = write_run(out, "aaaaaaaaaaa1", run_events(
        ("candidate_accepted", {"index": 1, "file": "x.go", "test_file": "../events.jsonl", "percent": 60.0}),
        ("candidate_accepted", {"index": 1, "file": "x.go", "test_file": "../x_test.go", "percent": 60.0}),
        ("candidate_accepted", {"index": 1, "file": "y.go", "test_file": "link_test.go", "percent": 60.0}),
        ("candidate_accepted", {"index": 1, "file": "z.go", "test_file": "big_test.go", "percent": 60.0}),
        ("job_completed", summary_data())))
    (folder / "tests").mkdir()
    (folder / "x_test.go").write_text("package outside\n")
    (folder / "tests" / "big_test.go").write_text("x" * (1024 * 1024 + 1))
    try:
        (folder / "tests" / "link_test.go").symlink_to(folder / "x_test.go")
        linked = True
    except OSError:  # no symlink privilege (Windows without developer mode)
        linked = False
    async with client_for(manager_for(tmp_path)) as client:
        for path in ("../events.jsonl", "%2e%2e%2fevents.jsonl", "..%2Fx_test.go", "../x_test.go", "big_test.go",
                     f"{(folder / 'x_test.go').as_posix()}"):
            r = await client.get(f"/api/jobs/aaaaaaaaaaa1/files/{path}")
            assert r.status_code == 404 and "error" in r.json() and "package outside" not in r.text, path
        if linked:
            assert (await client.get("/api/jobs/aaaaaaaaaaa1/files/link_test.go")).status_code == 404


async def test_interrupted_runs_never_block_a_new_run(tmp_path, out, monkeypatch):
    write_run(out, "aaaaaaaaaaa1", run_events())
    ids = iter(["aaaaaaaaaaa1", "aaaaaaaaaaa1", "aaaaaaaaaaa9"])  # the first two collide with the saved run
    monkeypatch.setattr(uuid, "uuid4", lambda: type("U", (), {"hex": next(ids) + "0" * 20})())
    (tmp_path / "repos" / "stats").mkdir(parents=True)
    (tmp_path / "repos" / "stats" / "go.mod").write_text("module m\n")

    async def runner(job, emit, cancel):
        from tests.test_api import summary
        return summary()

    m = JobManager(settings_for(tmp_path), runner=runner, llm_factory=fake_llm)
    m.load_history()
    async with client_for(m) as client:
        r = await client.post("/api/jobs", json={"repo_path": "stats", "options": {"write_summary": False}})
    assert r.status_code == 201 and r.json()["job_id"] == "aaaaaaaaaaa9"
    await m.get("aaaaaaaaaaa9").task
    assert m.get("aaaaaaaaaaa1").status is JobStatus.INTERRUPTED


async def test_write_again_on_a_saved_run(tmp_path, out):
    folder = out / "fc080d7fc500"
    folder.mkdir()
    shutil.copyfile(REAL_RUN / "events.jsonl", folder / "events.jsonl")
    shutil.copyfile(REAL_RUN / "report.json", folder / "report.json")
    m = manager_for(tmp_path)
    job = m.get("fc080d7fc500")
    assert job.snapshot()["ai_summary"] == "generated" and job.summary_tokens.total == 3515
    async with client_for(m) as client:
        r = await client.post("/api/jobs/fc080d7fc500/summary")
        assert r.status_code == 202 and r.json()["writing_summary"] is True
        body = (await client.get("/api/jobs/fc080d7fc500/events")).text
    await job.summary_task
    frames = [json.loads(line[len("data: "):]) for line in body.splitlines() if line.startswith("data: ")]
    assert [f["seq"] for f in frames] == list(range(72)) and frames[-1]["type"] == "summary_generated"
    saved = [json.loads(line) for line in (folder / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(saved) == 72 and [e["seq"] for e in saved] == list(range(72))
    assert saved[-1]["type"] == "summary_generated"
    report = json.loads((folder / "report.json").read_text(encoding="utf-8"))
    assert report["ai_summary"]["business"]["headline"] == "Coverage rose from 0% to 80%."
    assert (folder / "SUMMARY.md").exists()
    # back on disk afterwards
    assert job.events == [] and job.snapshot()["event_count"] == 72 and not job.writing_summary


async def test_write_again_needs_a_report(tmp_path, out):
    write_run(out, "aaaaaaaaaaa1", run_events())  # interrupted
    write_run(out, "aaaaaaaaaaa2", run_events(("job_failed", {"reason": "x", "message": "x", "output": ""})))
    folder = write_run(out, "aaaaaaaaaaa3", run_events(("job_completed", summary_data())))
    m = manager_for(tmp_path)
    (folder / "events.jsonl").unlink()  # deleted after startup: the facts cannot be built any more
    async with client_for(m) as client:
        r1 = await client.post("/api/jobs/aaaaaaaaaaa1/summary")
        r2 = await client.post("/api/jobs/aaaaaaaaaaa2/summary")
        r3 = await client.post("/api/jobs/aaaaaaaaaaa3/summary")
    assert r1.status_code == 409 and r1.json()["error"]["code"] == "no_report"
    assert "stopped before" in r1.json()["error"]["message"]
    assert r2.status_code == 409 and r2.json()["error"]["code"] == "no_report"
    assert r3.status_code == 409 and r3.json()["error"]["code"] == "run_files_unreadable"
    assert "./output/aaaaaaaaaaa3" in r3.json()["error"]["message"]
    assert m.running() is None and m.get("aaaaaaaaaaa3").finished


async def test_startup_reloads_a_real_run(tmp_path, out):
    """The whole app on an output dir holding a copy of a real run: listed, opened and replayed after startup."""
    folder = out / "fc080d7fc500"
    shutil.copytree(REAL_RUN, folder, ignore=shutil.ignore_patterns("ai_summary.json"))
    settings = settings_for(tmp_path)
    app = create_app(settings, JobManager(settings, llm_factory=fake_llm))
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            [listed] = (await client.get("/api/jobs")).json()
            assert listed["id"] == "fc080d7fc500" and listed["status"] == "completed"
            assert listed["percent"] == 83.33 and listed["request"]["repo_path"] == "semver"
            assert listed["summary"]["test_files"] == ["collection_test.go", "constraints_test.go", "version_test.go"]
            body = (await client.get("/api/jobs/fc080d7fc500/events")).text
            assert body.count("data: ") == 70 and "summary_generated" in body
            f = await client.get("/api/jobs/fc080d7fc500/files/collection_test.go")
            assert f.status_code == 200 and f.text.startswith("package semver")
