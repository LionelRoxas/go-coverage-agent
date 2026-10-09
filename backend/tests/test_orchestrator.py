# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
import asyncio
from types import SimpleNamespace

import pytest

from app.agents.context import ContextTooLarge
from app.engine.orchestrator import Orchestrator, RunDeps
from app.llm.client import LLMBudgetExhausted, LLMError, LLMFatal, LLMOutputTooLarge
from app.models import (CoverageReport, FileCoverage, FuncCoverage, FuncKey, JobOptions, JobRequest, StopReason,
                        TokenUsage)
from app.validator import ValidationKind, ValidationResult
from app.workspace import Workspace
from tests.fakes import snippet

# Toy coverage model: every function has two blocks "<name>:1" and "<name>:2".


def report(covered: set[str], funcs=(("a.go", "A"), ("b.go", "B"))) -> CoverageReport:
    fcs, files = [], {}
    for file, name in funcs:
        n = sum(1 for i in (1, 2) if f"{name}:{i}" in covered)
        fcs.append(FuncCoverage(key=FuncKey(file=file, name=name), statements=2, covered=n,
                                uncovered_lines=[] if n == 2 else [(1, 2)]))
        s, c = files.get(file, (0, 0))
        files[file] = (s + 2, c + n)
    total, cov = 2 * len(funcs), len(covered)
    return CoverageReport(total_statements=total, covered_statements=cov, percent=round(100 * cov / total, 2),
                          files=[FileCoverage(file=f, statements=s, covered=c, percent=round(100 * c / s, 2)) for f, (s, c) in files.items()],
                          functions=fcs, covered_block_ids=sorted(covered))


def accepted(covered, tests=("TestA",), funcs=(("a.go", "A"), ("b.go", "B"))):
    return ValidationResult(ValidationKind.ACCEPTED, report=report(set(covered), funcs), new_tests=list(tests))


class FakeValidator:
    def __init__(self, ws, results, prune_results=()):
        self.ws, self.results, self.prune_results = ws, list(results), list(prune_results)
        self.pruned, self.snips = [], []

    async def validate(self, test_file, package, snip, prev):
        self.snips.append(snip)
        self.ws.write_test(test_file, "package p\n// merged\n")  # simulate gohelper merge
        return self.results.pop(0)

    async def prune_and_check(self, test_file, names, prev, new_tests):
        self.pruned.append(names)
        return self.prune_results.pop(0)


class FakeAgents:
    def __init__(self, writes, fixes=(), too_large_when_multi=False, usage=10):
        self.writes, self.fixes, self.usage = list(writes), list(fixes), usage
        self.write_items, self.fix_kinds, self.histories = [], [], []
        self.too_large_when_multi = too_large_when_multi
        self.last_effort = "medium"

    async def write(self, item, inputs):
        if self.too_large_when_multi and len(item.functions) > 1:
            raise ContextTooLarge("too big")  # the real Agents.write raises it from render_context
        self.write_items.append(item)
        r = self.writes.pop(0)
        if isinstance(r, Exception):
            raise r
        return r, TokenUsage(prompt_tokens=self.usage, completion_tokens=5)

    async def fix(self, item, inputs, snip, result, history=()):
        self.fix_kinds.append(result.kind)
        self.histories.append(list(history))
        r = self.fixes.pop(0)
        if isinstance(r, Exception):
            raise r
        return r, TokenUsage(prompt_tokens=10, completion_tokens=5)


class FakeContexts:
    def __init__(self, declared=()):
        self.declared = list(declared)

    async def inputs_for(self, item, rep):
        return SimpleNamespace(declared=self.declared)


@pytest.fixture
def ws(tmp_path):
    (tmp_path / "repo").mkdir()
    (tmp_path / "scratch").mkdir()
    return Workspace(tmp_path / "repo", tmp_path / "scratch")


def run(ws, validator, agents, target=100.0, contexts=None, cancel=None, **opts):
    events = []

    async def emit(t, d):
        events.append((t, d))

    req = JobRequest(repo_path="x", target_coverage=target, options=JobOptions(**opts))
    deps = RunDeps(ws=ws, validator=validator, agents=agents, contexts=contexts or FakeContexts(),
                   package_of=lambda f: "p")
    orch = Orchestrator(deps, req, emit, cancel or asyncio.Event())
    return orch, events


