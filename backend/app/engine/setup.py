# AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
"""Turns a JobRequest into a ready-to-run workspace with a measured baseline."""
from __future__ import annotations

import asyncio
import posixpath
from dataclasses import dataclass

from app.agents.context import ContextProvider
from app.agents.llm_agents import Agents
from app.config import Settings
from app.engine.orchestrator import RunDeps
from app.gotools import GoToolError, GoTools, read_module_info
from app.llm.client import Emit, LLMClient
from app.models import CoverageReport, JobRequest
from app.validator import Validator
from app.workspace import Workspace, WorkspaceError, resolve_repo


class JobFailed(Exception):
    def __init__(self, reason: str, message: str, output: str = ""):
        super().__init__(message)
        self.reason, self.message, self.output = reason, message, output


@dataclass
class Prepared:
    deps: RunDeps
    baseline: CoverageReport


async def prepare(job_id: str, request: JobRequest, settings: Settings, llm: LLMClient | None,
                  emit: Emit, cancel: asyncio.Event) -> Prepared:
    try:
        source = resolve_repo(settings.repos_dir, request.repo_path)
    except WorkspaceError as e:
        raise JobFailed("invalid_repo", str(e)) from e

    ws = Workspace.create(settings.work_dir, job_id, source)
    removed = ws.delete_existing_tests() if request.options.delete_existing_tests else []
    tools = GoTools(ws.root, settings, cancel)
    module, go_version = read_module_info(ws.root)
    try:
        packages = await tools.list_packages(request.options.exclude_patterns)
    except GoToolError as e:
        raise JobFailed("repo_does_not_build", "Go could not load this module.", e.result.combined) from e
    if not packages:
        raise JobFailed("no_packages", "No testable Go packages remain after exclusions.")
    ws.seed_packages([(p.rel_dir, p.name) for p in packages])
    await emit("workspace_ready", {"removed_tests": removed, "packages": [p.import_path for p in packages]})

    try:
        funcs = await tools.funcs()
        symbols = await tools.symbols()
    except GoToolError as e:
        raise JobFailed("repo_does_not_build", "Some Go files in this module could not be parsed.",
                        e.result.combined) from e
    validator = Validator(ws, tools, packages, funcs, module)
    measured = await validator.measure()
    if cancel.is_set():
        raise JobFailed("cancelled", "Cancelled before the baseline finished.")
    if measured.report is None:
        if ws.test_files():
            raise JobFailed("existing_tests_fail",
                            "The repo's existing tests fail. Enable 'delete existing tests' or fix them first.",
                            measured.result.combined)
        raise JobFailed("repo_does_not_build", "The repo does not build with this Go toolchain.",
                        measured.result.combined)
    vet = await tools.vet(packages)
    if vet.exit_code != 0:
        # Every candidate would be rejected as vet_error, so fail now instead of wasting the token budget.
        raise JobFailed("repo_vet_fails", "`go vet` already fails on the unmodified repo.", vet.combined)
    await emit("baseline_measured", {"report": measured.report.public()})

    by_dir = {p.rel_dir: p for p in packages}
    contexts = ContextProvider(ws, tools, funcs, symbols, module, go_version, by_dir)
    deps = RunDeps(ws=ws, validator=validator, agents=Agents(llm, settings.max_prompt_tokens), contexts=contexts,
                   package_of=lambda file: by_dir[posixpath.dirname(file) or "."].name)
    return Prepared(deps=deps, baseline=measured.report)
