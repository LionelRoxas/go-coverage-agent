# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
from __future__ import annotations

import asyncio
import os

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse
from sse_starlette.sse import EventSourceResponse

from app.jobs import Job, JobConflict, JobManager, JobRejected
from app.models import JobRequest
from app.repos import SAMPLES, clone_sample, list_repos, list_samples
from app.uploads import UploadError, receive_upload
from app.workspace import WorkspaceError, resolve_repo

router = APIRouter(prefix="/api")


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def _manager(request: Request) -> JobManager:
    return request.app.state.manager


def _job(request: Request, job_id: str) -> Job:
    job = _manager(request).get(job_id)
    if job is None:
        raise ApiError(404, "job_not_found", f"No job with id {job_id!r}.")
    return job


@router.get("/health")
async def health(request: Request) -> dict:
    s, m = request.app.state.settings, _manager(request)
    return {"status": "ok", "go_version": request.app.state.go_version, "model": s.groq_model,
            "llm_configured": s.llm_configured, "tokens_left_today": m.ledger.remaining(),
            "min_daily_tokens_to_start": s.min_daily_tokens_to_start,
            "storage_writable": os.access(s.output_dir, os.W_OK) and os.access(s.repos_dir, os.W_OK),
            "host_repos_dir": s.host_repos_dir_display or None,
            "upload_limits": {"max_files": s.upload_max_files, "max_bytes": s.upload_max_bytes,
                              "max_file_bytes": s.upload_max_file_bytes}}


@router.get("/repos")
async def repos(request: Request) -> list[dict]:
    found = await asyncio.to_thread(list_repos, request.app.state.settings.repos_dir)
    return [r.model_dump() for r in found]


@router.get("/repos/samples")
async def samples(request: Request) -> list[dict]:
    return await asyncio.to_thread(list_samples, request.app.state.settings.repos_dir)


async def _download(request: Request, sample_id: str) -> dict:
    if sample_id not in SAMPLES:
        raise ApiError(404, "unknown_sample", f"No sample repository {sample_id!r}.")
    try:
        return (await clone_sample(request.app.state.settings, sample_id)).model_dump()
    except RuntimeError as e:
        raise ApiError(502, "clone_failed", str(e)) from e


@router.post("/repos/samples/{sample_id}")
async def download_sample(sample_id: str, request: Request) -> dict:
    return await _download(request, sample_id)


@router.post("/repos/sample")
async def sample(request: Request) -> dict:
    """Alias for the sample with id "stats"."""
    return await _download(request, "stats")


@router.post("/repos/upload")
async def upload_repo(request: Request) -> dict:
    """Multipart: one 'files' part per file (filename = path such as 'myproj/pkg/a.go') and optional 'name'."""
    try:
        return await receive_upload(request, request.app.state.settings)
    except UploadError as e:
        raise ApiError(e.status, e.code, e.message) from e


@router.post("/jobs", status_code=201)
async def create_job(body: JobRequest, request: Request) -> dict:
    try:
        resolve_repo(request.app.state.settings.repos_dir, body.repo_path)
    except WorkspaceError as e:
        raise ApiError(400, "invalid_repo", str(e)) from e
    try:
        job = _manager(request).start(body)
    except JobConflict as e:
        busy = _manager(request).get(e.job_id)
        what = "writing its summary" if busy is not None and busy.writing_summary else "running"
        raise ApiError(409, "job_running", f"Job {e.job_id} is still {what}.") from e
    except JobRejected as e:
        raise ApiError(e.status, e.code, e.message) from e
    return {"job_id": job.id}


@router.get("/jobs")
async def jobs(request: Request) -> list[dict]:
    return [j.snapshot() for j in _manager(request).list()]


@router.get("/jobs/{job_id}")
async def job(job_id: str, request: Request) -> dict:
    return _job(request, job_id).snapshot()


@router.get("/jobs/{job_id}/events")
async def events(job_id: str, request: Request) -> EventSourceResponse:
    job = _job(request, job_id)

    async def gen():
        async for event in job.stream():
            yield {"id": str(event.seq), "data": event.model_dump_json()}

    return EventSourceResponse(gen(), ping=15)


@router.post("/jobs/{job_id}/cancel")
async def cancel(job_id: str, request: Request) -> dict:
    _job(request, job_id)
    try:
        return _manager(request).cancel(job_id).snapshot()
    except JobRejected as e:
        raise ApiError(e.status, e.code, e.message) from e


@router.post("/jobs/{job_id}/summary", status_code=202)
async def write_summary(job_id: str, request: Request) -> dict:
    """Write the AI summary of a finished run (again); summary events follow on the job's event stream."""
    _job(request, job_id)
    try:
        return _manager(request).write_summary_again(job_id).snapshot()
    except JobRejected as e:
        raise ApiError(e.status, e.code, e.message) from e


@router.get("/jobs/{job_id}/files/{path:path}")
async def file(job_id: str, path: str, request: Request) -> PlainTextResponse:
    job = _job(request, job_id)
    if path not in job.accepted_test_files():
        raise ApiError(404, "file_not_found", "Not a generated test file of this job.")
    settings = request.app.state.settings
    target = settings.work_dir / job_id / "repo" / path
    if not target.is_file():  # e.g. a run reloaded after a restart: its working copy is gone, its export is not
        target = settings.output_dir / job_id / "tests" / path
    if not target.is_file():
        raise ApiError(404, "file_not_found", "File no longer exists.")
    return PlainTextResponse(target.read_text(encoding="utf-8"))