GOOD = snippet("func TestA(t *testing.T) {}", bugs=[("A", "looks odd")])


async def test_reaches_target_and_records_everything(ws):
    v = FakeValidator(ws, [accepted({"A:1", "A:2"})])
    orch, events = run(ws, v, FakeAgents([GOOD]), target=50)
    summary = await orch.run(report(set()))
    assert summary.stop_reason is StopReason.TARGET_REACHED
    assert summary.final_percent == 50.0 and summary.baseline_percent == 0.0
    assert summary.tests_added == ["TestA"] and summary.test_files == ["a_test.go"]
    assert summary.suspected_bugs[0].function == "A"
    assert summary.iterations[0].accepted == 1
    types = [t for t, _ in events]
    assert types[:3] == ["iteration_started", "plan_created", "llm_call"]
    assert "candidate_accepted" in types and "iteration_completed" in types
    assert ws.read("a_test.go") is not None


async def test_prunes_failing_new_tests_without_calling_fixer(ws):
    failing = ValidationResult(ValidationKind.TEST_FAILURE, "--- FAIL: TestBad", failed_tests=["TestBad"],
                               new_tests=["TestGood", "TestBad"])
    v = FakeValidator(ws, [failing], prune_results=[accepted({"A:1"}, tests=["TestGood"])])
    agents = FakeAgents([GOOD])
    orch, events = run(ws, v, agents, target=25)
    summary = await orch.run(report(set()))
    assert v.pruned == [["TestBad"]] and agents.fix_kinds == []
    assert summary.tests_added == ["TestGood"]
    assert ("tests_pruned", {"index": 1, "file": "a.go", "tests": ["TestBad"]}) in events


async def test_fixer_then_rejection_rolls_back_and_eventually_gives_up(ws):
    bad = ValidationResult(ValidationKind.COMPILE_ERROR, "undefined: x")
    v = FakeValidator(ws, [bad, bad, bad, bad])
    agents = FakeAgents([GOOD, GOOD], fixes=[GOOD, GOOD])
    orch, events = run(ws, v, agents, max_fix_attempts=1, patience=5, targets_per_iteration=1)
    summary = await orch.run(report(set(), funcs=(("a.go", "A"),)))
    assert agents.fix_kinds == [ValidationKind.COMPILE_ERROR, ValidationKind.COMPILE_ERROR]
    assert summary.stop_reason is StopReason.NO_REMAINING_TARGETS
    assert ws.read("a_test.go") is None, "rejected candidates must be rolled back"
    assert sum(1 for t, _ in events if t == "candidate_rejected") == 2


async def test_marginal_gains_stop(ws):
    funcs10 = tuple((f"f{i}.go", f"F{i}") for i in range(10))  # one accepted block = 5% gain
    v = FakeValidator(ws, [accepted({"F0:1"}, funcs=funcs10)])
    orch, _ = run(ws, v, FakeAgents([GOOD]), min_gain=10, patience=1, targets_per_iteration=1)
    summary = await orch.run(report(set(), funcs=funcs10))
    assert summary.stop_reason is StopReason.MARGINAL_GAINS


async def test_budget_exhaustion_stops_gracefully(ws):
    orch, _ = run(ws, FakeValidator(ws, []), FakeAgents([LLMBudgetExhausted("daily cap hit")]))
    summary = await orch.run(report(set()))
    assert summary.stop_reason is StopReason.BUDGET_EXHAUSTED and "daily cap hit" in summary.message


async def test_llm_fatal_propagates(ws):
    orch, _ = run(ws, FakeValidator(ws, []), FakeAgents([LLMFatal("bad key")]))
    with pytest.raises(LLMFatal):
        await orch.run(report(set()))


async def test_cancel_before_first_attempt(ws):
    cancel = asyncio.Event()
    cancel.set()
    orch, _ = run(ws, FakeValidator(ws, []), FakeAgents([]), cancel=cancel)
    assert (await orch.run(report(set()))).stop_reason is StopReason.CANCELLED


