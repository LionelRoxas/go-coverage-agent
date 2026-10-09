# AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
import httpx
import pytest

from app.config import Settings
from app.jobs import JobManager
from app.main import create_app
from app.repos import RepoInfo
from app.models import StopReason, Summary, TokenUsage


def summary():
    return Summary(stop_reason=StopReason.TARGET_REACHED, message="m", target=80, baseline_percent=0,
                   final_percent=80, iterations=[], test_files=["mean_test.go"], tests_added=[], suspected_bugs=[],
                   per_file=[], tokens=TokenUsage(), duration_s=0.1)


@pytest.fixture
async def env(tmp_path):
    repos = tmp_path / "repos"
    (repos / "stats").mkdir(parents=True)
    (repos / "stats" / "go.mod").write_text("module github.com/montanaflynn/stats\n\ngo 1.17\n")
    work = tmp_path / "work"
    settings = Settings(groq_api_key="k", repos_dir=repos, work_dir=work, output_dir=tmp_path / "out")

    async def runner(job, emit, cancel):
        test_file = work / job.id / "repo" / "mean_test.go"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("package stats\n")
        await emit("candidate_accepted", {"index": 1, "file": "mean.go", "test_file": "mean_test.go",
                                          "tests": ["TestMean"], "percent": 80.0, "gain": 80.0})
        return summary()

    manager = JobManager(settings, runner=runner)
    app = create_app(settings, manager)
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
    yield client, manager
    await client.aclose()


def make_env(tmp_path, runner, **overrides):
    repos = tmp_path / "repos"
    (repos / "stats").mkdir(parents=True)
    (repos / "stats" / "go.mod").write_text("module m\n")
    kw = dict(groq_api_key="k", repos_dir=repos, work_dir=tmp_path / "work", output_dir=tmp_path / "out")
    kw.update(overrides)
    settings = Settings(**kw)
    manager = JobManager(settings, runner=runner)
    app = create_app(settings, manager)
    return app, manager


def client_for(app, **kw):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app, **kw), base_url="http://test")


async def test_health(env):
    client, _ = env
    body = (await client.get("/api/health")).json()
    assert body["llm_configured"] is True and body["model"] == "openai/gpt-oss-120b"
    assert "tokens_left_today" in body


async def test_repos_listing(env):
    client, _ = env
    assert (await client.get("/api/repos")).json()[0]["path"] == "stats"


async def test_job_lifecycle_events_and_files(env):
    client, manager = env
    r = await client.post("/api/jobs", json={"repo_path": "stats", "target_coverage": 80})
    assert r.status_code == 201
    job_id = r.json()["job_id"]
    await manager.get(job_id).task

    snap = (await client.get(f"/api/jobs/{job_id}")).json()
    assert snap["status"] == "completed" and snap["summary"]["final_percent"] == 80

    events = (await client.get(f"/api/jobs/{job_id}/events")).text
    assert events.count("data: ") == 3 and '"type":"job_completed"' in events.replace(" ", "")

    f = await client.get(f"/api/jobs/{job_id}/files/mean_test.go")
    assert f.status_code == 200 and f.text == "package stats\n"
    assert (await client.get(f"/api/jobs/{job_id}/files/..%2F..%2Fetc%2Fpasswd")).status_code == 404


async def test_errors_use_error_envelope(env):
    client, _ = env
    r = await client.post("/api/jobs", json={"repo_path": "/Users/me/code/stats"})
    assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_repo"
    assert "./repos" in r.json()["error"]["message"]
    r = await client.post("/api/jobs", json={"repo_path": "stats", "target_coverage": 500})
    assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_request"
    assert (await client.get("/api/jobs/nope")).status_code == 404


async def noop_runner(job, emit, cancel):
    return summary()


async def test_conflict_cancel_and_listing(tmp_path):
    async def slow(job, emit, cancel):
        await cancel.wait()
        return summary()

    app, manager = make_env(tmp_path, slow)
    async with client_for(app) as client:
        job_id = (await client.post("/api/jobs", json={"repo_path": "stats"})).json()["job_id"]
        r = await client.post("/api/jobs", json={"repo_path": "stats"})
        assert r.status_code == 409 and r.json()["error"]["code"] == "job_running"
        assert [j["id"] for j in (await client.get("/api/jobs")).json()] == [job_id]
        r = await client.post(f"/api/jobs/{job_id}/cancel")
        assert r.status_code == 200 and r.json()["id"] == job_id
        await manager.get(job_id).task
        assert (await client.post("/api/jobs/nope/cancel")).status_code == 404


async def test_budget_low_is_429(tmp_path):
    app, manager = make_env(tmp_path, noop_runner)
    manager.ledger.add(manager.settings.daily_token_budget)
    async with client_for(app) as client:
        r = await client.post("/api/jobs", json={"repo_path": "stats"})
        assert r.status_code == 429 and r.json()["error"]["code"] == "daily_budget_low"


async def test_llm_not_configured_is_400(tmp_path):
    app, _ = make_env(tmp_path, noop_runner, groq_api_key="")
    async with client_for(app) as client:
        r = await client.post("/api/jobs", json={"repo_path": "stats"})
        assert r.status_code == 400 and r.json()["error"]["code"] == "llm_not_configured"


async def test_sample_clone_failure_is_502(env, monkeypatch):
    client, _ = env

    async def boom(settings):
        raise RuntimeError("git clone failed: nope")

    monkeypatch.setattr("app.api.clone_sample", boom)
    r = await client.post("/api/repos/sample")
    assert r.status_code == 502 and r.json()["error"]["code"] == "clone_failed"


async def test_unknown_route_and_wrong_method_use_envelope(env):
    client, _ = env
    r = await client.get("/api/nothing")
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"
    r = await client.delete("/api/health")
    assert r.status_code == 405 and r.json()["error"]["code"] == "method_not_allowed"
    assert "GET" in r.headers.get("allow", "")


async def test_unaccepted_existing_file_is_404(env):
    client, manager = env
    job_id = (await client.post("/api/jobs", json={"repo_path": "stats"})).json()["job_id"]
    await manager.get(job_id).task
    extra = manager.settings.work_dir / job_id / "repo" / "secret.go"
    extra.write_text("package stats\n")
    assert extra.is_file()
    r = await client.get(f"/api/jobs/{job_id}/files/secret.go")
    assert r.status_code == 404 and r.json()["error"]["code"] == "file_not_found"


async def test_unhandled_exception_is_500_envelope(tmp_path):
    app, manager = make_env(tmp_path, noop_runner)

    def explode():
        raise ValueError("secret detail")

    manager.list = explode
    async with client_for(app, raise_app_exceptions=False) as client:
        r = await client.get("/api/jobs")
    assert r.status_code == 500
    assert r.json() == {"error": {"code": "internal_error", "message": "Internal server error"}}


async def test_cross_origin_post_is_blocked(env, monkeypatch):
    client, _ = env
    calls = []

    async def fake_clone(settings):
        calls.append(1)
        return RepoInfo(path="stats", module="m", go_files=0, test_files=0)

    monkeypatch.setattr("app.api.clone_sample", fake_clone)
    r = await client.post("/api/repos/sample", headers={"Origin": "https://evil.example"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "forbidden_origin" and not calls
    r = await client.post("/api/repos/sample", headers={"Origin": "http://localhost:3000"})
    assert r.status_code == 200 and calls == [1]
