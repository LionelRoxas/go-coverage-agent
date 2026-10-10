# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
"""PARALLEL_WRITERS: each round's writer requests go out together; validation stays one at a time in plan order."""
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.agents.llm_agents import Agents, helper_prefix, parallel_naming_rule
from app.config import Settings
from app.engine.orchestrator import Orchestrator, RunDeps
from app.llm.client import GroqLLM, LLMCancelled, LLMError, LLMOutputTooLarge, LLMUnavailable
from app.llm.limits import RateLimiter, UsageLedger
from app.models import FuncKey, JobOptions, JobRequest, PlanItem, StopReason, TokenUsage
from app.validator import ValidationKind, ValidationResult
from app.workspace import Workspace
from tests.fakes import FakeLLM, snippet
from tests.test_orchestrator import FakeAgents, FakeContexts, FakeValidator, accepted, report, ws  # noqa: F401

GOLDEN = Path(__file__).parent / "fixtures" / "sequential_events.json"
FUNCS = (("c.go", "C"), ("c.go", "C2"), ("a.go", "A"), ("b.go", "B"))
ABC = (("a.go", "A"), ("b.go", "B"), ("c.go", "C"))
GOOD = snippet("func TestA(t *testing.T) {}")


def make(ws, validator, agents, *, contexts=None, cancel=None, reservation=0, target=100.0, **opts):
    events = []

    async def emit(t, d):
        events.append((t, d))

    async def no_sleep(seconds):
        pass

    req = JobRequest(repo_path="x", target_coverage=target, options=JobOptions(**opts))
    deps = RunDeps(ws=ws, validator=validator, agents=agents, contexts=contexts or FakeContexts(),
                   package_of=lambda f: "p")
    orch = Orchestrator(deps, req, emit, cancel or asyncio.Event(), sleep=no_sleep, call_reservation=reservation)
    return orch, events


def types(events):
    return [t for t, _ in events]


class KeyedAgents:
    """Writer answers chosen by file (a list per file, used in order), each after an optional delay. With
    `expected`, every writer waits at a gate that opens only once `expected` writers are in flight together."""

    def __init__(self, answers, delays=None, expected=0, usage=10, fixes=()):
        self.answers = {f: list(a) for f, a in answers.items()}
        self.delays, self.usage, self.fixes = delays or {}, usage, list(fixes)
        self.started: list[str] = []
        self.finished: list[str] = []
        self.parallel_flags: list[bool] = []
        self.expected, self.gate = expected, asyncio.Event()
        self.last_effort = "medium"

    async def write(self, item, inputs, on_request=None, parallel=False):
        self.started.append(item.file)
        self.parallel_flags.append(parallel)
        if on_request is not None:
            await on_request("medium")
        if self.expected:
            if len(self.started) >= self.expected:
                self.gate.set()
            await asyncio.wait_for(self.gate.wait(), timeout=2)
        await asyncio.sleep(self.delays.get(item.file, 0))
        self.finished.append(item.file)
        r = self.answers[item.file].pop(0)
        if isinstance(r, BaseException):
            raise r
        return r, TokenUsage(prompt_tokens=self.usage, completion_tokens=5)

    async def fix(self, item, inputs, snip, result, history=(), on_request=None):
        if on_request is not None:
            await on_request("medium")
        return self.fixes.pop(0), TokenUsage(prompt_tokens=10, completion_tokens=5)


class OrderedValidator(FakeValidator):
    """Results by test file; records the order in which candidates are checked."""

    def __init__(self, ws, results):
        super().__init__(ws, [])
        self.by_file = {f: list(r) for f, r in results.items()}
        self.order: list[str] = []

    async def validate(self, test_file, package, snip, prev):
        self.snips.append(snip)
        self.order.append(test_file)
        self.ws.write_test(test_file, "package p\n// merged\n")
        return self.by_file[test_file].pop(0)


# --- flag off: today's behaviour, event for event ---

def _scenario_results():
    """Two rounds that touch every path of an item: split after a too-large answer, a duplicate-name rename,
    a prune that gains nothing, a fixer, a deferral after a Groq outage, and reaching the goal."""
    dup = ValidationResult(ValidationKind.COMPILE_ERROR, "gohelper: duplicate declaration: TestA")
    failing = ValidationResult(ValidationKind.TEST_FAILURE, "--- FAIL: TestBad", failed_tests=["TestBad"],
                               new_tests=["TestA_2", "TestBad"])
    no_gain = ValidationResult(ValidationKind.NO_GAIN, "no new coverage")
    results = [accepted({"C:1", "C:2"}, funcs=FUNCS), dup, failing,
               accepted({"C:1", "C:2", "A:1", "A:2"}, tests=["TestA_2"], funcs=FUNCS),
               accepted({"C:1", "C:2", "A:1", "A:2", "B:1", "B:2"}, tests=["TestB"], funcs=FUNCS),
               accepted({"C:1", "C:2", "C2:1", "C2:2", "A:1", "A:2", "B:1", "B:2"}, tests=["TestC2"], funcs=FUNCS)]
    return results, [no_gain]