async def test_context_too_large_splits_multi_function_items(ws):
    funcs = (("a.go", "A"), ("a.go", "A2"))
    v = FakeValidator(ws, [accepted({"A:1", "A:2"}, funcs=funcs)])
    agents = FakeAgents([GOOD], too_large_when_multi=True)
    orch, _ = run(ws, v, agents, target=50)
    await orch.run(report(set(), funcs=funcs))
    assert len(agents.write_items[0].functions) == 1


async def test_cancel_during_validation_is_cancelled_not_rejected(ws):
    cancel = asyncio.Event()

    class CancellingValidator(FakeValidator):
        async def validate(self, test_file, package, snip, prev):
            r = await super().validate(test_file, package, snip, prev)
            cancel.set()
            return r

    bad = ValidationResult(ValidationKind.COMPILE_ERROR, "cancelled")
    orch, events = run(ws, CancellingValidator(ws, [bad]), FakeAgents([GOOD]), cancel=cancel, max_fix_attempts=0)
    summary = await orch.run(report(set()))
    assert summary.stop_reason is StopReason.CANCELLED
    assert not any(t == "candidate_rejected" for t, _ in events)
    assert ws.read("a_test.go") is None


async def test_unexpected_error_rolls_back_and_propagates(ws):
    class Boom(FakeValidator):
        async def validate(self, test_file, package, snip, prev):
            self.ws.write_test(test_file, "package p\n// merged\n")
            raise RuntimeError("disk on fire")

    orch, _ = run(ws, Boom(ws, []), FakeAgents([GOOD]))
    with pytest.raises(RuntimeError):
        await orch.run(report(set()))
    assert ws.read("a_test.go") is None


async def test_prunes_even_when_no_fix_attempts_allowed(ws):
    failing = ValidationResult(ValidationKind.TEST_FAILURE, "--- FAIL: TestBad", failed_tests=["TestBad"],
                               new_tests=["TestGood", "TestBad"])
    v = FakeValidator(ws, [failing], prune_results=[accepted({"A:1"}, tests=["TestGood"])])
    agents = FakeAgents([GOOD])
    orch, _ = run(ws, v, agents, target=25, max_fix_attempts=0)
    summary = await orch.run(report(set()))
    assert v.pruned == [["TestBad"]] and agents.fix_kinds == []
    assert summary.tests_added == ["TestGood"]


async def test_fixer_llm_error_rejects_and_rolls_back(ws):
    bad = ValidationResult(ValidationKind.COMPILE_ERROR, "undefined: x")
    agents = FakeAgents([GOOD], fixes=[LLMError("schema failure")])
    orch, events = run(ws, FakeValidator(ws, [bad]), agents, max_fix_attempts=1, targets_per_iteration=1,
                       max_iterations=1)
    await orch.run(report(set(), funcs=(("a.go", "A"),)))
    assert ("candidate_rejected", {"index": 1, "file": "a.go", "reason": "llm_error"}) in events
    assert ws.read("a_test.go") is None


async def test_writer_llm_error_records_its_cause_before_rejection(ws):
    msg = "model output does not match TestSnippet (3 errors)"
    agents = FakeAgents([LLMError(msg)])
    orch, events = run(ws, FakeValidator(ws, []), agents, targets_per_iteration=1, max_iterations=1)
    await orch.run(report(set(), funcs=(("a.go", "A"),)))
    cause = ("validation_result", {"index": 1, "file": "a.go", "kind": "llm_error", "output": msg, "failed_tests": []})
    rejected = ("candidate_rejected", {"index": 1, "file": "a.go", "reason": "llm_error"})
    assert cause in events
    assert events.index(cause) < events.index(rejected)


async def test_job_token_budget_stops_run(ws):
    bad = ValidationResult(ValidationKind.COMPILE_ERROR, "undefined: x")
    agents = FakeAgents([GOOD], usage=20_000)
    orch, _ = run(ws, FakeValidator(ws, [bad]), agents, max_fix_attempts=1, max_llm_tokens=10_000)
    summary = await orch.run(report(set()))
    assert summary.stop_reason is StopReason.BUDGET_EXHAUSTED
    assert ws.read("a_test.go") is None


