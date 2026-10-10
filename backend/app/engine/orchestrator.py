# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
"""The autonomous loop: plan → write → validate → prune/fix → accept or roll back → repeat."""
from __future__ import annotations

import asyncio
import logging
import time
from collections import Counter
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Coroutine

from app.agents.context import ContextTooLarge
from app.agents.history import AttemptRecord, attempt_record, observed_lines
from app.agents.planner import plan
from app.agents.repair import clean_imports, mechanical_repair
from app.engine.policy import StopPolicy, stop_message
from app.llm.client import (LLM_CALL, Emit, LLMBudgetExhausted, LLMCancelled, LLMError, LLMFatal,
                            LLMOutputTooLarge, LLMTimeout, LLMTransportError, LLMUnavailable, OnRequest)
from app.models import (CoverageReport, Disagreement, FileDelta, FuncKey, IterationRecord, JobRequest, PlanItem,
                        StopReason, Summary, SuspectedBug, TestSnippet, TokenUsage)
from app.validator import ValidationKind, ValidationResult
from app.workspace import Workspace, test_path_for


MAX_MECHANICAL_REPAIRS = 3
OUTAGE_BACKOFF_S = 15.0  # wait after the first Groq transport failure in a row; doubles per failure, up to the cap
OUTAGE_BACKOFF_MAX_S = 120.0
log = logging.getLogger(__name__)


def _event(d: Disagreement) -> dict[str, Any]:
    """A disagreement as its event shows it: where it happened tells how, and the outcome is not known yet."""
    return d.model_dump(exclude={"pruned", "outcome"})


class Cancelled(Exception):
    pass


class GroqUnreachable(Exception):
    """Groq has been unreachable (timeouts, 5xx, connection errors) for longer than the outage window."""

    def __init__(self, seconds: float):
        super().__init__(f"Groq unreachable for {seconds:.0f} s")
        self.minutes = max(1, round(seconds / 60))


@dataclass
class _Written:
    """One writer request of a parallel round: its answer, or the error it ended with (raised again, in plan order,
    when the item is validated, so it takes exactly the path it would have taken in a sequential round)."""
    snip: TestSnippet | None = None
    error: BaseException | None = None
    started: float = 0.0


@dataclass
class RunDeps:
    ws: Workspace
    validator: Any
    agents: Any
    contexts: Any
    package_of: Callable[[str], str]


