# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
""""Run mutation test" on a finished run: plant small operator bugs in a fresh copy of the repo, one at a time, and check
whether the run's kept tests catch them. An opt-in report, never an acceptance gate; no LLM is involved."""
from __future__ import annotations

import asyncio
import json
import posixpath
import random
import re
import shutil
from pathlib import Path
from typing import Any

from app import repos
from app.config import Settings
from app.coverage import parse_profile
from app.gotools import GoPackage, GoToolError, GoTools, read_module_info
from app.llm.client import Emit
from app.models import Block, JobRequest, Summary
from app.validator import Validator
from app.workspace import Workspace, WorkspaceError, resolve_repo

SEED = 0  # the same sample of mutants every time for the same code and tests
_BUILD_FAILED = re.compile(r"\[(?:build|setup) failed\]")
_TIMED_OUT = re.compile(r"^panic: test timed out", re.M)
KILLED = ("killed", "timeout")  # a timeout counts as killed; "invalid" (does not build) is not counted


class MutationFailed(Exception):
    def __init__(self, reason: str, message: str, output: str = ""):
        super().__init__(message)
        self.reason, self.message, self.output = reason, message, output


def covered(site: dict[str, Any], blocks: list[Block]) -> bool:
    pos = (site["line"], site["col"])
    return any(b.file == site["file"] and (b.start_line, b.start_col) <= pos <= (b.end_line, b.end_col) for b in blocks)


def sample(sites: list[dict[str, Any]], blocks: list[Block], n: int) -> list[dict[str, Any]]:
    """Up to `n` of the sites inside covered blocks, drawn with a fixed seed, in file and position order."""
    eligible = sorted((s for s in sites if covered(s, blocks)), key=lambda s: (s["file"], s["offset"]))
    picked = random.Random(SEED).sample(eligible, min(n, len(eligible)))
    return sorted(picked, key=lambda s: (s["file"], s["offset"]))


async def try_mutant(ws: Workspace, tools: Any, site: dict[str, Any], pkg: GoPackage, timeout_s: float) -> str | None:
    """Apply one mutation, run its package's tests, restore the file. "survived", "killed", "timeout" or "invalid"
    (the mutant does not build); None when cancelled."""
    path = ws.path(site["file"])
    source = path.read_bytes()
    start, old = site["offset"], site["original"].encode()
    if source[start:start + len(old)] != old:
        return "invalid"
    path.write_bytes(source[:start] + site["mutated"].encode() + source[start + len(old):])
    try:
        r = await tools.test_package(pkg, timeout_s)
    finally:
        path.write_bytes(source)
    if r.cancelled:
        return None
    if r.exit_code == 0:
        return "survived"
    if _BUILD_FAILED.search(r.combined):
        return "invalid"
    return "timeout" if r.timed_out or _TIMED_OUT.search(r.combined) else "killed"


def lines(ws: Workspace, site: dict[str, Any]) -> tuple[str, str]:
    """The site's source line before and after the swap, for the mini diff (Go columns count bytes)."""
    raw = ws.path(site["file"]).read_bytes().split(b"\n")[site["line"] - 1]
    c, old = site["col"] - 1, site["original"].encode()
    after = raw[:c] + site["mutated"].encode() + raw[c + len(old):]
    return raw.decode(errors="replace").strip(), after.decode(errors="replace").strip()


def result(mutants: list[dict[str, Any]]) -> dict[str, Any]:
    def score(k: int, s: int) -> float | None:
        return round(100 * k / (k + s), 1) if k + s else None

    per_file: dict[str, list[int]] = {}
    for m in mutants:
        if m["status"] != "invalid":
            counts = per_file.setdefault(m["file"], [0, 0])
            counts[0 if m["status"] in KILLED else 1] += 1
    killed = sum(m["status"] in KILLED for m in mutants)
    survived = sum(m["status"] == "survived" for m in mutants)
    return {"total": len(mutants), "killed": killed, "survived": survived,
            "invalid": sum(m["status"] == "invalid" for m in mutants),
            "timeouts": sum(m["status"] == "timeout" for m in mutants), "score": score(killed, survived),
            "per_file": [{"file": f, "killed": k, "survived": s, "score": score(k, s)}
                         for f, (k, s) in sorted(per_file.items())],
            "mutants": mutants}


def save(out_dir: Path, mutation: dict[str, Any], summary: Summary | None) -> None:
    """The result as `mutation` in report.json (replacing an earlier one; the other keys are kept). A run without a
    report (interrupted) gets none: its events.jsonl holds the result."""
    path = out_dir / "report.json"
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        if summary is None:
            return
        report = summary.model_dump(mode="json")
    report["mutation"] = mutation
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")