async def test_missing_import_is_repaired_without_calling_fixer(ws):
    bad = ValidationResult(ValidationKind.COMPILE_ERROR, "./a_test.go:5:2: undefined: errors")
    v = FakeValidator(ws, [bad, accepted({"A:1", "A:2"})])
    agents = FakeAgents([GOOD])
    orch, events = run(ws, v, agents, target=50, max_fix_attempts=0)
    summary = await orch.run(report(set()))
    assert agents.fix_kinds == [] and summary.tests_added == ["TestA"]
    assert v.snips[1].imports == ["testing", "errors"]
    assert ("mechanical_repair", {"index": 1, "file": "a.go", "repair": 1, "description": "added import errors"}) in events
    assert sum(1 for t, _ in events if t == "llm_call") == 1


async def test_mechanical_repair_is_bounded_and_falls_back_to_fixer(ws):
    bad = ValidationResult(ValidationKind.COMPILE_ERROR, "./a_test.go:5:2: undefined: errors")
    other = ValidationResult(ValidationKind.COMPILE_ERROR, "./a_test.go:9:1: undefined: foo")
    v = FakeValidator(ws, [bad, other, accepted({"A:1", "A:2"})])
    agents = FakeAgents([GOOD], fixes=[GOOD])
    orch, _ = run(ws, v, agents, target=50, max_fix_attempts=1)
    summary = await orch.run(report(set()))
    assert agents.fix_kinds == [ValidationKind.COMPILE_ERROR] and summary.tests_added == ["TestA"]


async def test_mechanical_repair_cap_then_fixer(ws):
    from app.engine.orchestrator import MAX_MECHANICAL_REPAIRS
    mods = ["errors", "sort", "strings", "fmt", "bytes"]
    bads = [ValidationResult(ValidationKind.COMPILE_ERROR, f"undefined: {m}") for m in mods[:MAX_MECHANICAL_REPAIRS + 1]]
    v = FakeValidator(ws, [*bads, accepted({"A:1", "A:2"})])
    agents = FakeAgents([GOOD], fixes=[GOOD])
    orch, events = run(ws, v, agents, target=50, max_fix_attempts=1)
    summary = await orch.run(report(set()))
    assert sum(1 for t, _ in events if t == "mechanical_repair") == MAX_MECHANICAL_REPAIRS
    assert agents.fix_kinds == [ValidationKind.COMPILE_ERROR] and summary.tests_added == ["TestA"]


async def test_output_too_large_retries_with_first_half(ws):
    funcs = tuple(("a.go", n) for n in ("A", "A2", "A3", "A4"))
    v = FakeValidator(ws, [accepted({"A:1", "A:2"}, funcs=funcs)])
    agents = FakeAgents([LLMOutputTooLarge("truncated"), GOOD])
    orch, _ = run(ws, v, agents, target=25, targets_per_iteration=1, max_iterations=1)
    await orch.run(report(set(), funcs=funcs))
    assert [len(i.functions) for i in agents.write_items] == [4, 2]
    assert [k.name for k in agents.write_items[1].functions] == ["A", "A2"]


async def test_output_too_large_on_single_function_is_skipped_too_large(ws):
    agents = FakeAgents([LLMOutputTooLarge("truncated")])
    orch, events = run(ws, FakeValidator(ws, []), agents, targets_per_iteration=1, max_iterations=1)
    await orch.run(report(set(), funcs=(("a.go", "A"),)))
    assert ("candidate_rejected", {"index": 1, "file": "a.go", "reason": "too_large"}) in events
    assert FuncKey(file="a.go", name="A") in orch.skipped


async def test_fixer_output_too_large_stays_llm_error(ws):
    bad = ValidationResult(ValidationKind.COMPILE_ERROR, "undefined: x")
    agents = FakeAgents([GOOD], fixes=[LLMOutputTooLarge("truncated")])
    orch, events = run(ws, FakeValidator(ws, [bad]), agents, max_fix_attempts=1, targets_per_iteration=1,
                       max_iterations=1)
    await orch.run(report(set(), funcs=(("a.go", "A"),)))
    assert ("candidate_rejected", {"index": 1, "file": "a.go", "reason": "llm_error"}) in events


