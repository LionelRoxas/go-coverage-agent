# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
import asyncio
from types import SimpleNamespace

import pytest

from app.agents.context import ContextTooLarge
from app.engine.orchestrator import Orchestrator, RunDeps
from app.llm.client import LLMBudgetExhausted, LLMError, LLMFatal, LLMOutputTooLarge, LLMTimeout, LLMUnavailable
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

    async def write(self, item, inputs, on_request=None):
        if self.too_large_when_multi and len(item.functions) > 1:
            raise ContextTooLarge("too big")  # the real Agents.write raises it from render_context
        self.write_items.append(item)
        if on_request is not None:
            await on_request("medium")
        r = self.writes.pop(0)
        if isinstance(r, Exception):
            raise r
        return r, TokenUsage(prompt_tokens=self.usage, completion_tokens=5)

    async def fix(self, item, inputs, snip, result, history=(), on_request=None):
        self.fix_kinds.append(result.kind)
        self.histories.append(list(history))
        if on_request is not None:
            await on_request("high")
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
    orch = Orchestrator(deps, req, emit, cancel or asyncio.Event(), sleep=_no_sleep)
    return orch, events


async def _no_sleep(seconds):
    pass


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
    assert types[:4] == ["iteration_started", "plan_created", "llm_request", "llm_call"]
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
    [pruned] = [d for t, d in events if t == "tests_pruned"]
    assert pruned["tests"] == ["TestBad"] and (pruned["index"], pruned["file"]) == (1, "a.go")


TTEST_OUTPUT = """--- FAIL: TestTTest_ErrorsAndEdgeCases (0.00s)
    --- FAIL: TestTTest_ErrorsAndEdgeCases/equal_means (0.00s)
        ttest_test.go:41: t statistic = 0.5477225575051661, want 0
--- FAIL: TestTTest_ErrorsAndEdgeCases (0.00s)
    --- FAIL: TestTTest_ErrorsAndEdgeCases/equal_means (0.00s)
        ttest_test.go:41: t statistic = 0.5477225575051661, want 0
FAIL
"""


async def test_a_pruned_failing_test_is_recorded_as_a_prediction_disagreement(ws):
    failing = ValidationResult(ValidationKind.TEST_FAILURE, TTEST_OUTPUT, failed_tests=["TestTTest_ErrorsAndEdgeCases"],
                               new_tests=["TestGood", "TestTTest_ErrorsAndEdgeCases"])
    v = FakeValidator(ws, [failing], prune_results=[accepted({"A:1"}, tests=["TestGood"])])
    orch, events = run(ws, v, FakeAgents([GOOD]), target=25)
    summary = await orch.run(report(set()))
    expected = {"file": "a.go", "functions": ["A"], "test": "TestTTest_ErrorsAndEdgeCases",
                "lines": ["TestTTest_ErrorsAndEdgeCases/equal_means: ttest_test.go:41: t statistic = 0.5477225575051661, "
                          "want 0"]}  # once, although -count=2 prints it twice
    [pruned] = [d for t, d in events if t == "tests_pruned"]
    assert pruned == {"index": 1, "file": "a.go", "tests": ["TestTTest_ErrorsAndEdgeCases"], "disagreements": [expected]}
    assert [d.model_dump() for d in summary.disagreements] == [{**expected, "pruned": True, "outcome": "dropped"}]
    assert summary.tests_added == ["TestGood"]  # the disagreement is reported, not kept as a test


async def test_a_disagreement_whose_test_a_fix_rewrote_and_kept_says_so(ws):
    """Pruning left no gain, so the Fixer rewrote the failing test (told to adopt the observed value) and it was
    accepted: the disagreement stays listed, as kept."""
    failing = ValidationResult(ValidationKind.TEST_FAILURE, TTEST_OUTPUT, failed_tests=["TestTTest_ErrorsAndEdgeCases"],
                               new_tests=["TestGood", "TestTTest_ErrorsAndEdgeCases"])
    no_gain = ValidationResult(ValidationKind.NO_GAIN, "no new statements", new_tests=["TestGood"])
    v = FakeValidator(ws, [failing, accepted({"A:1"}, tests=["TestGood", "TestTTest_ErrorsAndEdgeCases"])],
                      prune_results=[no_gain])
    agents = FakeAgents([GOOD], fixes=[GOOD])
    orch, events = run(ws, v, agents, target=25)
    summary = await orch.run(report(set()))
    assert agents.fix_kinds == [ValidationKind.NO_GAIN]
    [d] = summary.disagreements
    assert (d.test, d.pruned, d.outcome) == ("TestTTest_ErrorsAndEdgeCases", True, "kept")
    [pruned] = [x for t, x in events if t == "tests_pruned"]
    assert "outcome" not in pruned["disagreements"][0]  # not known when the event is sent


