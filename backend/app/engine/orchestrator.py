# AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
"""The autonomous loop: plan → write → validate → prune/fix → accept or roll back → repeat."""
from __future__ import annotations

import asyncio
import time
from collections import Counter
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from app.agents.context import ContextTooLarge
from app.agents.repair import mechanical_repair
from app.agents.planner import plan
from app.engine.policy import StopPolicy, stop_message
from app.llm.client import Emit, LLMBudgetExhausted, LLMCancelled, LLMError, LLMFatal
from app.models import (CoverageReport, FileDelta, FuncKey, IterationRecord, JobRequest, PlanItem, StopReason,
                        Summary, SuspectedBug, TestSnippet, TokenUsage)
from app.validator import ValidationKind, ValidationResult
from app.workspace import Workspace, test_path_for


MAX_MECHANICAL_REPAIRS = 3


class Cancelled(Exception):
    pass


@dataclass
class RunDeps:
    ws: Workspace
    validator: Any
    agents: Any
    contexts: Any
    package_of: Callable[[str], str]


class Orchestrator:
    def __init__(self, deps: RunDeps, request: JobRequest, emit: Emit, cancel: asyncio.Event,
                 clock: Callable[[], float] = time.monotonic):
        self.deps, self.request, self.emit, self.cancel, self.clock = deps, request, emit, cancel, clock
        self.opts = request.options
        self.policy = StopPolicy(request.target_coverage, self.opts.min_gain, self.opts.patience)
        self.tokens = TokenUsage()
        self.failed: Counter[FuncKey] = Counter()
        self.skipped: set[FuncKey] = set()
        self.iterations: list[IterationRecord] = []
        self.gains: list[float] = []
        self.tests_added: list[str] = []
        self.test_files: list[str] = []
        self.bugs: list[SuspectedBug] = []
        self.index = 0

    async def run(self, baseline: CoverageReport) -> Summary:
        started = self.clock()
        self.baseline = self.report = baseline
        detail = ""
        try:
            reason = await self._loop()
        except LLMBudgetExhausted as e:
            reason, detail = StopReason.BUDGET_EXHAUSTED, str(e)
        except Cancelled:
            reason = StopReason.CANCELLED
        return self._summary(reason, detail, self.clock() - started)

    async def _loop(self) -> StopReason:
        for index in range(1, self.opts.max_iterations + 1):
            if self.policy.target_reached(self.report.percent):
                return StopReason.TARGET_REACHED
            items = plan(self.report, self.failed, self.skipped, max_items=self.opts.targets_per_iteration)
            if not items:
                return StopReason.NO_REMAINING_TARGETS
            self.index, start = index, self.report.percent
            await self.emit("iteration_started", {"index": index, "percent": start})
            await self.emit("plan_created", {"index": index, "items": [
                {"file": i.file, "functions": [k.label() for k in i.functions],
                 "uncovered_statements": i.uncovered_statements} for i in items]})
            accepted = rejected = 0
            for item in items:
                if await self._attempt(item):
                    accepted += 1
                else:
                    rejected += 1
                if self.policy.target_reached(self.report.percent):
                    await self._record(index, start, accepted, rejected)
                    return StopReason.TARGET_REACHED
            await self._record(index, start, accepted, rejected)
            if self.policy.marginal(self.gains):
                return StopReason.MARGINAL_GAINS
        return StopReason.MAX_ITERATIONS

    async def _record(self, index: int, start: float, accepted: int, rejected: int) -> None:
        end = self.report.percent
        self.iterations.append(IterationRecord(index=index, start_percent=start, end_percent=end,
                                               accepted=accepted, rejected=rejected))
        self.gains.append(round(end - start, 2))
        await self.emit("iteration_completed", {"index": index, "start_percent": start, "end_percent": end,
                                                "accepted": accepted, "rejected": rejected})

    def _check(self) -> None:
        if self.cancel.is_set():
            raise Cancelled()
        if self.tokens.total >= self.opts.max_llm_tokens:
            raise LLMBudgetExhausted("Reached this job's token budget (max_llm_tokens).")

    async def _call(self, role: str, item: PlanItem,
                    coro: Awaitable[tuple[TestSnippet, TokenUsage]]) -> TestSnippet:
        try:
            snip, usage = await coro
        except LLMCancelled as e:
            raise Cancelled() from e
        self.tokens = self.tokens.add(usage)
        await self.emit("llm_call", {"index": self.index, "file": item.file, "role": role,
                                     "prompt_tokens": usage.prompt_tokens, "completion_tokens": usage.completion_tokens,
                                     "total_tokens": self.tokens.total})
        return snip

    async def _validate(self, base: dict[str, Any], coro: Awaitable[ValidationResult]) -> ValidationResult:
        result = await coro
        if self.cancel.is_set():  # gotools reports a cancelled run as a failure; do not misreport it
            raise Cancelled()
        await self.emit("validation_result", {**base, **result.event()})
        return result

    async def _generated(self, base: dict[str, Any], test_file: str, snip: TestSnippet) -> None:
        await self.emit("candidate_generated", {**base, "test_file": test_file, "code": snip.code,
                                                "test_plan": [s.model_dump() for s in snip.test_plan]})

    async def _too_large(self, item: PlanItem, base: dict[str, Any]) -> bool:
        """Context too big: retry with a single function, or skip the item for good."""
        if len(item.functions) > 1:
            return await self._attempt(item.model_copy(update={"functions": item.functions[:1]}))
        self.skipped.update(item.functions)
        await self.emit("candidate_rejected", {**base, "reason": "too_large"})
        return False

    async def _attempt(self, item: PlanItem) -> bool:
        self._check()
        ws, validator = self.deps.ws, self.deps.validator
        test_file, package = test_path_for(item.file), self.deps.package_of(item.file)
        base = {"index": self.index, "file": item.file}
        try:
            inputs = await self.deps.contexts.inputs_for(item, self.report)
        except ContextTooLarge:
            return await self._too_large(item, base)

        snap = ws.snapshot([test_file, "go.mod", "go.sum"])
        snip: TestSnippet | None = None
        try:
            try:
                # render_context (inside agents.write) is where ContextTooLarge is actually raised
                snip = await self._call("writer", item, self.deps.agents.write(item, inputs))
            except ContextTooLarge:
                too_large = True
            else:
                too_large = False
                await self._generated(base, test_file, snip)
                result = await self._validate(base, validator.validate(test_file, package, snip, self.report))
                attempts = repairs = 0
                while not result.accepted:
                    self._check()
                    if result.kind is ValidationKind.TEST_FAILURE:
                        doomed = [n for n in result.failed_tests if n in result.new_tests]
                        if doomed and len(doomed) == len(result.failed_tests) and len(doomed) < len(result.new_tests):
                            await self.emit("tests_pruned", {**base, "tests": doomed})
                            result = await self._validate(
                                base, validator.prune_and_check(test_file, doomed, self.report, result.new_tests))
                            if result.accepted:
                                break
                    if result.kind is ValidationKind.COMPILE_ERROR and repairs < MAX_MECHANICAL_REPAIRS:
                        repaired = mechanical_repair(snip, result.output, package)
                        if repaired is not None:  # forgotten import / self-qualified identifier: no LLM call needed
                            repairs += 1
                            await self.emit("mechanical_repair", {**base, "repair": repairs})
                            ws.restore(snap)
                            snip = repaired
                            await self._generated(base, test_file, snip)
                            result = await self._validate(base, validator.validate(test_file, package, snip, self.report))
                            continue
                    if attempts >= self.opts.max_fix_attempts:
                        break
                    attempts += 1
                    await self.emit("fix_attempt", {**base, "attempt": attempts, "kind": result.kind.value})
                    ws.restore(snap)
                    snip = await self._call("fixer", item, self.deps.agents.fix(item, inputs, snip, result))
                    await self._generated(base, test_file, snip)
                    result = await self._validate(base, validator.validate(test_file, package, snip, self.report))
        except (LLMError, ContextTooLarge) as e:
            if isinstance(e, (LLMBudgetExhausted, LLMFatal, LLMCancelled)):
                ws.restore(snap)
                raise
            too_large = False
            result = ValidationResult(ValidationKind.LLM_ERROR, str(e))
        except BaseException:  # incl. Cancelled, OSError, asyncio.CancelledError: never leave a candidate behind
            ws.restore(snap)
            raise
        if too_large:
            ws.restore(snap)
            return await self._too_large(item, base)

        if result.accepted and result.report is not None:
            gain = round(result.report.percent - self.report.percent, 2)
            self.report = result.report
            self.tests_added.extend(result.new_tests)
            if test_file not in self.test_files:
                self.test_files.append(test_file)
            if snip is not None:
                self.bugs.extend(snip.suspected_bugs)
            await self.emit("candidate_accepted", {**base, "test_file": test_file, "tests": result.new_tests,
                                                   "percent": self.report.percent, "gain": gain})
            return True

        ws.restore(snap)
        for key in item.functions:
            self.failed[key] += 1
        await self.emit("candidate_rejected", {**base, "reason": result.kind.value})
        return False

    def _summary(self, reason: StopReason, detail: str, duration: float) -> Summary:
        before = {f.file: f.percent for f in self.baseline.files}
        per_file = sorted((FileDelta(file=f.file, before=before.get(f.file, 0.0), after=f.percent)
                           for f in self.report.files), key=lambda d: (-(d.after - d.before), d.file))
        return Summary(
            stop_reason=reason, message=stop_message(reason, self.request, detail),
            target=self.request.target_coverage, baseline_percent=self.baseline.percent,
            final_percent=self.report.percent, iterations=self.iterations, test_files=sorted(self.test_files),
            tests_added=self.tests_added, suspected_bugs=self.bugs, per_file=per_file, tokens=self.tokens,
            duration_s=round(duration, 1),
        )
