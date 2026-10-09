# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
"""Chooses what to test next. Deterministic on purpose: it costs no LLM tokens and is easy to test."""
from __future__ import annotations

from typing import Mapping

from app.models import CoverageReport, FuncKey, PlanItem


def plan(report: CoverageReport, failed: Mapping[FuncKey, int], skipped: set[FuncKey], *,
         max_items: int = 3, max_statements: int = 100, max_failures: int = 2) -> list[PlanItem]:
    """Pack each file's biggest uncovered functions up to `max_statements`, then take the `max_items` fullest files.

    Ranking files by what one prompt can cover (not by their single biggest function) spends the fixed
    per-call tokens where they buy the most statements (measured in run 1: ~1.9K tokens per percentage
    point for items over 40 statements versus ~3.7K for items of 20 or fewer).
    """
    candidates = [fc for fc in report.functions
                  if fc.uncovered > 0 and failed.get(fc.key, 0) < max_failures and fc.key not in skipped]
    candidates.sort(key=lambda fc: (-fc.uncovered, fc.key.file, fc.key.receiver, fc.key.name))
    items: dict[str, PlanItem] = {}
    for fc in candidates:
        item = items.get(fc.key.file)
        if item is None:
            item = items[fc.key.file] = PlanItem(file=fc.key.file, functions=[], uncovered_statements=0)
        if item.functions and item.uncovered_statements + fc.uncovered > max_statements:
            continue
        item.functions.append(fc.key)
        item.uncovered_statements += fc.uncovered
    ranked = sorted(items.values(), key=lambda i: (-i.uncovered_statements, i.file))
    return ranked[:max_items]
