# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
"""SUMMARY.md and the ai_summary / ai_summary_error keys of report.json. The frontend's "Copy as Markdown"
(frontend/src/lib/aiSummary.ts) builds the same Markdown; keep the two in step."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.models import Summary

NOTE = "AI-written from this run's measured data."


def usd(value: float) -> str:
    return f"${value:.2f}" if value >= 0.01 or value == 0 else f"${value:.4f}"


def cost_line(cost: dict[str, float]) -> str:
    return f"Estimated cost: {usd(cost['total'])} (input {usd(cost['input'])}, output {usd(cost['output'])})"


def to_markdown(ai: dict[str, Any], *, repo: str, model: str, generated_at: float) -> str:
    """`ai`: a summary_generated payload (business, technical, cost_usd?)."""
    b, t = ai["business"], ai["technical"]
    day = datetime.fromtimestamp(generated_at, UTC).date().isoformat()
    blocks: list[str] = [f"# AI summary: {repo}", f"_{NOTE} Generated {day} with {model}._"]

    def add(text: str, prefix: str = "") -> None:
        if text.strip():
            blocks.append(f"{prefix}{text.strip()}")

    def bullets(title: str, items: list[str]) -> None:
        if items:
            blocks.append(f"**{title}**")
            blocks.append("\n".join(f"- {i}" for i in items))

    blocks.append("## For stakeholders")
    add(b["headline"], "### ")
    add(b["outcome"])
    add(b["efficiency"])
    if ai.get("cost_usd"):
        blocks.append(cost_line(ai["cost_usd"]))
    bullets("Risks", b["risks"])
    add(b["recommendation"], "**Recommendation:** ")

    blocks.append("## For engineering teams")
    add(t["headline"], "### ")
    add(t["what_was_tested"], "**What was tested:** ")
    add(t["where_tests_live"], "**Where the tests live:** ")
    bullets("Gaps", [f"`{g['file']}`: {g['detail']}" for g in t["gaps"]])
    bullets("Suspected bugs", t["suspected_bugs"])
    add(t["rejected_or_failed"], "**Rejected or failed:** ")
    add(t["how_to_run"], "**How to run:** ")
    bullets("Next steps", t["next_steps"])
    return "\n\n".join(blocks) + "\n"


def save(out_dir: Path, summary: Summary, *, ai: dict[str, Any] | None = None, markdown: str | None = None,
         error: dict[str, str] | None = None) -> None:
    """A new summary replaces ai_summary (and clears an earlier error) and rewrites SUMMARY.md; a failure records
    ai_summary_error and keeps an earlier summary and its SUMMARY.md."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "report.json"
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        report = summary.model_dump(mode="json")
    if ai is not None:
        report["ai_summary"] = ai
        report.pop("ai_summary_error", None)
        if markdown is not None:
            (out_dir / "SUMMARY.md").write_text(markdown, encoding="utf-8")
    if error is not None:
        report["ai_summary_error"] = error
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