async def test_when_every_new_test_fails_the_failures_sent_to_the_fixer_are_disagreements_too(ws):
    failing = ValidationResult(ValidationKind.TEST_FAILURE, TTEST_OUTPUT, failed_tests=["TestTTest_ErrorsAndEdgeCases"],
                               new_tests=["TestTTest_ErrorsAndEdgeCases"])
    v = FakeValidator(ws, [failing, failing, failing])  # the Fixer repeats the same failing expectation twice
    agents = FakeAgents([GOOD], fixes=[GOOD, GOOD])
    orch, events = run(ws, v, agents, max_iterations=1, targets_per_iteration=1)
    summary = await orch.run(report(set(), funcs=(("a.go", "A"),)))
    assert v.pruned == [] and agents.fix_kinds == [ValidationKind.TEST_FAILURE] * 2
    [d] = summary.disagreements  # the same observation twice is listed once
    assert (d.test, d.pruned, d.outcome) == ("TestTTest_ErrorsAndEdgeCases", False, "not_accepted")
    assert d.lines == ["TestTTest_ErrorsAndEdgeCases/equal_means: ttest_test.go:41: t statistic = 0.5477225575051661, "
                       "want 0"]
    fixes = [x for t, x in events if t == "fix_attempt"]
    assert [f["disagreements"][0]["test"] for f in fixes] == ["TestTTest_ErrorsAndEdgeCases"] * 2
    assert all("pruned" not in f["disagreements"][0] for f in fixes)


async def test_a_compile_error_sent_to_the_fixer_is_no_disagreement(ws):
    bad = ValidationResult(ValidationKind.COMPILE_ERROR, "undefined: x")
    v = FakeValidator(ws, [bad, accepted({"A:1"})])
    orch, events = run(ws, v, FakeAgents([GOOD], fixes=[GOOD]), target=25)
    summary = await orch.run(report(set()))
    assert summary.disagreements == []
    assert all("disagreements" not in x for t, x in events if t == "fix_attempt")


async def test_disagreement_lines_are_capped(ws):
    long = "--- FAIL: TestBad (0.00s)\n    a_test.go:3: got " + "x" * 1000 + ", want y\n"
    failing = ValidationResult(ValidationKind.TEST_FAILURE, long, failed_tests=["TestBad"],
                               new_tests=["TestGood", "TestBad"])
    v = FakeValidator(ws, [failing], prune_results=[accepted({"A:1"}, tests=["TestGood"])])
    orch, _ = run(ws, v, FakeAgents([GOOD]), target=25)
    summary = await orch.run(report(set()))
    [line] = summary.disagreements[0].lines
    assert len(line) == 300 and line.startswith("TestBad: a_test.go:3: got xxx") and line.endswith("…")


async def test_no_disagreements_when_every_test_passes(ws):
    orch, events = run(ws, FakeValidator(ws, [accepted({"A:1"})]), FakeAgents([GOOD]), target=25)
    summary = await orch.run(report(set()))
    assert summary.disagreements == [] and "tests_pruned" not in [t for t, _ in events]


async def test_assertion_free_removals_are_not_disagreements(ws):
    v = FakeValidator(ws, [assertion_free(["TestNoCheck"], ["TestGood", "TestNoCheck"])],
                      prune_results=[accepted({"A:1"}, tests=["TestGood"])])
    orch, events = run(ws, v, FakeAgents([GOOD]), target=25)
    summary = await orch.run(report(set()))
    assert v.pruned == [["TestNoCheck"]] and summary.disagreements == []
    assert all("disagreements" not in d for t, d in events if t == "tests_pruned")


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


