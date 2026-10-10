# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
from __future__ import annotations

import asyncio
import logging
import shutil
from pathlib import Path
from typing import Callable

from app.config import Settings
from app.engine.orchestrator import Orchestrator
from app.engine.setup import JobFailed, Prepared, prepare
from app.llm.client import Emit, LLMClient, LLMFatal
from app.models import Event, JobRequest, Summary
from app.workspace import Workspace

log = logging.getLogger(__name__)

__all__ = ["JobFailed", "prepare", "run_job", "write_artifacts"]


def write_artifacts(dest: Path, ws: Workspace | None, summary: Summary | None, events: list[Event],
                    accepted: list[str] | None = None) -> None:
    """Without a summary (failed job) export only the accepted test files when known, else every test file."""
    dest.mkdir(parents=True, exist_ok=True)
    if ws is not None:
        if summary is not None:
            files = summary.test_files
        else:
            files = accepted if accepted is not None else ws.test_files()
        for rel in files:
            src = ws.path(rel)
            if src.exists():
                target = dest / "tests" / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, target)
    if summary is not None:
        (dest / "report.json").write_text(summary.model_dump_json(indent=2), encoding="utf-8")
    (dest / "events.jsonl").write_text("".join(e.model_dump_json() + "\n" for e in events), encoding="utf-8")


async def run_job(job_id: str, request: JobRequest, settings: Settings, llm: LLMClient, emit: Emit,
                  cancel: asyncio.Event, events: Callable[[], list[Event]]) -> Summary:
    prepared: Prepared | None = None
    summary: Summary | None = None
    try:
        prepared = await prepare(job_id, request, settings, llm, emit, cancel)
        summary = await Orchestrator(prepared.deps, request, emit, cancel,
                                     unavailable_after_s=settings.llm_unavailable_after_s).run(prepared.baseline)
        return summary
    except LLMFatal as e:
        raise JobFailed("llm_auth", str(e)) from e
    finally:
        try:
            log_events = events()
            accepted = sorted({e.data["test_file"] for e in log_events if e.type == "candidate_accepted"})
            write_artifacts(settings.output_dir / job_id, prepared.deps.ws if prepared else None, summary, log_events,
                            accepted)
        except Exception:  # never mask the job's own outcome
            log.exception("could not write artifacts for job %s", job_id)
        else:
            # The tests are exported to output/<id>/tests, which the API serves from now on; the copy is not needed.
            shutil.rmtree(settings.work_dir / job_id, ignore_errors=True)