async def _sequential_events(ws, reservation=0):
    results, prunes = _scenario_results()
    agents = FakeAgents([LLMOutputTooLarge("truncated"), GOOD, GOOD, LLMUnavailable("down"), GOOD, GOOD], fixes=[GOOD])
    orch, events = make(ws, FakeValidator(ws, results, prunes), agents, max_fix_attempts=1, targets_per_iteration=3,
                        max_iterations=3, contexts=FakeContexts(["TestA"]), reservation=reservation)
    summary = await orch.run(report(set(), funcs=FUNCS))
    return summary, json.loads(json.dumps(events))


@pytest.mark.parametrize("reservation", [0, 16000])
async def test_flag_off_keeps_the_sequential_event_sequence(ws, reservation):
    """The golden file was recorded from the orchestrator before parallel writers existed. FakeAgents.write takes no
    `parallel` argument, so this also proves the sequential writer call (and so its prompt) is unchanged."""
    summary, events = await _sequential_events(ws, reservation)
    assert summary.stop_reason is StopReason.TARGET_REACHED
    assert events == json.loads(GOLDEN.read_text(encoding="utf-8"))


# --- flag on ---

async def test_writer_requests_overlap_and_validation_follows_plan_order(ws):
    # c.go answers first and a.go last; the gate only opens once all three writers are in flight together.
    agents = KeyedAgents({"a.go": [GOOD], "b.go": [GOOD], "c.go": [GOOD]},
                         delays={"a.go": 0.03, "b.go": 0.02, "c.go": 0.0}, expected=3)
    v = OrderedValidator(ws, {"a_test.go": [accepted({"A:1"}, funcs=ABC)],
                              "b_test.go": [accepted({"A:1", "B:1"}, funcs=ABC)],
                              "c_test.go": [accepted({"A:1", "B:1", "C:1"}, funcs=ABC)]})
    orch, events = make(ws, v, agents, max_iterations=1, parallel_writers=True)
    await orch.run(report(set(), funcs=ABC))
    assert agents.started == ["a.go", "b.go", "c.go"] and agents.finished == ["c.go", "b.go", "a.go"]
    assert agents.parallel_flags == [True, True, True]
    assert v.order == ["a_test.go", "b_test.go", "c_test.go"]  # plan order, whatever order the answers came in
    assert types(events)[2:8] == ["llm_request"] * 3 + ["llm_call"] * 3
    assert [d["file"] for k, d in events if k == "llm_request"] == ["a.go", "b.go", "c.go"]
    assert [d["file"] for k, d in events if k == "llm_call"] == ["c.go", "b.go", "a.go"]  # each with its own file
    assert [d["file"] for k, d in events if k == "candidate_accepted"] == ["a.go", "b.go", "c.go"]
    assert [d["total_tokens"] for k, d in events if k == "llm_call"] == [15, 30, 45]  # every call charged once


async def test_parallel_rounds_reach_the_same_result_as_sequential(ws, tmp_path):
    seq_summary, _ = await _sequential_events(ws)
    (tmp_path / "repo2").mkdir()
    ws2 = Workspace(tmp_path / "repo2", tmp_path / "scratch")
    results, prunes = _scenario_results()
    # The same answers by file: c.go is split, a.go renamed/pruned/fixed, b.go meets an outage once.
    agents = KeyedAgents({"c.go": [LLMOutputTooLarge("truncated"), GOOD, GOOD], "a.go": [GOOD],
                          "b.go": [LLMUnavailable("down"), GOOD]}, fixes=[GOOD])
    orch, events = make(ws2, FakeValidator(ws2, results, prunes), agents, max_fix_attempts=1, targets_per_iteration=3,
                        max_iterations=3, contexts=FakeContexts(["TestA"]), parallel_writers=True)
    summary = await orch.run(report(set(), funcs=FUNCS))
    assert summary.stop_reason is StopReason.TARGET_REACHED
    assert (summary.final_percent, summary.tests_added, summary.test_files, summary.iterations) == (
        seq_summary.final_percent, seq_summary.tests_added, seq_summary.test_files, seq_summary.iterations)
    # Groq answered the round's other writers, so b.go is deferred without waiting out an outage.
    assert types(events).count("llm_unreachable") == 0 and summary.iterations[0].deferred == 1


