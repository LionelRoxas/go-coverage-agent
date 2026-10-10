# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
"""Run history from OUTPUT_DIR: on startup each saved run folder (<job id>/events.jsonl) becomes a read-only Job.
Only its snapshot is kept in memory; its events are read from disk when a client opens the event stream.
Nothing on disk is changed here."""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.jobs import Job, iter_events
from app.models import Event, JobRequest, JobStatus, Summary, TokenUsage

log = logging.getLogger(__name__)

JOB_ID = re.compile(r"[0-9a-f]{12}")  # uuid4().hex[:12], as JobManager.start makes them
TERMINAL = {"job_completed": JobStatus.COMPLETED, "job_cancelled": JobStatus.CANCELLED, "job_failed": JobStatus.FAILED}
AI_SUMMARY = {"summary_generated": "generated", "summary_failed": "failed"}


class Unreadable(Exception):
    """A run folder that cannot be loaded."""


def _first_event(path: Path) -> Event:
    try:
        first = next(iter_events(path), None)
    except (OSError, UnicodeDecodeError) as e:
        raise Unreadable(f"events.jsonl cannot be read ({e})") from e
    if first is None or first.type != "job_started":
        raise Unreadable("events.jsonl does not start with job_started")
    return first


def _report(folder: Path) -> dict[str, Any] | None:
    path = folder / "report.json"
    if not path.is_file():
        return None
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        log.info("%s: report.json cannot be read (%s); using the events only", folder, e)
        return None
    return report if isinstance(report, dict) else None


def load_run(folder: Path) -> Job:
    """A Job for one saved run folder, or Unreadable."""
    path = folder / "events.jsonl"
    started = _first_event(path)
    try:
        request = JobRequest.model_validate({k: started.data[k] for k in ("repo_path", "target_coverage", "options")
                                             if k in started.data})
    except ValidationError as e:
        raise Unreadable(f"job_started does not hold a valid request ({e.errors()[0]['msg']})") from e

    terminal: Event | None = None
    count, percent, ai_summary, accepted = 0, None, None, set()
    try:
        for e in iter_events(path):
            count += 1
            if e.type in TERMINAL:
                terminal = e
            elif e.type in AI_SUMMARY:
                ai_summary = AI_SUMMARY[e.type]
            elif e.type == "baseline_measured":
                percent = e.data.get("report", {}).get("percent", percent)
            elif e.type == "candidate_accepted":
                percent = e.data.get("percent", percent)
                if "test_file" in e.data:
                    accepted.add(e.data["test_file"])
    except (OSError, UnicodeDecodeError) as e:
        raise Unreadable(f"events.jsonl cannot be read ({e})") from e

    job = Job(folder.name, request)
    job.created_at, job.finished, job.log_path = started.ts, True, path
    job.saved_event_count, job.saved_test_files = count, sorted(accepted)
    if terminal is None:
        job.status = JobStatus.INTERRUPTED
    elif terminal.type == "job_failed" and terminal.data.get("reason") == "cancelled":
        job.status = JobStatus.CANCELLED  # cancelled during setup: no Summary
    else:
        job.status = TERMINAL[terminal.type]

    report = _report(folder)
    summary_data = report if report is not None else (
        terminal.data if terminal is not None and terminal.type != "job_failed" else None)
    if summary_data is not None:
        try:
            job.summary = Summary.model_validate(summary_data)
        except ValidationError:
            log.info("%s: no valid summary in %s", folder, "report.json" if report is not None else terminal.type)
    if report is not None:
        tokens = report.get("summary_tokens") or {}
        job.summary_tokens = TokenUsage(prompt_tokens=tokens.get("prompt_tokens", 0),
                                        completion_tokens=tokens.get("completion_tokens", 0))
        if ai_summary is None:
            ai_summary = "generated" if "ai_summary" in report else "failed" if "ai_summary_error" in report else None
    job.percent = job.summary.final_percent if job.summary is not None else percent
    job.ai_summary = ai_summary
    return job


def load_runs(output_dir: Path, max_runs: int) -> list[Job]:
    """The most recent `max_runs` saved runs (by start time). Anything else in the folder is skipped with a log line;
    this never raises."""
    try:
        entries = sorted(output_dir.iterdir())
    except OSError as e:
        log.info("no run history loaded: %s cannot be listed (%s)", output_dir, e)
        return []
    found: list[tuple[float, Path]] = []
    for entry in entries:
        if not entry.is_dir() or not JOB_ID.fullmatch(entry.name):
            log.debug("run history: skipped %s (not a run folder)", entry.name)
            continue
        if not (entry / "events.jsonl").is_file():
            log.info("run history: skipped %s (no events.jsonl)", entry.name)
            continue
        try:
            found.append((_first_event(entry / "events.jsonl").ts, entry))
        except Unreadable as e:
            log.info("run history: skipped %s (%s)", entry.name, e)
    found.sort(key=lambda x: x[0], reverse=True)
    jobs: list[Job] = []
    for _, folder in found[:max_runs]:
        try:
            jobs.append(load_run(folder))
        except Unreadable as e:
            log.info("run history: skipped %s (%s)", folder.name, e)
        except Exception:  # noqa: BLE001 — one bad folder must never stop the app from starting
            log.info("run history: skipped %s (unexpected error)", folder.name, exc_info=True)
    if len(found) > max_runs:
        log.info("run history: loaded the %d most recent of %d runs (HISTORY_MAX_RUNS)", max_runs, len(found))
    return jobs
