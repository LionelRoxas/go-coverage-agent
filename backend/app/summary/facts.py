# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
"""RunFacts: everything the summary may state, measured from the finished run (its Summary and events). No LLM."""
from __future__ import annotations

import re
from collections import Counter
from typing import Sequence

from pydantic import BaseModel

from app.models import Event, Summary, SuspectedBug

TERMINAL = ("job_completed", "job_cancelled")
# a compile error from a name declared twice in the package (gohelper's merge check, or the compiler)
_COLLISION = re.compile(r"duplicate declaration: |redeclared in this block")
LOWEST_FILES = 5


class TokenFacts(BaseModel):
    prompt: int
    completion: int
    total: int


class RoleCalls(BaseModel):
    role: str
    reasoning_effort: str | None
    calls: int


class FileFact(BaseModel):
    file: str
    before: float
    after: float


class LowFile(BaseModel):
    file: str
    percent: float
    uncovered_statements: int


class CostFacts(BaseModel):
    input_usd: float
    output_usd: float
    total_usd: float


class RunFacts(BaseModel):
    repo: str
    module: str | None
    model: str
    goal_percent: float
    baseline_percent: float
    final_percent: float
    gain_points: float
    stop_reason: str
    stop_message: str
    rounds: int
    duration_s: float
    duration_min: float
    tokens: TokenFacts
    tokens_per_point: int | None  # tokens per percentage point gained; None without a gain
    cost_usd: CostFacts | None  # only when both GROQ_PRICE_*_PER_M are set
    llm_calls: list[RoleCalls]
    targets_accepted: int
    targets_rejected: int
    rejected_reasons: dict[str, int]
    targets_deferred: int = 0  # items that met a Groq outage and were planned again later (not rejections)
    failed_llm_calls: int = 0  # calls that ended in an error; their billed tokens are in `tokens`
    first_check_passes: int  # writer answers accepted on their first check, with no prune, repair or fix
    llm_fixes: int
    mechanical_repairs: int
    pruned_tests: int
    # PARALLEL_WRITERS comparisons: whether the run's writer requests went out together, and the costs of stale context
    parallel_writers: bool = False
    duplicate_test_renames: int = 0  # Test functions renamed mechanically because the name was already declared
    helper_collision_fixes: int = 0  # Fixer calls for a compile error about a name declared twice in the package
    no_gain_rejections: int = 0  # candidates rejected because they covered nothing new
    llm_timeouts: int
    rate_limit_waits: int
    rate_limit_wait_s: float
    tests_added_count: int
    tests_added: list[str]
    test_files_count: int
    test_files: list[str]
    tests_dir: str  # where the generated test files were exported, relative to the project folder
    per_file: list[FileFact]
    lowest_files: list[LowFile]
    suspected_bugs: list[SuspectedBug]


def cost_usd(prompt_tokens: int, completion_tokens: int,
             price_input_per_m: float | None, price_output_per_m: float | None) -> CostFacts | None:
    if price_input_per_m is None or price_output_per_m is None:
        return None
    inp = prompt_tokens * price_input_per_m / 1_000_000
    out = completion_tokens * price_output_per_m / 1_000_000
    return CostFacts(input_usd=round(inp, 4), output_usd=round(out, 4), total_usd=round(inp + out, 4))


def _module(packages: Sequence[str]) -> str | None:
    """The module path: the import path every package starts with (the shortest), when there is one."""
    if not packages:
        return None
    root = min(packages, key=len)
    return root if all(p == root or p.startswith(root + "/") for p in packages) else None


def _run_events(events: Sequence[Event]) -> list[Event]:
    """Events of the run itself: up to its terminal event (later ones belong to summaries written afterwards)."""
    for i, e in enumerate(events):
        if e.type in TERMINAL:
            return list(events[:i])
    return list(events)