# job 86b6d88b558c: `testing\` in the Writer's imports was rejected by the guard and sent to the Fixer
async def test_stray_characters_in_imports_are_cleaned_before_the_first_check(ws):
    stray = snippet("func TestA(t *testing.T) {}", imports=("testing\\",))
    v = FakeValidator(ws, [accepted({"A:1", "A:2"})])
    agents = FakeAgents([stray])
    orch, events = run(ws, v, agents, target=50, max_fix_attempts=1)
    summary = await orch.run(report(set()))
    assert agents.fix_kinds == [] and summary.tests_added == ["TestA"]
    assert [s.imports for s in v.snips] == [["testing"]]
    assert ("mechanical_repair", {"index": 1, "file": "a.go", "repair": 0,
                                  "description": "cleaned import path 'testing\\' → 'testing'"}) in events
    types = [t for t, _ in events]
    i = types.index("mechanical_repair")
    assert types[i - 1:i + 3] == ["candidate_generated", "mechanical_repair", "candidate_generated", "validation_result"]
    assert sum(1 for t in types if t == "llm_call") == 1


async def test_fixer_answer_is_cleaned_too_and_cleanups_are_not_numbered_repairs(ws):
    bad = ValidationResult(ValidationKind.COMPILE_ERROR, "undefined: x")
    stray = snippet("func TestA(t *testing.T) {}", imports=('"testing"',))
    v = FakeValidator(ws, [bad, accepted({"A:1", "A:2"})])
    agents = FakeAgents([stray], fixes=[stray])
    orch, events = run(ws, v, agents, target=50, max_fix_attempts=1)
    await orch.run(report(set()))
    assert [s.imports for s in v.snips] == [["testing"], ["testing"]]
    assert [d["repair"] for t, d in events if t == "mechanical_repair"] == [0, 0]


async def test_llm_request_is_emitted_before_each_call(ws):
    bad = ValidationResult(ValidationKind.COMPILE_ERROR, "undefined: x")
    v = FakeValidator(ws, [bad, accepted({"A:1", "A:2"})])
    orch, events = run(ws, v, FakeAgents([GOOD], fixes=[GOOD]), target=50, max_fix_attempts=1)
    await orch.run(report(set()))
    calls = [(t, d) for t, d in events if t in ("llm_request", "llm_call")]
    assert [t for t, _ in calls] == ["llm_request", "llm_call", "llm_request", "llm_call"]
    assert calls[0][1] == {"index": 1, "file": "a.go", "role": "writer", "reasoning_effort": "medium"}
    assert calls[2][1] == {"index": 1, "file": "a.go", "role": "fixer", "reasoning_effort": "high", "attempt": 1}


async def test_a_groq_timeout_is_recorded_as_llm_timeout(ws):
    msg = "Groq did not answer within 240 s, twice"
    v = FakeValidator(ws, [accepted({"A:1", "A:2"}, funcs=ONE)])
    orch, events = run(ws, v, FakeAgents([LLMTimeout(msg), GOOD]), targets_per_iteration=1, max_iterations=1)
    await orch.run(report(set(), funcs=ONE))
    assert ("validation_result", {"index": 1, "file": "a.go", "kind": "llm_timeout", "output": msg,
                                  "failed_tests": []}) in events
    assert ("candidate_deferred", {"index": 1, "file": "a.go", "reason": "llm_timeout"}) in events


async def test_a_timeout_retried_at_low_effort_is_not_a_fix_attempt(ws, tmp_path):
    from app.agents.llm_agents import Agents
    from app.config import Settings
    from app.llm.client import GroqLLM
    from app.llm.limits import RateLimiter, UsageLedger
    from tests.test_llm_agents import INPUTS
    from tests.test_llm_client import Completion, FakeGroq, Raw, _timeout

    class Contexts:
        async def inputs_for(self, item, rep):
            return INPUTS

    fake = FakeGroq([_timeout(), Raw(Completion(GOOD.model_dump_json(), "stop"))])
    llm = GroqLLM(Settings(groq_api_key="k"), UsageLedger(tmp_path / "u.json", 1_000_000), RateLimiter(), client=fake)
    v = FakeValidator(ws, [accepted({"A:1", "A:2"})])
    orch, events = run(ws, v, Agents(llm, 12000), target=50, max_fix_attempts=1, contexts=Contexts())
    summary = await orch.run(report(set()))
    assert summary.tests_added == ["TestA"]
    assert [d["reasoning_effort"] for t, d in events if t == "llm_request"] == ["medium", "low"]
    assert [d["reasoning_effort"] for t, d in events if t == "llm_call"] == ["low"]
    assert not any(t == "fix_attempt" for t, _ in events)


def billed(error, prompt=1000, completion=500):
    """An LLM error carrying the tokens Groq billed before it (as GroqLLM attaches them)."""
    error.spent = TokenUsage(prompt_tokens=prompt, completion_tokens=completion)
    return error