async def test_one_failing_writer_does_not_affect_the_others(ws):
    funcs = (("a.go", "A"), ("b.go", "B"), ("c.go", "C"), ("c.go", "C2"))
    agents = KeyedAgents({"a.go": [GOOD], "b.go": [LLMError("schema failure")],
                          "c.go": [LLMOutputTooLarge("truncated"), GOOD]})
    v = OrderedValidator(ws, {"a_test.go": [accepted({"A:1"}, funcs=funcs)],
                              "c_test.go": [accepted({"A:1", "C:1"}, funcs=funcs)]})
    orch, events = make(ws, v, agents, max_iterations=1, max_fix_attempts=0, parallel_writers=True)
    summary = await orch.run(report(set(), funcs=funcs))
    outcome = {d["file"]: (k, d.get("reason")) for k, d in events
               if k in ("candidate_accepted", "candidate_rejected", "candidate_deferred")}
    assert outcome == {"c.go": ("candidate_accepted", None), "a.go": ("candidate_accepted", None),
                       "b.go": ("candidate_rejected", "llm_error")}
    assert summary.iterations[0].accepted == 2 and summary.iterations[0].rejected == 1
    assert agents.started.count("c.go") == 2  # the too-large answer was split and written again, alone
    assert ws.read("b_test.go") is None


async def test_writers_all_meeting_an_outage_are_deferred_with_one_back_off(ws):
    agents = KeyedAgents({"a.go": [LLMUnavailable("down"), GOOD], "b.go": [LLMUnavailable("down"), GOOD]})
    v = OrderedValidator(ws, {"a_test.go": [accepted({"A:1"})], "b_test.go": [accepted({"A:1", "B:1"})]})
    orch, events = make(ws, v, agents, max_iterations=1, parallel_writers=True)
    summary = await orch.run(report(set()))
    t = types(events)
    assert t.count("candidate_deferred") == 2 and t.count("llm_unreachable") == 1
    assert t.index("llm_unreachable") == t.index("iteration_completed") - 1  # after the round's items
    # The outage-only round counts toward neither max_iterations nor patience: the next round still runs.
    assert [(i.deferred, i.accepted) for i in summary.iterations] == [(2, 0), (0, 2)]


async def test_names_accepted_earlier_in_the_round_count_for_the_rename(ws):
    """a.go's and b.go's writers both wrote TestX from the round-start state. a.go's version is accepted first; the
    mechanical rename of b.go's must avoid the names a.go just added (TestX and TestX_2), so it picks TestX_3
    (from the stale round-start names it would have picked TestX_2, a second collision)."""
    declared: list[str] = []

    class LiveContexts:
        async def inputs_for(self, item, rep):
            return SimpleNamespace(declared=list(declared))

    class Merging(OrderedValidator):
        async def validate(self, test_file, package, snip, prev):
            r = await super().validate(test_file, package, snip, prev)
            if r.accepted:
                declared.extend(r.new_tests)
            return r

    x = snippet("func TestX(t *testing.T) {}")
    dup = ValidationResult(ValidationKind.COMPILE_ERROR, "gohelper: duplicate declaration: TestX")
    v = Merging(ws, {"a_test.go": [accepted({"A:1"}, tests=["TestX", "TestX_2"])],
                     "b_test.go": [dup, accepted({"A:1", "B:1"}, tests=["TestX_3"])]})
    agents = KeyedAgents({"a.go": [x], "b.go": [x]})
    orch, _ = make(ws, v, agents, max_iterations=1, max_fix_attempts=0, contexts=LiveContexts(),
                   parallel_writers=True)
    summary = await orch.run(report(set()))
    assert v.snips[-1].code == "func TestX_3(t *testing.T) {}"
    assert summary.tests_added == ["TestX", "TestX_2", "TestX_3"]


async def test_concurrent_writers_never_overshoot_the_job_budget_by_more_than_one_reservation(ws):
    funcs = tuple((f"f{i}.go", f"F{i}") for i in range(5))
    answers = {f"f{i}.go": [GOOD] for i in range(5)}
    agents = KeyedAgents(answers, delays={f: 0.01 for f in answers}, usage=2995)  # 3000 tokens per call
    v = OrderedValidator(ws, {f"f{i}_test.go": [accepted({f"F{i}:1"}, tests=[f"T{i}"], funcs=funcs)] for i in range(5)})
    orch, _ = make(ws, v, agents, max_iterations=1, targets_per_iteration=5, max_llm_tokens=10_000,
                   reservation=4000, parallel_writers=True)
    summary = await orch.run(report(set(), funcs=funcs))
    # Reserved before sending: 0, 4000 and 8000 are under 10 000; the fourth would make 12 000 and is refused.
    assert len(agents.started) == 3
    assert summary.tokens.total <= 10_000 + 4000
    assert summary.stop_reason is StopReason.BUDGET_EXHAUSTED
    assert v.order == ["f0_test.go", "f1_test.go", "f2_test.go"]  # the answers already paid for are still checked
    assert orch._reserved == 0  # every reservation was released