def build_facts(summary: Summary, events: Sequence[Event], *, repo: str, model: str, job_id: str,
                price_input_per_m: float | None = None, price_output_per_m: float | None = None) -> RunFacts:
    run = _run_events(events)
    by_type: dict[str, list[dict]] = {}
    for e in run:
        by_type.setdefault(e.type, []).append(e.data)

    packages = next((d.get("packages", []) for d in by_type.get("workspace_ready", [])), [])
    baseline_files = next((d["report"]["files"] for d in by_type.get("baseline_measured", [])), [])
    statements = {f["file"]: f["statements"] for f in baseline_files}

    answered = [d for d in by_type.get("llm_call", []) if not d.get("failed")]
    calls = Counter((d.get("role", ""), d.get("reasoning_effort")) for d in answered)
    rejected = Counter(d.get("reason", "") for d in by_type.get("candidate_rejected", []))

    collision_fixes = 0
    last_output: dict[tuple[int, str], str] = {}  # each item's latest compile error output
    for e in run:
        key = (e.data.get("index", 0), e.data.get("file", ""))
        if e.type == "validation_result":
            last_output[key] = e.data.get("output", "") if e.data.get("kind") == "compile_error" else ""
        elif e.type == "fix_attempt" and e.data.get("kind") == "compile_error":
            collision_fixes += bool(_COLLISION.search(last_output.get(key, "")))
    started = next((d for d in by_type.get("job_started", [])), {})

    first_passes = 0
    awaiting: set[tuple[int, str]] = set()  # items whose writer answer has not been checked yet
    for e in run:
        key = (e.data.get("index", 0), e.data.get("file", ""))
        if e.type == "llm_call" and e.data.get("role") == "writer" and not e.data.get("failed"):
            awaiting.add(key)
        elif e.type == "validation_result" and key in awaiting:
            awaiting.discard(key)
            first_passes += e.data.get("kind") == "accepted"

    per_file = [FileFact(file=d.file, before=d.before, after=d.after) for d in summary.per_file]
    lows = []
    for d in summary.per_file:
        total = statements.get(d.file)
        if total is None or d.after >= 100:
            continue
        lows.append(LowFile(file=d.file, percent=d.after, uncovered_statements=total - round(total * d.after / 100)))
    lows.sort(key=lambda x: (x.percent, -x.uncovered_statements, x.file))

    tokens = summary.tokens
    gain = round(summary.final_percent - summary.baseline_percent, 2)
    waits = by_type.get("rate_limited", [])
    return RunFacts(
        repo=repo, module=_module(packages), model=model, goal_percent=summary.target,
        baseline_percent=summary.baseline_percent, final_percent=summary.final_percent, gain_points=gain,
        stop_reason=summary.stop_reason.value, stop_message=summary.message, rounds=len(summary.iterations),
        duration_s=summary.duration_s, duration_min=round(summary.duration_s / 60, 1),
        tokens=TokenFacts(prompt=tokens.prompt_tokens, completion=tokens.completion_tokens, total=tokens.total),
        tokens_per_point=round(tokens.total / gain) if gain > 0 else None,
        cost_usd=cost_usd(tokens.prompt_tokens, tokens.completion_tokens, price_input_per_m, price_output_per_m),
        llm_calls=[RoleCalls(role=r, reasoning_effort=eff, calls=n) for (r, eff), n in calls.items()],
        targets_accepted=len(by_type.get("candidate_accepted", [])), targets_rejected=sum(rejected.values()),
        rejected_reasons=dict(rejected), first_check_passes=first_passes,
        targets_deferred=len(by_type.get("candidate_deferred", [])),
        failed_llm_calls=len(by_type.get("llm_call", [])) - len(answered),
        llm_fixes=len(by_type.get("fix_attempt", [])), mechanical_repairs=len(by_type.get("mechanical_repair", [])),
        pruned_tests=sum(len(d.get("tests", [])) for d in by_type.get("tests_pruned", [])),
        parallel_writers=bool((started.get("options") or {}).get("parallel_writers", False)),
        duplicate_test_renames=sum(str(d.get("description", "")).startswith("renamed duplicate test")
                                   for d in by_type.get("mechanical_repair", [])),
        helper_collision_fixes=collision_fixes, no_gain_rejections=rejected.get("no_gain", 0),
        llm_timeouts=sum(d.get("kind") == "llm_timeout" for d in by_type.get("validation_result", [])),
        rate_limit_waits=len(waits), rate_limit_wait_s=round(sum(float(d.get("seconds", 0)) for d in waits), 1),
        tests_added_count=len(summary.tests_added), tests_added=list(summary.tests_added),
        test_files_count=len(summary.test_files), test_files=list(summary.test_files),
        tests_dir=f"output/{job_id}/tests",
        per_file=per_file, lowest_files=lows[:LOWEST_FILES], suspected_bugs=list(summary.suspected_bugs),
    )