async def test_tokens_billed_by_a_failed_writer_call_are_charged(ws):
    funcs = (("a.go", "A"), ("a.go", "A2"))
    v = FakeValidator(ws, [accepted({"A:1", "A:2"}, funcs=funcs)])
    agents = FakeAgents([billed(LLMOutputTooLarge("truncated")), GOOD])
    orch, events = run(ws, v, agents, target=50, targets_per_iteration=1, max_iterations=1)
    summary = await orch.run(report(set(), funcs=funcs))
    assert summary.tokens == TokenUsage(prompt_tokens=1010, completion_tokens=505)
    calls = [d for t, d in events if t == "llm_call"]
    assert [(d["role"], d["prompt_tokens"], d["completion_tokens"], d["total_tokens"], d.get("failed")) for d in calls] == [
        ("writer", 1000, 500, 1500, True), ("writer", 10, 5, 1515, None)]


async def test_tokens_billed_by_a_failed_fixer_call_are_charged(ws):
    bad = ValidationResult(ValidationKind.COMPILE_ERROR, "undefined: x")
    agents = FakeAgents([GOOD], fixes=[billed(LLMError("schema failure"), 200, 100)])
    orch, events = run(ws, FakeValidator(ws, [bad]), agents, max_fix_attempts=1, targets_per_iteration=1,
                       max_iterations=1)
    summary = await orch.run(report(set(), funcs=(("a.go", "A"),)))
    assert summary.tokens == TokenUsage(prompt_tokens=210, completion_tokens=105)
    assert [d["total_tokens"] for t, d in events if t == "llm_call"] == [15, 315]


async def test_billed_tokens_of_failed_calls_count_toward_the_job_budget(ws):
    agents = FakeAgents([billed(LLMTimeout("slow"), 8000, 4000), GOOD])
    orch, _ = run(ws, FakeValidator(ws, []), agents, max_llm_tokens=10_000)
    summary = await orch.run(report(set()))
    assert summary.stop_reason is StopReason.BUDGET_EXHAUSTED
    assert summary.tokens.total == 12_000


async def test_tokens_billed_before_budget_exhaustion_are_charged(ws):
    orch, _ = run(ws, FakeValidator(ws, []), FakeAgents([billed(LLMBudgetExhausted("daily cap hit"), 30, 20)]))
    summary = await orch.run(report(set()))
    assert summary.stop_reason is StopReason.BUDGET_EXHAUSTED and summary.tokens.total == 50


class FakeTime:
    """A clock that only moves while the orchestrator backs off."""
    def __init__(self):
        self.now, self.slept = 0.0, []

    def clock(self):
        return self.now

    async def sleep(self, seconds):
        self.slept.append(seconds)
        self.now += seconds


def run_timed(ws, validator, agents, **opts):
    t = FakeTime()
    events = []

    async def emit(kind, data):
        events.append((kind, data))

    req = JobRequest(repo_path="x", target_coverage=opts.pop("target", 100.0), options=JobOptions(**opts))
    deps = RunDeps(ws=ws, validator=validator, agents=agents, contexts=FakeContexts(), package_of=lambda f: "p")
    return Orchestrator(deps, req, emit, asyncio.Event(), clock=t.clock, sleep=t.sleep), events, t


ONE = (("a.go", "A"),)


@pytest.mark.parametrize("outage", [LLMUnavailable("Groq is unreachable: 503"), LLMTimeout("slow, twice")])
async def test_a_groq_outage_does_not_burn_the_target_and_it_is_retried_later(ws, outage):
    v = FakeValidator(ws, [accepted({"A:1", "A:2"}, funcs=ONE)])
    orch, events, t = run_timed(ws, v, FakeAgents([outage, GOOD]), targets_per_iteration=1, patience=1)
    summary = await orch.run(report(set(), funcs=ONE))
    assert summary.stop_reason is StopReason.TARGET_REACHED  # an outage-only round is not a marginal gain
    assert len(agents_items := v.snips) == 1 and agents_items[0] == GOOD
    assert not orch.failed and t.slept == [15.0]
    assert ("llm_unreachable", {"seconds": 15.0, "unreachable_s": 0.0}) in events
    reason = "llm_timeout" if isinstance(outage, LLMTimeout) else "llm_unavailable"
    assert ("candidate_deferred", {"index": 1, "file": "a.go", "reason": reason}) in events
    assert not any(kind == "candidate_rejected" for kind, _ in events)  # deferred, not rejected
    first = summary.iterations[0]
    assert (first.accepted, first.rejected, first.deferred) == (0, 0, 1)
    assert ("validation_result", {"index": 1, "file": "a.go", "kind": reason, "output": str(outage),
                                  "failed_tests": []}) in events