async def test_without_reservations_every_writer_would_have_gone_out(ws):
    """The control for the budget test: only the reservations hold the cap."""
    funcs = tuple((f"f{i}.go", f"F{i}") for i in range(5))
    agents = KeyedAgents({f"f{i}.go": [GOOD] for i in range(5)}, usage=2995)
    v = OrderedValidator(ws, {f"f{i}_test.go": [ValidationResult(ValidationKind.NO_GAIN, "")] for i in range(5)})
    orch, _ = make(ws, v, agents, max_iterations=1, targets_per_iteration=5, max_llm_tokens=10_000,
                   max_fix_attempts=0, parallel_writers=True)
    await orch.run(report(set(), funcs=funcs))
    assert len(agents.started) == 5 and orch.tokens.total == 15_000


async def test_cancel_stops_every_writer_in_flight_and_nothing_follows(ws):
    cancel = asyncio.Event()

    class Hanging(KeyedAgents):
        async def write(self, item, inputs, on_request=None, parallel=False):
            self.started.append(item.file)
            if on_request is not None:
                await on_request("medium")
            if len(self.started) == 3:
                asyncio.get_running_loop().call_later(0.02, cancel.set)
            await cancel.wait()
            raise LLMCancelled("cancelled during an LLM request")

    orch, events = make(ws, FakeValidator(ws, []), Hanging({}), cancel=cancel, parallel_writers=True)
    summary = await asyncio.wait_for(orch.run(report(set(), funcs=ABC)), timeout=2)
    assert summary.stop_reason is StopReason.CANCELLED
    assert types(events) == ["iteration_started", "plan_created", "llm_request", "llm_request", "llm_request"]
    assert [t for t in asyncio.all_tasks() if t is not asyncio.current_task()] == []


async def test_cancel_with_the_real_client_cancels_every_hanging_request(ws, tmp_path):
    cancel = asyncio.Event()

    class HangingGroq:
        def __init__(self):
            self.sent = self.cancelled = 0
            self.chat = self.completions = self.with_raw_response = self

        async def create(self, **kwargs):
            self.sent += 1
            if self.sent == 3:
                asyncio.get_running_loop().call_later(0.02, cancel.set)
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                self.cancelled += 1
                raise

    groq_client = HangingGroq()
    ledger = UsageLedger(tmp_path / "u.json", 1_000_000)
    llm = GroqLLM(Settings(groq_api_key="k"), ledger, RateLimiter(), client=groq_client, cancel=cancel)

    class ClientAgents:
        last_effort = None

        async def write(self, item, inputs, on_request=None, parallel=False):
            return await llm.complete(role="writer", system="s", user=item.file, schema=type(GOOD),
                                      on_request=on_request)

    orch, events = make(ws, FakeValidator(ws, []), ClientAgents(), cancel=cancel, parallel_writers=True)
    summary = await asyncio.wait_for(orch.run(report(set(), funcs=ABC)), timeout=2)
    assert summary.stop_reason is StopReason.CANCELLED
    assert groq_client.sent == 3 and groq_client.cancelled == 3
    assert ledger.reserved == 0 and llm.limiter._inflight == 0
    assert "llm_call" not in types(events)
    assert [t for t in asyncio.all_tasks() if t is not asyncio.current_task()] == []


# --- the Writer's prompt ---

def test_helper_prefix_comes_from_the_file_base_name():
    assert helper_prefix("stats/norm.go") == "norm"
    assert helper_prefix("big_int.go") == "bigInt"
    assert helper_prefix("x/2d-shape.go") == "t2dShape"


async def test_naming_line_only_when_parallel():
    llm = FakeLLM([GOOD, GOOD])
    agents = Agents(llm, max_prompt_tokens=12000)
    item = PlanItem(file="stats/norm.go", functions=[FuncKey(file="stats/norm.go", name="Norm")],
                    uncovered_statements=3)
    inputs = SimpleNamespace(module="m", package="stats", go_version="1.22", source_file="stats/norm.go",
                             test_file="stats/norm_test.go", targets=[("Norm", "func Norm() {}")], declared=[],
                             referenced=[], existing_tests=[])
    await agents.write(item, inputs)
    await agents.write(item, inputs, parallel=True)
    off, on = llm.calls[0]["user"], llm.calls[1]["user"]
    line = parallel_naming_rule(item)
    assert line not in off and on == f"{off}\n{line}"
    assert "`norm`" in line and "`normApproxEqual`" in line and "Test function" in line
