# AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
"""Chooses what to test next. Deterministic on purpose: it costs no LLM tokens and is easy to test."""
from __future__ import annotations

from typing import Mapping

from app.models import CoverageReport, FuncKey, PlanItem


def plan(report: CoverageReport, failed: Mapping[FuncKey, int], skipped: set[FuncKey], *,
         max_items: int = 3, max_statements: int = 60, max_failures: int = 2) -> list[PlanItem]:
    candidates = [fc for fc in report.functions
                  if fc.uncovered > 0 and failed.get(fc.key, 0) < max_failures and fc.key not in skipped]
    candidates.sort(key=lambda fc: (-fc.uncovered, fc.key.file, fc.key.receiver, fc.key.name))
    items: dict[str, PlanItem] = {}
    for fc in candidates:
        item = items.get(fc.key.file)
        if item is None:
            if len(items) >= max_items:
                continue
            item = items[fc.key.file] = PlanItem(file=fc.key.file, functions=[], uncovered_statements=0)
        if item.functions and item.uncovered_statements + fc.uncovered > max_statements:
            continue
        item.functions.append(fc.key)
        item.uncovered_statements += fc.uncovered
    return list(items.values())
