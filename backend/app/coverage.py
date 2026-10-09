# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
"""Parse `go test -coverprofile` output and attribute statements to files and functions."""
from __future__ import annotations

import re
from collections import defaultdict

from app.models import Block, CoverageReport, FileCoverage, FuncCoverage, FuncInfo, FuncKey

_LINE = re.compile(
    r"^(?P<file>.+):(?P<sl>\d+)\.(?P<sc>\d+),(?P<el>\d+)\.(?P<ec>\d+) (?P<n>\d+) (?P<count>\d+)$"
)


def parse_profile(text: str, module: str) -> dict[Block, bool]:
    prefix = module + "/"
    hits: dict[Block, bool] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("mode:"):
            continue
        m = _LINE.match(line)
        if m is None:
            raise ValueError(f"unrecognized coverage line: {line!r}")
        file = m["file"].removeprefix(prefix)
        block = Block(file=file, start_line=int(m["sl"]), start_col=int(m["sc"]),
                      end_line=int(m["el"]), end_col=int(m["ec"]), statements=int(m["n"]))
        hits[block] = hits.get(block, False) or int(m["count"]) > 0
    return hits


def _pct(covered: int, total: int) -> float:
    return round(100.0 * covered / total, 2) if total else 0.0


def _merge_ranges(ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for start, end in sorted(ranges):
        if merged and start <= merged[-1][1] + 1:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def summarize(hits: dict[Block, bool], funcs: list[FuncInfo]) -> CoverageReport:
    funcs_by_file: dict[str, list[FuncInfo]] = defaultdict(list)
    for f in funcs:
        funcs_by_file[f.key.file].append(f)

    file_totals: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    fn_totals: dict[FuncKey, list[int]] = {}
    fn_uncovered: dict[FuncKey, list[tuple[int, int]]] = defaultdict(list)

    for block, hit in hits.items():
        ft = file_totals[block.file]
        ft[0] += block.statements
        ft[1] += block.statements if hit else 0
        owner = next((f for f in funcs_by_file.get(block.file, [])
                      if f.start_line <= block.start_line <= f.end_line), None)
        if owner is None:
            continue
        totals = fn_totals.setdefault(owner.key, [0, 0])
        totals[0] += block.statements
        totals[1] += block.statements if hit else 0
        if not hit:
            fn_uncovered[owner.key].append((block.start_line, block.end_line))

    total = sum(t[0] for t in file_totals.values())
    covered = sum(t[1] for t in file_totals.values())
    files = [FileCoverage(file=f, statements=t[0], covered=t[1], percent=_pct(t[1], t[0]))
             for f, t in sorted(file_totals.items())]
    functions = [
        FuncCoverage(key=k, statements=t[0], covered=t[1], uncovered_lines=_merge_ranges(fn_uncovered[k]))
        for k, t in sorted(fn_totals.items(), key=lambda kv: (kv[0].file, kv[0].receiver, kv[0].name))
    ]
    return CoverageReport(
        total_statements=total, covered_statements=covered, percent=_pct(covered, total),
        files=files, functions=functions,
        covered_block_ids=sorted(b.id for b, h in hits.items() if h),
    )