class Orchestrator:
    def __init__(self, deps: RunDeps, request: JobRequest, emit: Emit, cancel: asyncio.Event,
                 clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], Awaitable[None]] | None = None, unavailable_after_s: float = 600.0,
                 call_reservation: int = 0):
        self.deps, self.request, self.emit, self.cancel, self.clock = deps, request, emit, cancel, clock
        self._sleep, self.unavailable_after_s = sleep, unavailable_after_s
        # Job budget (max_llm_tokens): every call reserves this many tokens while it is in flight
        # (CALL_TOKEN_RESERVATION), so calls running at the same time never jointly overshoot the budget by more
        # than one reservation, as long as each call stays within CALL_TOKEN_RESERVATION (a larger answer adds its
        # excess, as a single call does in a sequential run).
        self.call_reservation = call_reservation
        self._reserved = 0
        # The current run of Groq transport failures: when the first failing call started, and how many in a row.
        self._outage_since: float | None = None
        self._outage_failures = 0
        self.deferred = 0  # items that hit a transport failure (planned again later, never counted as failed)
        self.opts = request.options
        self.parallel = self.opts.parallel_writers  # PARALLEL_WRITERS: each round's writer requests go out together
        self.policy = StopPolicy(request.target_coverage, self.opts.min_gain, self.opts.patience)
        self.tokens = TokenUsage()
        self.failed: Counter[FuncKey] = Counter()
        self.skipped: set[FuncKey] = set()
        self.iterations: list[IterationRecord] = []
        self.gains: list[float] = []
        self.tests_added: list[str] = []
        self.test_files: list[str] = []
        self.bugs: list[SuspectedBug] = []
        self.disagreements: list[Disagreement] = []  # failing tests pruned (prediction vs implementation)
        self.index = 0

    async def run(self, baseline: CoverageReport) -> Summary:
        started = self.clock()
        self.baseline = self.report = baseline
        detail, minutes = "", 0
        try:
            reason = await self._loop()
        except LLMBudgetExhausted as e:
            reason, detail = StopReason.BUDGET_EXHAUSTED, str(e)
        except GroqUnreachable as e:
            reason, minutes = StopReason.LLM_UNAVAILABLE, e.minutes
        except Cancelled:
            reason = StopReason.CANCELLED
        return self._summary(reason, detail, self.clock() - started, minutes)

    async def _loop(self) -> StopReason:
        # Rounds in which every item only met a Groq outage measured nothing, so they use up neither max_iterations
        # nor patience; the outage window (LLM_UNAVAILABLE_AFTER_S) bounds them.
        counted = index = 0
        while counted < self.opts.max_iterations:
            index += 1
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
            deferred_before = self.deferred
            written: list[_Written] | list[None] = (await self._write_round(items) if self.parallel
                                                    else [None] * len(items))
            refused: LLMBudgetExhausted | None = None
            for item, answer in zip(items, written, strict=False):  # validation: one item at a time, in plan order
                if answer is not None and isinstance(answer.error, LLMBudgetExhausted) and answer.error.local:
                    # Refused before it was sent (budget reserved by the round's other requests): skip it, check
                    # the answers already paid for, then stop for the budget.
                    refused = refused or answer.error
                    continue
                before = self.deferred
                if await self._attempt(item, answer):
                    accepted += 1
                elif self.deferred == before:  # a deferred item is not a rejection
                    rejected += 1
                if self.policy.target_reached(self.report.percent):
                    await self._record(index, start, accepted, rejected, self.deferred - deferred_before)
                    return StopReason.TARGET_REACHED
            if refused is not None:
                raise refused
            deferred = self.deferred - deferred_before
            if self.parallel and deferred and self._outage_since is not None:
                await self._back_off()  # once per round: the round's requests all went out together
            outage_only = accepted == 0 and rejected == 0 and deferred > 0
            await self._record(index, start, accepted, rejected, deferred, count_gain=not outage_only)
            if not outage_only:
                counted += 1
            if self.policy.marginal(self.gains):
                return StopReason.MARGINAL_GAINS
        return StopReason.MAX_ITERATIONS

    async def _record(self, index: int, start: float, accepted: int, rejected: int, deferred: int = 0,
                      count_gain: bool = True) -> None:
        end = self.report.percent
        self.iterations.append(IterationRecord(index=index, start_percent=start, end_percent=end,
                                               accepted=accepted, rejected=rejected, deferred=deferred))
        if count_gain:
            self.gains.append(round(end - start, 2))
        await self.emit("iteration_completed", {"index": index, "start_percent": start, "end_percent": end,
                                                "accepted": accepted, "rejected": rejected, "deferred": deferred})

    def _check(self) -> None:
        if self.cancel.is_set():
            raise Cancelled()
        if self.tokens.total >= self.opts.max_llm_tokens:
            raise LLMBudgetExhausted("Reached this job's token budget (max_llm_tokens).")

    def _reserve(self) -> None:
        """Check the job budget and reserve one call's worth, atomically (no await in between). Calls in flight
        count with their reservation; with none in flight this is exactly the check `_check` makes."""
        if self.tokens.total + self._reserved >= self.opts.max_llm_tokens:
            exhausted = LLMBudgetExhausted("Reached this job's token budget (max_llm_tokens).")
            exhausted.local = True  # refused before Groq was contacted
            raise exhausted
        self._reserved += self.call_reservation

    async def _call(self, role: str, item: PlanItem, coro: Coroutine[Any, Any, tuple[TestSnippet, TokenUsage]],
                    track_outage: bool = True) -> TestSnippet:
        """`track_outage=False`: a parallel writer; `_write_round` applies the outage bookkeeping in plan order."""
        try:
            self._reserve()
        except LLMBudgetExhausted:
            coro.close()  # never started
            raise
        started = self.clock()
        try:
            snip, usage = await coro
        except LLMError as e:
            self._reserved -= self.call_reservation  # released; what Groq billed is charged instead
            # Groq billed these before the call failed (truncated answers, a schema retry, a timeout after a billed
            # attempt); they are in the daily ledger already and count toward this job's tokens and budget too.
            if e.spent.total > 0:
                await self._charge(role, item, e.spent, failed=True)
            if isinstance(e, LLMCancelled):
                raise Cancelled() from e
            if track_outage:
                self._note_outage(e, started)
            raise
        except BaseException:
            self._reserved -= self.call_reservation
            raise
        # Reconcile: the reservation is replaced by the actual usage (`_charge` adds it before its first await, and
        # reads the answering effort from `agents.last_effort` before any other call can resume and change it).
        self._reserved -= self.call_reservation
        if track_outage:
            self._outage_since, self._outage_failures = None, 0
        await self._charge(role, item, usage)
        return snip

    def _note_outage(self, e: BaseException, started: float) -> None:
        if isinstance(e, LLMTransportError):
            if self._outage_since is None:
                self._outage_since = started
        elif isinstance(e, LLMError) and not e.local:  # Groq answered (with an error about this request): outage over
            self._outage_since, self._outage_failures = None, 0

    def _write(self, item: PlanItem, inputs: Any) -> Coroutine[Any, Any, tuple[TestSnippet, TokenUsage]]:
        on_request = self._on_request("writer", item)
        if self.parallel:  # other writers work on the same package at the same time: ask for distinct names
            return self.deps.agents.write(item, inputs, on_request=on_request, parallel=True)
        return self.deps.agents.write(item, inputs, on_request=on_request)

    async def _write_round(self, items: list[PlanItem]) -> list[_Written]:
        """Send every writer request of the round at once, each built from the round-start state. Each request
        reserves its share of the job budget, and charges and reports its own tokens when it answers."""
        self._check()

        async def write(item: PlanItem) -> _Written:
            out = _Written()
            # rate_limited events of this request name its item, so the UI pauses only that one (a task's own context)
            LLM_CALL.set({"index": self.index, "file": item.file, "role": "writer"})
            try:
                if self.cancel.is_set():  # Cancel pressed before this request went out: never send it
                    raise Cancelled()
                inputs = await self.deps.contexts.inputs_for(item, self.report)
                if self.cancel.is_set():
                    raise Cancelled()
                out.started = self.clock()
                out.snip = await self._call("writer", item, self._write(item, inputs), track_outage=False)
            except (LLMError, ContextTooLarge, Cancelled) as e:
                out.error = e
            return out

        tasks = [asyncio.ensure_future(write(item)) for item in items]
        try:
            written = list(await asyncio.gather(*tasks))
        except BaseException:  # e.g. the job task itself was cancelled: never leave a request running
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise
        if self.cancel.is_set() or any(isinstance(w.error, Cancelled) for w in written):
            raise Cancelled()
        for w in written:  # the outage bookkeeping `_call` does, in plan order so it never depends on timing
            if w.error is None:
                self._outage_since, self._outage_failures = None, 0
            else:
                self._note_outage(w.error, w.started)
        return written

    async def _back_off(self) -> None:
        """After a transport failure: stop the run once Groq has been unreachable for the outage window, else wait
        (15 s, doubling, at most 120 s) before the next item."""
        assert self._outage_since is not None
        elapsed = self.clock() - self._outage_since
        if elapsed >= self.unavailable_after_s:
            raise GroqUnreachable(elapsed)
        self._outage_failures += 1
        wait = min(OUTAGE_BACKOFF_S * 2 ** (self._outage_failures - 1), OUTAGE_BACKOFF_MAX_S)
        await self.emit("llm_unreachable", {"seconds": wait, "unreachable_s": round(elapsed, 1)})
        if self._sleep is not None:
            await self._sleep(wait)
        else:
            try:  # wake up at once on Cancel
                await asyncio.wait_for(self.cancel.wait(), timeout=wait)
            except asyncio.TimeoutError:
                pass
        if self.cancel.is_set():
            raise Cancelled()

    async def _charge(self, role: str, item: PlanItem, usage: TokenUsage, failed: bool = False) -> None:
        self.tokens = self.tokens.add(usage)
        data: dict[str, Any] = {"index": self.index, "file": item.file, "role": role,
                                "prompt_tokens": usage.prompt_tokens, "completion_tokens": usage.completion_tokens,
                                "total_tokens": self.tokens.total,
                                "reasoning_effort": None if failed else self.deps.agents.last_effort}
        if failed:
            data["failed"] = True  # the call ended in an error; its tokens were billed all the same
        await self.emit("llm_call", data)

    def _on_request(self, role: str, item: PlanItem, attempt: int | None = None) -> OnRequest:
        """Emit `llm_request` right before each Groq request, so the UI can show how long it has been waiting."""
        async def emit(effort: str) -> None:
            data: dict[str, Any] = {"index": self.index, "file": item.file, "role": role, "reasoning_effort": effort}
            if attempt is not None:
                data["attempt"] = attempt
            await self.emit("llm_request", data)
        return emit

    async def _validate(self, base: dict[str, Any], coro: Awaitable[ValidationResult]) -> ValidationResult:
        result = await coro
        if self.cancel.is_set():  # gotools reports a cancelled run as a failure; do not misreport it
            raise Cancelled()
        await self.emit("validation_result", {**base, **result.event()})
        return result

    async def _generated(self, base: dict[str, Any], test_file: str, snip: TestSnippet) -> None:
        await self.emit("candidate_generated", {**base, "test_file": test_file, "code": snip.code,
                                                "test_plan": [s.model_dump() for s in snip.test_plan]})

    async def _model_answer(self, base: dict[str, Any], test_file: str, snip: TestSnippet) -> TestSnippet:
        """Report the model's answer, then clean stray characters from its import paths (no LLM call, no fix attempt)."""
        await self._generated(base, test_file, snip)
        cleaned = clean_imports(snip)
        if cleaned is None:
            return snip
        await self.emit("mechanical_repair", {**base, "repair": 0, "description": cleaned[1]})  # 0: not a numbered repair
        await self._generated(base, test_file, cleaned[0])
        return cleaned[0]

    async def _too_large(self, item: PlanItem, base: dict[str, Any], *, half: bool = False) -> bool:
        """Request or answer too big: retry with fewer functions (one, or the first half), or skip the item for good."""
        if len(item.functions) > 1:
            keep = (len(item.functions) + 1) // 2 if half else 1
            return await self._attempt(item.model_copy(update={"functions": item.functions[:keep]}))
        self.skipped.update(item.functions)
        await self.emit("candidate_rejected", {**base, "reason": "too_large"})
        return False

    async def _attempt(self, item: PlanItem, written: _Written | None = None) -> bool:
        """`written`: the item's writer answer from a parallel round. Its context is built again here from the
        current workspace, so names accepted earlier in the round count for the mechanical rename and the Fixer."""
        if written is None:
            self._check()
        elif self.cancel.is_set():  # the answer is paid for and checking it costs no tokens: only Cancel stops it
            raise Cancelled()
        ws, validator = self.deps.ws, self.deps.validator
        test_file, package = test_path_for(item.file), self.deps.package_of(item.file)
        base = {"index": self.index, "file": item.file}
        try:
            inputs = await self.deps.contexts.inputs_for(item, self.report)
        except ContextTooLarge:
            return await self._too_large(item, base)

        snap = ws.snapshot([test_file, "go.mod", "go.sum"])
        snip: TestSnippet | None = None
        half = transport = False
        history: list[AttemptRecord] = []  # every check of this candidate, oldest first, for the Fixer
        mine: list[Disagreement] = []  # disagreements first recorded by this attempt; their outcome is set at its end
        try:
            try:
                # render_context (inside agents.write) is where ContextTooLarge is actually raised
                if written is None:
                    snip = await self._call("writer", item, self._write(item, inputs))
                elif written.error is not None:
                    raise written.error
                else:
                    snip = written.snip
            except ContextTooLarge:
                too_large = True
            except LLMOutputTooLarge:  # only the writer's answer is split; the fixer's falls through as LLM_ERROR
                too_large, half = True, True
            else:
                too_large = False
                snip = await self._model_answer(base, test_file, snip)
                result = await self._validate(base, validator.validate(test_file, package, snip, self.report))
                history.append(attempt_record("writer", result))
                attempts = repairs = 0
                while not result.accepted:
                    self._check()
                    free = result.no_assertions if result.kind is ValidationKind.NO_ASSERTIONS else []
                    if free and len(free) < len(result.new_tests):  # all of them: the Fixer is told to assert
                        await self.emit("tests_pruned", {**base, "tests": free, "reason": "no_assertions"})
                        result = await self._validate(
                            base, validator.prune_and_check(test_file, free, self.report, result.new_tests))
                        history.append(attempt_record(f"prune of [{', '.join(free)}] (no assertions)", result,
                                                      pruned=free, pruned_reason=ValidationKind.NO_ASSERTIONS.value))
                        if result.accepted:
                            break
                    if result.kind is ValidationKind.TEST_FAILURE:
                        doomed = [n for n in result.failed_tests if n in result.new_tests]
                        if doomed and len(doomed) == len(result.failed_tests) and len(doomed) < len(result.new_tests):
                            found = self._disagreements(item, doomed, result.output, mine)
                            await self.emit("tests_pruned", {**base, "tests": doomed,
                                                             "disagreements": [_event(d) for d in found]})
                            result = await self._validate(
                                base, validator.prune_and_check(test_file, doomed, self.report, result.new_tests))
                            history.append(attempt_record(f"prune of [{', '.join(doomed)}]", result, pruned=doomed))
                            if result.accepted:
                                break
                    if result.kind is ValidationKind.COMPILE_ERROR and repairs < MAX_MECHANICAL_REPAIRS:
                        repaired = mechanical_repair(snip, result.output, package, inputs.declared)
                        if repaired is not None:  # forgotten import / self-qualified name / duplicate test name: no LLM call
                            repairs += 1
                            await self.emit("mechanical_repair", {**base, "repair": repairs, "description": repaired[1]})
                            ws.restore(snap)
                            snip = repaired[0]
                            await self._generated(base, test_file, snip)
                            result = await self._validate(base, validator.validate(test_file, package, snip, self.report))
                            history.append(attempt_record(f"auto_fix: {repaired[1]}", result))
                            continue
                    if attempts >= self.opts.max_fix_attempts:
                        break
                    attempts += 1
                    fixing: dict[str, Any] = {**base, "attempt": attempts, "kind": result.kind.value}
                    failing = [n for n in result.failed_tests if n in result.new_tests]
                    if result.kind is ValidationKind.TEST_FAILURE and failing:  # e.g. every new test failed: no prune
                        found = self._disagreements(item, failing, result.output, mine, pruned=False)
                        fixing["disagreements"] = [_event(d) for d in found]
                    await self.emit("fix_attempt", fixing)
                    ws.restore(snap)
                    snip = await self._call("fixer", item, self.deps.agents.fix(
                        item, inputs, snip, result, list(history), on_request=self._on_request("fixer", item, attempts)))
                    snip = await self._model_answer(base, test_file, snip)
                    result = await self._validate(base, validator.validate(test_file, package, snip, self.report))
                    history.append(attempt_record(f"llm_fix {attempts}", result))
        except (LLMError, ContextTooLarge) as e:
            if isinstance(e, (LLMBudgetExhausted, LLMFatal, LLMCancelled)):
                ws.restore(snap)
                raise
            too_large = False
            transport = isinstance(e, LLMTransportError)
            # a fixer prompt that cannot fit even after degrading is a local check, not a model error
            kind = (ValidationKind.PROMPT_TOO_LARGE if isinstance(e, ContextTooLarge)
                    else ValidationKind.LLM_TIMEOUT if isinstance(e, LLMTimeout)
                    else ValidationKind.LLM_UNAVAILABLE if isinstance(e, LLMUnavailable) else ValidationKind.LLM_ERROR)
            result = ValidationResult(kind, str(e))
            log.warning("%s for %s: %s", kind.value, item.file, e)
            await self.emit("validation_result", {**base, **result.event()})
        except BaseException:  # incl. Cancelled, OSError, asyncio.CancelledError: never leave a candidate behind
            ws.restore(snap)
            raise
        if too_large:
            ws.restore(snap)
            return await self._too_large(item, base, half=half)

        if result.accepted and result.report is not None:
            gain = round(result.report.percent - self.report.percent, 2)
            self.report = result.report
            self.tests_added.extend(result.new_tests)
            if test_file not in self.test_files:
                self.test_files.append(test_file)
            if snip is not None:
                self.bugs.extend(snip.suspected_bugs)
            for d in mine:  # a test of that name in the accepted code was rewritten after it failed (it may now
                if d.test in result.new_tests:  # expect the code's value). Only upgrades: once a test is kept, a
                    d.outcome = "kept"  # later attempt that prunes the same failure does not remove it from the suite
                elif d.outcome == "not_accepted":
                    d.outcome = "dropped"
            accepted: dict[str, Any] = {**base, "test_file": test_file, "tests": result.new_tests,
                                        "percent": self.report.percent, "gain": gain}
            if snip is not None and snip.suspected_bugs:  # where each claim came from, to drop any Go refuted later
                accepted["suspected_bugs"] = [b.model_dump() for b in snip.suspected_bugs]
            await self.emit("candidate_accepted", accepted)
            return True

        ws.restore(snap)
        if transport:  # Groq was unreachable: not this item's fault, so it is planned again in a later round
            self.deferred += 1
            await self.emit("candidate_deferred", {**base, "reason": result.kind.value})
            if not self.parallel:  # a parallel round backs off once, after all its items (see _loop)
                await self._back_off()
            return False
        for key in item.functions:
            self.failed[key] += 1
        await self.emit("candidate_rejected", {**base, "reason": result.kind.value})
        return False

    def _disagreements(self, item: PlanItem, tests: list[str], output: str, mine: list[Disagreement],
                       pruned: bool = True) -> list[Disagreement]:
        """Each failing new test about to be pruned (or, when no prune applies, sent to the Fixer), with its observed
        got/want lines: the model's prediction and the code disagree, and nobody has decided which is wrong.
        Recorded once per (file, test, lines) for the report; a new record starts as `not_accepted`. The record (new,
        or the one an earlier attempt made of the same observation) joins `mine`, whose outcome the attempt upgrades when
        its candidate is accepted (not_accepted -> kept/dropped, dropped -> kept; kept stays kept)."""
        functions = [k.label() for k in item.functions]
        found = [Disagreement(file=item.file, functions=functions, test=t, lines=observed_lines(output, t),
                              pruned=pruned, outcome="not_accepted") for t in tests]
        for d in found:
            record = next((o for o in self.disagreements if (o.file, o.test, o.lines) == (d.file, d.test, d.lines)), None)
            if record is None:
                self.disagreements.append(record := d)
            if not any(m is record for m in mine):
                mine.append(record)
        return found

    def _summary(self, reason: StopReason, detail: str, duration: float, minutes: int = 0) -> Summary:
        before = {f.file: f.percent for f in self.baseline.files}
        per_file = sorted((FileDelta(file=f.file, before=before.get(f.file, 0.0), after=f.percent)
                           for f in self.report.files), key=lambda d: (-(d.after - d.before), d.file))
        return Summary(
            stop_reason=reason, message=stop_message(reason, self.request, detail, minutes=minutes),
            target=self.request.target_coverage, baseline_percent=self.baseline.percent,
            final_percent=self.report.percent, iterations=self.iterations, test_files=sorted(self.test_files),
            tests_added=self.tests_added, suspected_bugs=self.bugs, disagreements=self.disagreements,
            per_file=per_file, tokens=self.tokens,
            duration_s=round(duration, 1),
        )