async def test_outage_only_rounds_do_not_use_up_max_iterations(ws):
    v = FakeValidator(ws, [accepted({"A:1", "A:2"}, funcs=ONE)])
    orch, _, _ = run_timed(ws, v, FakeAgents([LLMUnavailable("down"), LLMUnavailable("down"), GOOD]),
                           targets_per_iteration=1, max_iterations=1)
    summary = await orch.run(report(set(), funcs=ONE))
    assert summary.stop_reason is StopReason.TARGET_REACHED
    assert [i.index for i in summary.iterations] == [1, 2, 3]


async def test_an_error_raised_before_groq_was_contacted_does_not_end_the_outage(ws):
    local = LLMError("prompt is ~13000 tokens, over the 12000 limit")
    local.local = True
    v = FakeValidator(ws, [accepted({"A:1", "A:2"}, funcs=ONE)])
    agents = FakeAgents([LLMUnavailable("down"), local, LLMUnavailable("down"), GOOD])
    orch, _, t = run_timed(ws, v, agents, targets_per_iteration=1, patience=5)
    await orch.run(report(set(), funcs=ONE))
    assert t.slept == [15.0, 30.0]


async def test_groq_unreachable_past_the_window_stops_with_llm_unavailable(ws):
    agents = FakeAgents([LLMUnavailable("Groq is unreachable") for _ in range(20)])
    orch, events, t = run_timed(ws, FakeValidator(ws, []), agents, targets_per_iteration=1, max_iterations=30)
    summary = await orch.run(report(set(), funcs=ONE))
    assert summary.stop_reason is StopReason.LLM_UNAVAILABLE
    assert summary.message == "Stopped: Groq was unreachable for 12 minutes; tests kept so far are saved."
    assert t.slept == [15.0, 30.0, 60.0, 120.0, 120.0, 120.0, 120.0, 120.0]  # 705 s >= 600 s at the 9th failure
    assert not orch.failed


async def test_a_model_error_from_groq_ends_the_outage(ws):
    v = FakeValidator(ws, [accepted({"A:1", "A:2"}, funcs=ONE)])
    agents = FakeAgents([LLMUnavailable("down"), LLMError("schema"), LLMUnavailable("down"), GOOD])
    orch, _, t = run_timed(ws, v, agents, targets_per_iteration=1, patience=5)
    await orch.run(report(set(), funcs=ONE))
    assert t.slept == [15.0, 15.0]


async def test_a_successful_call_ends_the_outage(ws):
    funcs = (("a.go", "A"), ("b.go", "B"))
    bad = ValidationResult(ValidationKind.COMPILE_ERROR, "undefined: x")
    v = FakeValidator(ws, [bad, accepted({"A:1", "A:2"}, funcs=funcs)])
    agents = FakeAgents([LLMUnavailable("down"), GOOD, LLMUnavailable("down again"), GOOD])
    orch, _, t = run_timed(ws, v, agents, target=50, targets_per_iteration=1, max_fix_attempts=0, patience=5)
    await orch.run(report(set(), funcs=funcs))
    assert t.slept == [15.0, 15.0]


async def test_a_model_error_still_counts_as_a_failure(ws):
    orch, _, _ = run_timed(ws, FakeValidator(ws, []), FakeAgents([LLMError("schema")]), targets_per_iteration=1,
                           max_iterations=1)
    await orch.run(report(set(), funcs=ONE))
    assert orch.failed[FuncKey(file="a.go", name="A")] == 1


async def test_cancel_during_an_outage_backoff_wakes_at_once(ws):
    cancel = asyncio.Event()

    async def emit(kind, data):
        if kind == "llm_unreachable":
            cancel.set()

    req = JobRequest(repo_path="x", options=JobOptions(targets_per_iteration=1))
    deps = RunDeps(ws=ws, validator=FakeValidator(ws, []), agents=FakeAgents([LLMUnavailable("down")]),
                   contexts=FakeContexts(), package_of=lambda f: "p")
    orch = Orchestrator(deps, req, emit, cancel)  # the real, cancellable wait
    summary = await asyncio.wait_for(orch.run(report(set(), funcs=ONE)), timeout=5)
    assert summary.stop_reason is StopReason.CANCELLED