async def test_duplicate_test_name_is_renamed_without_calling_fixer(ws):
    dup = ValidationResult(ValidationKind.COMPILE_ERROR, "gohelper: duplicate declaration: TestA")
    v = FakeValidator(ws, [dup, accepted({"A:1", "A:2"}, tests=["TestA_3"])])
    agents = FakeAgents([GOOD])
    orch, events = run(ws, v, agents, target=50, max_fix_attempts=0, contexts=FakeContexts(["TestA", "TestA_2"]))
    summary = await orch.run(report(set()))
    assert agents.fix_kinds == [] and summary.tests_added == ["TestA_3"]
    assert v.snips[1].code == "func TestA_3(t *testing.T) {}"
    assert ("mechanical_repair", {"index": 1, "file": "a.go", "repair": 1,
                                  "description": "renamed duplicate test TestA to TestA_3"}) in events


async def test_duplicate_helper_goes_to_the_fixer(ws):
    dup = ValidationResult(ValidationKind.COMPILE_ERROR, "gohelper: duplicate declaration: approxEqual")
    helper = snippet("func approxEqual(a, b float64) bool { return a == b }")
    v = FakeValidator(ws, [dup, accepted({"A:1", "A:2"})])
    agents = FakeAgents([helper], fixes=[GOOD])
    orch, events = run(ws, v, agents, target=50, max_fix_attempts=1, contexts=FakeContexts(["approxEqual"]))
    await orch.run(report(set()))
    assert agents.fix_kinds == [ValidationKind.COMPILE_ERROR]
    assert not any(t == "mechanical_repair" for t, _ in events)


async def test_fixer_prompt_too_large_is_not_a_model_error(ws):
    bad = ValidationResult(ValidationKind.COMPILE_ERROR, "undefined: x")
    msg = "targets need ~3591 tokens; budget is 2191"
    agents = FakeAgents([GOOD], fixes=[ContextTooLarge(msg)])
    orch, events = run(ws, FakeValidator(ws, [bad]), agents, max_fix_attempts=1, targets_per_iteration=1,
                       max_iterations=1)
    await orch.run(report(set(), funcs=(("a.go", "A"),)))
    assert ("validation_result", {"index": 1, "file": "a.go", "kind": "prompt_too_large", "output": msg,
                                  "failed_tests": []}) in events
    assert ("candidate_rejected", {"index": 1, "file": "a.go", "reason": "prompt_too_large"}) in events
    assert not any(d.get("kind") == "llm_error" or d.get("reason") == "llm_error" for _, d in events)
    assert ws.read("a_test.go") is None


async def test_repeated_duplicates_stop_after_the_mechanical_cap_then_go_to_the_fixer(ws):
    from app.engine.orchestrator import MAX_MECHANICAL_REPAIRS
    names = ["TestA", "TestB", "TestC", "TestD"]
    many = snippet("\n\n".join(f"func {n}(t *testing.T) {{}}" for n in names))
    dups = [ValidationResult(ValidationKind.COMPILE_ERROR, f"gohelper: duplicate declaration: {n}") for n in names]
    v = FakeValidator(ws, [*dups, accepted({"A:1", "A:2"})])
    agents = FakeAgents([many], fixes=[GOOD])
    orch, events = run(ws, v, agents, target=50, max_fix_attempts=1, contexts=FakeContexts(names))
    summary = await orch.run(report(set()))
    repairs = [d["description"] for t, d in events if t == "mechanical_repair"]
    assert repairs == [f"renamed duplicate test {n} to {n}_2" for n in names[:MAX_MECHANICAL_REPAIRS]]
    assert agents.fix_kinds == [ValidationKind.COMPILE_ERROR] and summary.tests_added == ["TestA"]


# output/7ef641efb870, iteration 7 (constraints.go): go test -count=2 prints every failure twice
EVIDENCE_FAILURE = """--- FAIL: TestParse (0.00s)
    --- FAIL: TestParse/!=_1.x (0.00s)
        constraints_test.go:721: minorDirty = true, want false
--- FAIL: TestNotEqual (0.00s)
    constraints_test.go:772: expected error for minor dirty equality, got nil
--- FAIL: TestParse (0.00s)
    --- FAIL: TestParse/!=_1.x (0.00s)
        constraints_test.go:721: minorDirty = true, want false
--- FAIL: TestNotEqual (0.00s)
    constraints_test.go:772: expected error for minor dirty equality, got nil
FAIL"""
FIX_FAILURE = "--- FAIL: TestMajorX (0.00s)\n    constraints_test.go:702: unexpected dirty flags: dirty=true minorDirty=true\n"
NO_GAIN = ValidationResult(ValidationKind.NO_GAIN, "the new tests executed no previously uncovered statements")