async def run_mutation(job_id: str, request: JobRequest, settings: Settings, emit: Emit,
                       cancel: asyncio.Event) -> dict[str, Any]:
    """The mutation_completed payload, or MutationFailed. Works in WORK_DIR/<job>-mutation, removed afterwards."""
    tests = settings.output_dir / job_id / "tests"
    kept = sorted(p.relative_to(tests).as_posix() for p in tests.rglob("*_test.go")) if tests.is_dir() else []
    if not kept:
        raise MutationFailed("no_tests", f"No kept test files were found in ./output/{job_id}/tests.")
    try:
        source = resolve_repo(settings.repos_dir, request.repo_path, settings.host_repos_mount)
    except WorkspaceError as e:
        raise MutationFailed("invalid_repo", f"The run's repository {request.repo_path!r} can't be used any more: "
                             f"{e}") from e
    name = f"{job_id}-mutation"
    shutil.rmtree(settings.work_dir / name, ignore_errors=True)
    try:
        return await _run(name, request, settings, emit, cancel, source, tests, kept)
    finally:
        shutil.rmtree(settings.work_dir / name, ignore_errors=True)


async def _run(name: str, request: JobRequest, settings: Settings, emit: Emit, cancel: asyncio.Event,
               source: Path, tests: Path, kept: list[str]) -> dict[str, Any]:
    cancelled = MutationFailed("cancelled", "Cancelled before the mutation test finished.")
    try:
        async with repos.repo_lock:
            ws = await asyncio.to_thread(Workspace.create, settings.work_dir, name, source,
                                         (settings.host_repos_mount,))
        if request.options.delete_existing_tests:
            ws.delete_existing_tests()
        module, _ = read_module_info(ws.root)
    except (WorkspaceError, OSError, ValueError) as e:
        raise MutationFailed("invalid_repo", f"A fresh copy of the repository could not be made: {e}") from e
    tools = GoTools(ws.root, settings, cancel, tmp_dir=ws.scratch / "gotmp")
    try:
        packages = await tools.list_packages(request.options.exclude_patterns)
    except GoToolError as e:
        if cancel.is_set():
            raise cancelled from e
        raise MutationFailed("go_failed", "Go could not load the module in a fresh copy.", e.result.combined) from e
    try:
        ws.seed_packages([(p.rel_dir, p.name) for p in packages])  # as the run did
        for rel in kept:
            ws.write_test(rel, (tests / rel).read_text(encoding="utf-8"))
    except (WorkspaceError, OSError, ValueError) as e:
        raise MutationFailed("invalid_repo", f"The kept tests could not be copied into a fresh copy: {e}") from e

    measured = await Validator(ws, tools, packages, [], module).measure()
    if cancel.is_set():
        raise cancelled
    if measured.report is None:
        raise MutationFailed("baseline_failed", "The kept tests do not pass in a fresh copy of the repository, so "
                             "no mutant can be judged.", measured.result.combined)
    hits = parse_profile((ws.scratch / "cover.out").read_text(encoding="utf-8"), module)
    blocks = [b for b, hit in hits.items() if hit]

    sites: list[dict[str, Any]] = []
    package_of: dict[str, GoPackage] = {}
    for pkg in packages:
        for f in sorted(ws.path(pkg.rel_dir).glob("*.go")):
            if f.name.endswith("_test.go"):
                continue
            rel = posixpath.normpath(posixpath.join(pkg.rel_dir, f.name))
            package_of[rel] = pkg
            try:
                sites += await tools.mutate(rel)
            except GoToolError:  # a file Go does not build (another build target): none of its lines is covered
                continue
    picked = sample(sites, blocks, settings.mutation_sample)

    await emit("mutation_started", {"total": len(picked)})
    mutants: list[dict[str, Any]] = []
    for index, site in enumerate(picked, 1):
        if cancel.is_set():
            raise cancelled
        status = await try_mutant(ws, tools, site, package_of[site["file"]], settings.mutation_timeout_s)
        if status is None:
            raise cancelled
        before, after = lines(ws, site)
        mutant = {"index": index, "file": site["file"], "line": site["line"], "original": site["original"],
                  "mutated": site["mutated"], "op": site["op"], "status": status, "before": before, "after": after}
        mutants.append(mutant)
        await emit("mutant_result", mutant)
    return result(mutants)
