# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
"""In-memory job registry (one running job at a time) with replayable event streams."""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any, AsyncIterator, Awaitable, Callable

from app.config import Settings
from app.engine.run import JobFailed, run_job
from app.llm.client import Emit, GroqLLM
from app.llm.limits import RateLimiter, UsageLedger
from app.models import Event, JobRequest, JobStatus, StopReason, Summary

log = logging.getLogger(__name__)


class JobConflict(Exception):
    def __init__(self, job_id: str):
        super().__init__(job_id)
        self.job_id = job_id


class JobRejected(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


class Job:
    def __init__(self, job_id: str, request: JobRequest):
        self.id, self.request = job_id, request
        self.status = JobStatus.RUNNING
        self.created_at = time.time()
        self.events: list[Event] = []
        self.summary: Summary | None = None
        self.percent: float | None = None
        self.cancel = asyncio.Event()
        self.finished = False
        self.task: asyncio.Task[None] | None = None
        self._subscribers: list[asyncio.Queue[Event | None]] = []

    async def emit(self, type_: str, data: dict[str, Any]) -> None:
        event = Event(seq=len(self.events), ts=time.time(), type=type_, data=data)
        self.events.append(event)
        if type_ == "baseline_measured":
            self.percent = data["report"]["percent"]
        elif type_ == "candidate_accepted":
            self.percent = data["percent"]
        for q in self._subscribers:
            q.put_nowait(event)

    def close(self) -> None:
        self.finished = True
        for q in self._subscribers:
            q.put_nowait(None)

    async def stream(self) -> AsyncIterator[Event]:
        queue: asyncio.Queue[Event | None] = asyncio.Queue()
        self._subscribers.append(queue)
        done_at_subscribe = self.finished  # decide before replay: the job may finish while we yield
        try:
            last = -1
            for event in list(self.events):
                last = event.seq
                yield event
            if done_at_subscribe:
                return
            while (event := await queue.get()) is not None:
                if event.seq > last:
                    last = event.seq
                    yield event
        finally:
            self._subscribers.remove(queue)

    def accepted_test_files(self) -> list[str]:
        return sorted({e.data["test_file"] for e in self.events if e.type == "candidate_accepted"})

    def snapshot(self) -> dict[str, Any]:
        return {"id": self.id, "status": self.status.value, "request": self.request.model_dump(mode="json"),
                "created_at": self.created_at, "percent": self.percent, "event_count": len(self.events),
                "summary": self.summary.model_dump(mode="json") if self.summary else None}


Runner = Callable[[Job, Emit, asyncio.Event], Awaitable[Summary]]


class JobManager:
    def __init__(self, settings: Settings, runner: Runner | None = None):
        self.settings = settings
        self.ledger = UsageLedger(settings.output_dir / ".usage.json", settings.daily_token_budget)
        self.limiter = RateLimiter()
        self.jobs: dict[str, Job] = {}
        self._runner = runner or self._default_runner

    async def _default_runner(self, job: Job, emit: Emit, cancel: asyncio.Event) -> Summary:
        llm = GroqLLM(self.settings, self.ledger, self.limiter, emit=emit, cancel=cancel)
        return await run_job(job.id, job.request, self.settings, llm, emit, cancel, lambda: job.events)

    def running(self) -> Job | None:
        return next((j for j in self.jobs.values() if j.status is JobStatus.RUNNING), None)

    def get(self, job_id: str) -> Job | None:
        return self.jobs.get(job_id)

    def list(self) -> list[Job]:
        return sorted(self.jobs.values(), key=lambda j: j.created_at, reverse=True)

    def start(self, request: JobRequest) -> Job:
        if not self.settings.llm_configured:
            raise JobRejected(400, "llm_not_configured", "Set GROQ_API_KEY in .env and restart the app.")
        remaining = self.ledger.remaining()
        if remaining < self.settings.min_daily_tokens_to_start:
            raise JobRejected(429, "daily_budget_low",
                              f"Only ~{remaining:,} Groq tokens are left today; the budget resets at 00:00 UTC.")
        if (running := self.running()) is not None:
            raise JobConflict(running.id)
        job = Job(uuid.uuid4().hex[:12], request)
        self.jobs[job.id] = job
        job.task = asyncio.create_task(self._run(job))
        return job

    def cancel(self, job_id: str) -> Job | None:
        job = self.jobs.get(job_id)
        if job is not None and job.status is JobStatus.RUNNING:
            job.cancel.set()
        return job

    async def _run(self, job: Job) -> None:
        await job.emit("job_started", {"repo_path": job.request.repo_path,
                                       "target_coverage": job.request.target_coverage,
                                       "options": job.request.options.model_dump(mode="json"),
                                       "model": self.settings.groq_model})
        try:
            summary = await self._runner(job, job.emit, job.cancel)
            job.summary = summary
            if summary.stop_reason is StopReason.CANCELLED:
                job.status = JobStatus.CANCELLED
                await job.emit("job_cancelled", summary.model_dump(mode="json"))
            else:
                job.status = JobStatus.COMPLETED
                await job.emit("job_completed", summary.model_dump(mode="json"))
        except JobFailed as e:
            job.status = JobStatus.FAILED
            await job.emit("job_failed", {"reason": e.reason, "message": e.message, "output": e.output[:8000]})
        except Exception as e:  # noqa: BLE001 — surface anything unexpected to the UI
            log.exception("job %s crashed", job.id)
            job.status = JobStatus.FAILED
            await job.emit("job_failed", {"reason": "internal_error", "message": str(e), "output": ""})
        finally:
            # Rewrite events.jsonl here so it includes the terminal event (run_job wrote it earlier).
            try:
                out = self.settings.output_dir / job.id
                out.mkdir(parents=True, exist_ok=True)
                (out / "events.jsonl").write_text(
                    "".join(e.model_dump_json() + "\n" for e in job.events), encoding="utf-8")
            except Exception:  # noqa: BLE001 — never let artifact writing block close()
                log.warning("could not write events.jsonl for job %s", job.id, exc_info=True)
            finally:
                job.close()