def assertion_free(free, new_tests):
    from app.validator import no_assertions_message
    return ValidationResult(ValidationKind.NO_ASSERTIONS, no_assertions_message(list(free), len(new_tests)),
                            new_tests=list(new_tests), no_assertions=list(free))


async def test_prunes_assertion_free_new_tests_and_records_why(ws):
    v = FakeValidator(ws, [assertion_free(["TestNoCheck"], ["TestGood", "TestNoCheck"])],
                      prune_results=[accepted({"A:1"}, tests=["TestGood"])])
    agents = FakeAgents([GOOD])
    orch, events = run(ws, v, agents, target=25)
    summary = await orch.run(report(set()))
    assert v.pruned == [["TestNoCheck"]] and agents.fix_kinds == []
    assert summary.tests_added == ["TestGood"]
    assert ("tests_pruned", {"index": 1, "file": "a.go", "tests": ["TestNoCheck"], "reason": "no_assertions"}) in events
    [first, _] = [d for t, d in events if t == "validation_result"]
    assert first["kind"] == "no_assertions" and first["no_assertions"] == ["TestNoCheck"]


async def test_assertion_free_prune_then_failing_prune_in_one_round(ws):
    failing = ValidationResult(ValidationKind.TEST_FAILURE, "--- FAIL: TestBad", failed_tests=["TestBad"],
                               new_tests=["TestGood", "TestBad"])
    v = FakeValidator(ws, [assertion_free(["TestNoCheck"], ["TestGood", "TestBad", "TestNoCheck"])],
                      prune_results=[failing, accepted({"A:1"}, tests=["TestGood"])])
    agents = FakeAgents([GOOD])
    orch, events = run(ws, v, agents, target=25)
    summary = await orch.run(report(set()))
    assert v.pruned == [["TestNoCheck"], ["TestBad"]] and agents.fix_kinds == []
    assert summary.tests_added == ["TestGood"]
    pruned = [d for t, d in events if t == "tests_pruned"]
    assert [p.get("reason") for p in pruned] == ["no_assertions", None]  # failing-test prunes keep their old shape


async def test_all_assertion_free_goes_to_the_fixer_with_the_rule(ws):
    v = FakeValidator(ws, [assertion_free(["TestA"], ["TestA"]), accepted({"A:1"}, tests=["TestA"])])
    agents = FakeAgents([GOOD], fixes=[GOOD])
    orch, events = run(ws, v, agents, target=25, max_fix_attempts=1)
    summary = await orch.run(report(set()))
    assert v.pruned == [] and agents.fix_kinds == [ValidationKind.NO_ASSERTIONS]
    assert summary.tests_added == ["TestA"]
    assert "tests_pruned" not in [t for t, _ in events]
    [history] = agents.histories
    assert history[0].kind == "no_assertions" and "Every Test function must check its result" in history[0].lines[0]


async def test_all_assertion_free_is_rejected_when_the_fixer_cannot_help(ws):
    v = FakeValidator(ws, [assertion_free(["TestA"], ["TestA"])])
    orch, events = run(ws, v, FakeAgents([GOOD]), target=25, max_fix_attempts=0, max_iterations=1)
    await orch.run(report(set(), funcs=(("a.go", "A"),)))
    assert ("candidate_rejected", {"index": 1, "file": "a.go", "reason": "no_assertions"}) in events
    assert ws.read("a_test.go") is None  # rolled back


async def test_assertion_free_prune_that_leaves_no_gain_goes_to_the_fixer_marked_as_such(ws):
    v = FakeValidator(ws, [assertion_free(["TestNoCheck"], ["TestGood", "TestNoCheck"]), accepted({"A:1"})],
                      prune_results=[NO_GAIN])
    agents = FakeAgents([GOOD], fixes=[GOOD])
    orch, _ = run(ws, v, agents, target=25, max_fix_attempts=1)
    await orch.run(report(set()))
    [history] = agents.histories
    assert history[-1].source == "prune of [TestNoCheck] (no assertions)"
    assert history[-1].pruned == ("TestNoCheck",) and history[-1].pruned_reason == "no_assertions"
    assert agents.fix_kinds == [ValidationKind.NO_GAIN]