class RealContexts:
    async def inputs_for(self, item, rep):
        from app.agents.context import ContextInputs
        return ContextInputs(module="m", package="p", go_version="1.22", source_file="a.go", test_file="a_test.go",
                             targets=[("A", "func A() {\n\tx := 1  // UNCOVERED\n}")], declared=[], referenced=[],
                             existing_tests=[])


async def test_fixer_sees_the_assertion_failures_that_pruning_hid(ws):
    """writer -> test_failure -> prune -> no_gain -> fixer -> test_failure -> prune -> no_gain -> fixer: each fixer
    prompt carries the earlier observed values, not just "no new coverage"."""
    from app.agents.llm_agents import PRUNED_NO_GAIN, Agents
    from tests.fakes import FakeLLM
    first = ValidationResult(ValidationKind.TEST_FAILURE, EVIDENCE_FAILURE, failed_tests=["TestParse", "TestNotEqual"],
                             new_tests=["TestParse", "TestNotEqual", "TestOther"])
    second = ValidationResult(ValidationKind.TEST_FAILURE, FIX_FAILURE, failed_tests=["TestMajorX"],
                              new_tests=["TestMajorX", "TestOther"])
    v = FakeValidator(ws, [first, second, accepted({"A:1", "A:2"})], prune_results=[NO_GAIN, NO_GAIN])
    llm = FakeLLM([GOOD, GOOD, GOOD])
    orch, _ = run(ws, v, Agents(llm, max_prompt_tokens=12_000), target=50, max_fix_attempts=2,
                  targets_per_iteration=1, contexts=RealContexts())
    summary = await orch.run(report(set()))
    assert summary.final_percent == 50.0
    fixes = [c["user"] for c in llm.calls if c["role"] == "fixer"]
    assert len(fixes) == 2
    assert "TestParse/!=_1.x: constraints_test.go:721: minorDirty = true, want false" in fixes[0]
    assert "TestNotEqual: constraints_test.go:772: expected error for minor dirty equality, got nil" in fixes[0]
    assert "1. writer -> test_failure\n" in fixes[0] and PRUNED_NO_GAIN in fixes[0]
    assert "minorDirty = true, want false" in fixes[1] and "unexpected dirty flags: dirty=true minorDirty=true" in fixes[1]
    assert "2. prune of [TestParse, TestNotEqual] -> no_gain" in fixes[1] and "3. llm_fix 1 -> test_failure" in fixes[1]


async def test_history_records_each_check_with_its_source(ws):
    failing = ValidationResult(ValidationKind.TEST_FAILURE, EVIDENCE_FAILURE, failed_tests=["TestParse"],
                               new_tests=["TestParse", "TestOther"])
    missing = ValidationResult(ValidationKind.COMPILE_ERROR, "./a_test.go:3:2: undefined: strings")
    v = FakeValidator(ws, [missing, failing, accepted({"A:1", "A:2"})], prune_results=[NO_GAIN])
    agents = FakeAgents([snippet("func TestA(t *testing.T) { strings.ToLower(\"\") }")], fixes=[GOOD])
    orch, _ = run(ws, v, agents, target=50, max_fix_attempts=1, targets_per_iteration=1)
    await orch.run(report(set()))
    [history] = agents.histories
    assert [r.source for r in history] == ["writer", "auto_fix: added import strings",
                                           "prune of [TestParse]"]
    assert [r.kind for r in history] == ["compile_error", "test_failure", "no_gain"]
    assert history[-1].pruned == ("TestParse",)


async def test_llm_call_event_carries_the_reasoning_effort(ws):
    v = FakeValidator(ws, [accepted({"A:1", "A:2"})])
    orch, events = run(ws, v, FakeAgents([GOOD]), target=50)
    await orch.run(report(set()))
    [call] = [d for t, d in events if t == "llm_call"]
    assert call["reasoning_effort"] == "medium" and call["role"] == "writer"
