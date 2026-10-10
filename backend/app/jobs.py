# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
"""In-memory job registry (one running job at a time) with replayable event streams. Runs saved in OUTPUT_DIR are
reloaded on startup (app.saved_runs); their events stay on disk until a client asks for them."""
from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any, AsyncIterator, Awaitable, Callable, Iterator

from pydantic import ValidationError

from app.agents.llm_agents import Agents
from app.config import Settings
from app.engine.run import JobFailed, run_job
from app.llm.client import (Emit, GroqLLM, LLMBudgetExhausted, LLMCancelled, LLMClient, LLMError, LLMFatal,
                            LLMTimeout)
from app.llm.limits import RateLimiter, UsageLedger
from app.models import Event, JobRequest, JobStatus, StopReason, Summary, TokenUsage
from app.summary.facts import build_facts, cost_usd
from app.summary.grounding import ground
from app.summary.report import save, to_markdown

log = logging.getLogger(__name__)


class JobConflict(Exception):
    def __init__(self, job_id: str):
        super().__init__(job_id)
        self.job_id = job_id


class JobRejected(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def iter_events(path: Path) -> Iterator[Event]:
    """The events of an events.jsonl, skipping a line that does not parse (a truncated last line: a partial write,
    possibly cut inside a multi-byte character, which `errors="replace"` turns into a line that fails validation)."""
    with path.open(encoding="utf-8", errors="replace") as f:
        for n, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                yield Event.model_validate_json(line)
            except ValidationError:
                log.debug("%s: line %d is not a complete event; ignored", path, n)


def read_events(path: Path) -> list[Event]:
    return list(iter_events(path))


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
        self.summary_task: asyncio.Task[None] | None = None  # a summary written again on request
        self.summary_tokens = TokenUsage()  # every summary call so far; counts toward max_llm_tokens
        self.summary_cancel = asyncio.Event()  # Cancel while the summary is written (a new one per summary)
        self.ai_summary: str | None = None  # "generated" / "failed": the last summary event, if any
        self._subscribers: list[asyncio.Queue[Event | None]] = []
        # A run reloaded from OUTPUT_DIR: its events.jsonl, and the count and accepted test files read from it at
        # startup. Its events are loaded into `events` only while its summary is written again.
        self.log_path: Path | None = None
        self.saved_event_count = 0
        self.saved_test_files: list[str] = []
        # Replayed after the file, never written: the job_completed / job_cancelled of a saved run whose file lacks it
        # (the app stopped while its summary was written) but whose report.json holds the Summary.
        self.saved_tail: list[Event] = []

    @property
    def on_disk(self) -> bool:
        """A saved run whose events are not in memory."""
        return self.log_path is not None and not self.events

    async def emit(self, type_: str, data: dict[str, Any]) -> None:
        event = Event(seq=self.events[-1].seq + 1 if self.events else 0, ts=time.time(), type=type_, data=data)
        self.events.append(event)
        if type_ == "baseline_measured":
            self.percent = data["report"]["percent"]
        elif type_ == "candidate_accepted":
            self.percent = data["percent"]
        elif type_ in ("summary_generated", "summary_failed"):
            self.ai_summary = "generated" if type_ == "summary_generated" else "failed"
        for q in self._subscribers:
            q.put_nowait(event)

    def close(self) -> None:
        self.finished = True
        for q in self._subscribers:
            q.put_nowait(None)

    async def stream(self) -> AsyncIterator[Event]:
        if self.on_disk:  # a saved run: replay its file, then end
            assert self.log_path is not None
            try:
                events = await asyncio.to_thread(read_events, self.log_path)
            except (OSError, ValueError):
                log.warning("could not read %s", self.log_path, exc_info=True)
                return
            for event in [*events, *self.saved_tail]:
                yield event
            return
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
        if self.on_disk:
            return self.saved_test_files
        return sorted({e.data["test_file"] for e in self.events if e.type == "candidate_accepted"})

    def snapshot(self) -> dict[str, Any]:
        return {"id": self.id, "status": self.status.value, "request": self.request.model_dump(mode="json"),
                "created_at": self.created_at, "percent": self.percent,
                "event_count": self.saved_event_count if self.on_disk else len(self.events),
                "summary": self.summary.model_dump(mode="json") if self.summary else None,
                "writing_summary": self.writing_summary, "ai_summary": self.ai_summary}

    @property
    def writing_summary(self) -> bool:
        """The run has ended but its stream is still open: the summary is being written."""
        return self.status is not JobStatus.RUNNING and not self.finished


Runner = Callable[[Job, Emit, asyncio.Event], Awaitable[Summary]]
LLMFactory = Callable[[Emit, asyncio.Event], LLMClient]  # (emit, cancel) -> the summary call's client


class SummaryFailed(Exception):
    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason, self.message = reason, message


def _failure(e: LLMError) -> tuple[str, str]:
    """summary_failed reason and message for an LLM error."""
    if isinstance(e, LLMCancelled):
        return "cancelled", "Cancelled while the summary was being written."
    reason = ("budget_exhausted" if isinstance(e, LLMBudgetExhausted) else "timeout" if isinstance(e, LLMTimeout)
              else "llm_auth" if isinstance(e, LLMFatal) else "llm_error")
    return reason, str(e)


class JobManager:
    def __init__(self, settings: Settings, runner: Runner | None = None, llm_factory: LLMFactory | None = None):
        self.settings = settings
        self.ledger = UsageLedger(settings.output_dir / ".usage.json", settings.daily_token_budget)
        self.limiter = RateLimiter()
        self.jobs: dict[str, Job] = {}
        self._runner = runner or self._default_runner
        # The summary call: same pacing and daily ledger, with its own cancel event (a cancelled job's is set).
        self._llm_factory = llm_factory or (
            lambda emit, cancel: GroqLLM(settings, self.ledger, self.limiter, emit=emit, cancel=cancel))

    async def _default_runner(self, job: Job, emit: Emit, cancel: asyncio.Event) -> Summary:
        llm = GroqLLM(self.settings, self.ledger, self.limiter, emit=emit, cancel=cancel)
        return await run_job(job.id, job.request, self.settings, llm, emit, cancel, lambda: job.events)

    @property
    def summary_deadline_s(self) -> float:
        """The whole summary call, retries and waits included: one timed-out request and its retry, plus 30 s."""
        return 2 * self.settings.groq_timeout_s + 30

    def running(self) -> Job | None:
        """The busy job: running, or writing its summary. One job uses Groq at a time."""
        return next((j for j in self.jobs.values() if j.status is JobStatus.RUNNING or not j.finished), None)

    def load_history(self) -> None:
        """Startup: add the most recent HISTORY_MAX_RUNS runs saved in OUTPUT_DIR (never raises)."""
        from app.saved_runs import load_runs  # it builds Jobs, so it imports this module
        for job in load_runs(self.settings.output_dir, self.settings.history_max_runs):
            self.jobs.setdefault(job.id, job)

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
        while (job_id := uuid.uuid4().hex[:12]) in self.jobs or (self.settings.output_dir / job_id).exists():
            pass  # never reuse the id of a loaded or saved run
        job = Job(job_id, request)
        self.jobs[job.id] = job
        job.task = asyncio.create_task(self._run(job))
        return job

    def cancel(self, job_id: str) -> Job | None:
        job = self.jobs.get(job_id)
        if job is not None and job.log_path is not None and job.finished:
            raise JobRejected(409, "job_not_running", "This run is not running; it was reloaded from ./output.")
        if job is not None and job.status is JobStatus.RUNNING:
            job.cancel.set()
        elif job is not None and job.writing_summary:
            job.summary_cancel.set()  # the run keeps its result; the summary fails as "cancelled"
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
            # cancelled during setup: no Summary exists, so the event stays job_failed (reason "cancelled")
            job.status = JobStatus.CANCELLED if e.reason == "cancelled" else JobStatus.FAILED
            await job.emit("job_failed", {"reason": e.reason, "message": e.message, "output": e.output[:8000]})
        except Exception as e:  # noqa: BLE001 — surface anything unexpected to the UI
            log.exception("job %s crashed", job.id)
            job.status = JobStatus.FAILED
            await job.emit("job_failed", {"reason": "internal_error", "message": str(e), "output": ""})
        else:
            # The terminal event is on disk before the summary call, which can take minutes: a restart meanwhile
            # reloads the run as completed / cancelled, not interrupted.
            self._save_events(job)
            # After job_completed / job_cancelled, so the result shows at once; the stream stays open meanwhile.
            # Setup failures have no Summary and get no summary.
            if job.request.options.write_summary:
                job.summary_cancel = asyncio.Event()  # before the summary starts, so no Cancel is lost
                await self._write_summary(job)
        finally:
            try:
                self._save_events(job)
            finally:
                job.close()

    def write_summary_again(self, job_id: str, saved_events: list[Event] | None = None) -> Job:
        """POST /api/jobs/{id}/summary: (re)write the summary of a finished job; its events go to the job's stream,
        which stays open until the summary is written or has failed."""
        job = self.jobs[job_id]
        if job.status is JobStatus.RUNNING or not job.finished:
            raise JobRejected(409, "job_running", "This run is still running or writing its summary.")
        if (busy := self.running()) is not None:
            raise JobRejected(409, "job_running", f"Run {busy.id} is still running; write the summary when it ends.")
        if job.status is JobStatus.INTERRUPTED:
            raise JobRejected(409, "no_report",
                              "This run stopped before it finished, so there is no report to summarize.")
        if job.summary is None:
            raise JobRejected(409, "no_report",
                              "This run ended before its baseline was measured, so there is nothing to summarize.")
        if not self.settings.llm_configured:
            raise JobRejected(400, "llm_not_configured", "Set GROQ_API_KEY in .env and restart the app.")
        if job.on_disk:
            job.events = saved_events if saved_events is not None else self.saved_events(job_id)
        job.finished = False
        job.summary_cancel = asyncio.Event()  # now, not in the task: a Cancel before it starts must count
        job.summary_task = asyncio.create_task(self._summary_again(job))
        return job

    def saved_events(self, job_id: str) -> list[Event] | None:
        """A saved run's events (with its replayed tail), to hold in memory while its summary is written again; None
        for a job whose events are in memory. 409 when its files no longer give the facts the summary needs. Blocking
        file I/O: the API calls it in a thread."""
        job = self.jobs[job_id]
        if not job.on_disk or job.summary is None:
            return None
        assert job.log_path is not None
        unreadable = JobRejected(409, "run_files_unreadable", f"This run's saved files in ./output/{job.id} can't be "
                                 "read any more, so its summary can't be written again.")
        try:
            events = [*read_events(job.log_path), *job.saved_tail]
            build_facts(job.summary, events, repo=job.request.repo_path, model="", job_id=job.id)
        except Exception as e:  # noqa: BLE001 — a missing file, or events older code can't use
            log.info("cannot write the summary of saved run %s again", job.id, exc_info=True)
            raise unreadable from e
        if not events:
            raise unreadable
        return events

    async def _summary_again(self, job: Job) -> None:
        try:
            await self._write_summary(job)
        finally:
            try:
                self._save_events(job)
            finally:
                if job.log_path is not None:  # a saved run: back to disk, keeping the counts its snapshot shows
                    job.saved_event_count, job.saved_test_files = len(job.events), job.accepted_test_files()
                    job.events, job.saved_tail = [], []  # the tail is in the file now
                job.close()

    def _model(self, job: Job) -> str:
        started = next((e for e in job.events if e.type == "job_started"), None)
        return (started.data.get("model") if started else None) or self.settings.groq_model

    async def _summarize(self, job: Job) -> dict[str, Any]:
        """The summary_generated payload, or SummaryFailed."""
        s, summary = self.settings, job.summary
        assert summary is not None
        if not s.llm_configured:
            raise SummaryFailed("llm_not_configured", "Set GROQ_API_KEY in .env and restart the app.")
        if summary.tokens.total + job.summary_tokens.total >= job.request.options.max_llm_tokens:
            raise SummaryFailed("budget_exhausted", "This run's token budget (max_llm_tokens) is used up.")
        facts = build_facts(summary, job.events, repo=job.request.repo_path, model=self._model(job), job_id=job.id,
                            price_input_per_m=s.groq_price_input_per_m, price_output_per_m=s.groq_price_output_per_m)

        async def on_request(effort: str) -> None:
            await job.emit("llm_request", {"role": "summarizer", "reasoning_effort": effort})

        if job.summary_cancel.is_set():
            raise SummaryFailed("cancelled", "Cancelled before the summary was written.")
        llm = self._llm_factory(job.emit, job.summary_cancel)
        try:
            written, usage = await asyncio.wait_for(
                Agents(llm, s.max_prompt_tokens).summarize(facts, on_request=on_request), self.summary_deadline_s)
        except TimeoutError as e:  # retries and rate-limit waits must not keep the job busy for many minutes
            raise SummaryFailed("timeout", f"The summary was not written within {self.summary_deadline_s:g} s.") from e
        except LLMError as e:
            job.summary_tokens = job.summary_tokens.add(e.spent)  # e.g. truncated answers before the failure
            raise SummaryFailed(*_failure(e)) from e
        job.summary_tokens = job.summary_tokens.add(usage)
        grounded, dropped = ground(written, facts)
        payload: dict[str, Any] = {**grounded.model_dump(mode="json"), "dropped_sentences": dropped,
                                   "tokens": {"prompt_tokens": usage.prompt_tokens,
                                              "completion_tokens": usage.completion_tokens,
                                              "total_tokens": usage.total}}
        prices = s.groq_price_input_per_m, s.groq_price_output_per_m
        call = cost_usd(usage.prompt_tokens, usage.completion_tokens, *prices)
        both = summary.tokens.add(usage)
        total = cost_usd(both.prompt_tokens, both.completion_tokens, *prices)
        if facts.cost_usd is not None and call is not None and total is not None:
            # run: the cost the text talks about; summary: this call; input/output/total: the two together
            payload["cost_usd"] = {"run": facts.cost_usd.total_usd, "summary": call.total_usd,
                                   "input": total.input_usd, "output": total.output_usd, "total": total.total_usd}
        return payload

    async def _write_summary(self, job: Job) -> None:
        """Emit summary_generated or summary_failed (never raises; the run itself has already ended) and save it
        next to the run's other files."""
        assert job.summary is not None
        out = self.settings.output_dir / job.id
        try:
            payload = await self._summarize(job)
        except Exception as e:  # noqa: BLE001
            if isinstance(e, SummaryFailed):
                reason, message = e.reason, e.message
            else:
                log.exception("the summary of job %s crashed", job.id)
                reason, message = "internal_error", str(e)
            await job.emit("summary_failed", {"reason": reason, "message": message})
            try:
                save(out, job.summary, error={"reason": reason, "message": message},
                     summary_tokens=job.summary_tokens)
            except Exception:  # noqa: BLE001
                log.warning("could not save the summary error of job %s", job.id, exc_info=True)
            return
        await job.emit("summary_generated", payload)
        generated_at, model = job.events[-1].ts, self._model(job)
        try:
            markdown = to_markdown(payload, repo=job.request.repo_path, model=model, generated_at=generated_at)
            save(out, job.summary, ai={**payload, "model": model, "generated_at": generated_at}, markdown=markdown,
                 summary_tokens=job.summary_tokens)
        except Exception:  # noqa: BLE001
            log.warning("could not save the summary of job %s", job.id, exc_info=True)

    def _save_events(self, job: Job) -> None:
        """Rewrite events.jsonl so it includes the terminal and summary events (run_job wrote it earlier)."""
        try:
            out = self.settings.output_dir / job.id
            out.mkdir(parents=True, exist_ok=True)
            tmp = out / "events.jsonl.tmp"  # replace, never truncate: a kill mid-write keeps the earlier file
            tmp.write_text("".join(e.model_dump_json() + "\n" for e in job.events), encoding="utf-8")
            os.replace(tmp, out / "events.jsonl")
        except Exception:  # noqa: BLE001 — never let artifact writing block close()
            log.warning("could not write events.jsonl for job %s", job.id, exc_info=True)
