# AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
import asyncio

import httpx
import pytest

from app.config import Settings
from app.jobs import JobManager
from app.main import create_app
from app.models import StopReason, Summary, TokenUsage


def summary():
    return Summary(stop_reason=StopReason.TARGET_REACHED, message="m", target=80, baseline_percent=0,
                   final_percent=80, iterations=[], test_files=["mean_test.go"], tests_added=[], suspected_bugs=[],
                   per_file=[], tokens=TokenUsage(), duration_s=0.1)


@pytest.fixture
def env(tmp_path):
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
    return client, manager


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
