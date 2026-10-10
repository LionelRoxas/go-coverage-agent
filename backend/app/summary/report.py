# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
"""SUMMARY.md and the ai_summary / ai_summary_error keys of report.json. The frontend's "Copy as Markdown"
(frontend/src/lib/aiSummary.ts) builds the same Markdown; keep the two in step."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.models import Disagreement, Summary, TokenUsage

NOTE = "AI-written from this run's measured data."
EMPTY = "Nothing in this part could be checked against the run's data."
DISAGREEMENTS = "Prediction disagreements (not confirmed bugs: the prediction or the code is wrong)"
# frontend/src/lib/format.ts DISAGREEMENT_HOW / DISAGREEMENT_OUTCOME hold the same words
HOW = {True: "removed when it failed", False: "sent to the Fixer when it failed"}
OUTCOME = {"kept": "a test of this name was kept after a fix and may now expect the code's value",
           "dropped": "not in the accepted tests", "not_accepted": "its attempt was not accepted"}


def usd(value: float) -> str:
    """One rule for every amount: 4 decimals below $1, 2 from $1 up."""
    return f"${value:.4f}" if value < 1 else f"${value:.2f}"


def cost_line(cost: dict[str, float]) -> str:
    """The run's cost (what the text talks about), this summary call's, and both together."""
    return (f"Run cost {usd(cost['run'])} · summary {usd(cost['summary'])} · total {usd(cost['total'])} "
            f"(input {usd(cost['input'])}, output {usd(cost['output'])})")


def disagreement_line(d: Disagreement) -> str:
    """One disagreement for the summary's deterministic part: where, which test, what Go observed, what happened to
    the test at that point and, when known (not in older reports), what became of its candidate."""
    observed = " | ".join(d.lines) if d.lines else "no assertion output"
    then = "; ".join(filter(None, [HOW[d.pruned], OUTCOME.get(d.outcome, "")]))
    return f"`{d.test}` ({d.file}: {', '.join(d.functions)}): {observed} ({then})"


def _has_text(part: dict[str, Any]) -> bool:
    return any(v.strip() if isinstance(v, str) else bool(v) for v in part.values())


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
    if not _has_text(b):
        blocks.append(f"_{EMPTY}_")
    add(b["headline"], "### ")
    add(b["outcome"])
    add(b["efficiency"])
    if ai.get("cost_usd"):
        blocks.append(cost_line(ai["cost_usd"]))
    bullets("Risks", b["risks"])
    add(b["recommendation"], "**Recommendation:** ")

    blocks.append("## For engineering teams")
    if not _has_text(t):
        blocks.append(f"_{EMPTY}_")
    add(t["headline"], "### ")
    add(t["what_was_tested"], "**What was tested:** ")
    add(t["where_tests_live"], "**Where the tests live:** ")
    bullets("Gaps", [f"`{g['file']}`: {g['detail']}" for g in t["gaps"]])
    bullets("Suspected bugs", t["suspected_bugs"])
    bullets(DISAGREEMENTS, ai.get("disagreements") or [])  # deterministic, from the run (older payloads lack it)
    add(t["rejected_or_failed"], "**Rejected or failed:** ")
    add(t["how_to_run"], "**How to run:** ")
    bullets("Next steps", t["next_steps"])
    return "\n\n".join(blocks) + "\n"


def save(out_dir: Path, summary: Summary, *, ai: dict[str, Any] | None = None, markdown: str | None = None,
         error: dict[str, str] | None = None, summary_tokens: TokenUsage | None = None) -> None:
    """A new summary replaces ai_summary (and clears an earlier error) and rewrites SUMMARY.md; a failure records
    ai_summary_error and keeps an earlier summary and its SUMMARY.md. `summary_tokens`: every summary call of the
    job so far, kept apart from the run's own `tokens`."""
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
    if summary_tokens is not None:
        report["summary_tokens"] = {"prompt_tokens": summary_tokens.prompt_tokens,
                                    "completion_tokens": summary_tokens.completion_tokens,
                                    "total_tokens": summary_tokens.total}
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
