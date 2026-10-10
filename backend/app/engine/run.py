# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
from __future__ import annotations

import asyncio
import logging
import os
import shutil
from pathlib import Path
from typing import Any, Callable

from app.config import Settings
from app.engine.orchestrator import Orchestrator
from app.engine.setup import JobFailed, Prepared, prepare
from app.llm.client import Emit, LLMClient, LLMFatal
from app.models import Event, JobRequest, Summary
from app.summary.facts import drop_refuted_bugs
from app.workspace import Workspace

log = logging.getLogger(__name__)

__all__ = ["JobFailed", "export_test", "prepare", "run_job", "write_artifacts"]


def export_test(dest: Path, ws: Workspace, rel: str) -> None:
    """Copy one test file of the working copy to dest/tests, replacing an earlier copy in one step (temp file +
    rename): a kill mid-copy leaves the earlier accepted version, never a truncated file."""
    src = ws.path(rel)
    if src.exists():
        target = dest / "tests" / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(target.name + ".tmp")
        shutil.copyfile(src, tmp)
        os.replace(tmp, target)


def write_artifacts(dest: Path, ws: Workspace | None, summary: Summary | None,
                    accepted: list[str] | None = None) -> None:
    """Export the test files and report.json. Without a summary (failed job) export only the accepted test files when
    known, else every test file. Each accepted file was already exported when it was accepted; this copies them again
    (the same content), so it is safe to repeat. events.jsonl is not written here: the job appends each event as it is
    emitted (app.jobs)."""
    dest.mkdir(parents=True, exist_ok=True)
    if ws is not None:
        if summary is not None:
            files = summary.test_files
        else:
            files = accepted if accepted is not None else ws.test_files()
        for rel in files:
            export_test(dest, ws, rel)
    if summary is not None:
        (dest / "report.json").write_text(summary.model_dump_json(indent=2), encoding="utf-8")


async def run_job(job_id: str, request: JobRequest, settings: Settings, llm: LLMClient, emit: Emit,
                  cancel: asyncio.Event, events: Callable[[], list[Event]]) -> Summary:
    dest = settings.output_dir / job_id
    prepared: Prepared | None = None
    summary: Summary | None = None
    try:
        prepared = await prepare(job_id, request, settings, llm, emit, cancel)
        ws = prepared.deps.ws

        async def emit_exporting(type_: str, data: dict[str, Any]) -> None:
            # An accepted test file reaches output/<id>/tests before its event, so a run killed later keeps it.
            if type_ == "candidate_accepted":
                try:
                    export_test(dest, ws, data["test_file"])
                except Exception:  # noqa: BLE001 — the final export copies it again
                    log.warning("could not export %s for job %s", data.get("test_file"), job_id, exc_info=True)
            await emit(type_, data)

        summary = await Orchestrator(prepared.deps, request, emit_exporting, cancel,
                                     unavailable_after_s=settings.llm_unavailable_after_s,
                                     call_reservation=settings.call_token_reservation).run(prepared.baseline)
        # A claim the runtime disproved never reaches the report, the job's events or the AI summary.
        summary = summary.model_copy(update={"suspected_bugs": drop_refuted_bugs(summary.suspected_bugs, events())})
        return summary
    except LLMFatal as e:
        raise JobFailed("llm_auth", str(e)) from e
    finally:
        try:
            accepted = sorted({e.data["test_file"] for e in events() if e.type == "candidate_accepted"})
            write_artifacts(dest, prepared.deps.ws if prepared else None, summary, accepted)
        except Exception:  # never mask the job's own outcome
            log.exception("could not write artifacts for job %s", job_id)
        else:
            # The tests are exported to output/<id>/tests, which the API serves from now on; the copy is not needed.
            shutil.rmtree(settings.work_dir / job_id, ignore_errors=True)
