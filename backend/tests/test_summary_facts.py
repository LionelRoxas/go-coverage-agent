# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
"""RunFacts from a real run: output/e2de1ca387cb (stats, 0% -> 81.07%), trimmed to tests/fixtures/run_e2de1ca387cb."""
from pathlib import Path

import pytest

from app.models import Event, Summary
from app.summary.facts import build_facts, cost_usd

FIXTURE = Path(__file__).parent / "fixtures" / "run_e2de1ca387cb" / "events.jsonl"


def load():
    events = [Event.model_validate_json(line) for line in FIXTURE.read_text(encoding="utf-8").splitlines() if line]
    summary = Summary.model_validate(next(e.data for e in events if e.type == "job_completed"))
    return summary, events


def facts(**kw):
    summary, events = load()
    return build_facts(summary, events, repo="stats", model="openai/gpt-oss-120b", job_id="e2de1ca387cb", **kw)


def test_run_level_facts():
    f = facts()
    assert (f.repo, f.module, f.model) == ("stats", "github.com/montanaflynn/stats", "openai/gpt-oss-120b")
    assert (f.goal_percent, f.baseline_percent, f.final_percent, f.gain_points) == (80.0, 0.0, 81.07, 81.07)
    assert f.stop_reason == "target_reached" and f.stop_message == "Reached the 80% coverage target."
    assert (f.rounds, f.duration_s, f.duration_min) == (11, 310.1, 5.2)
    assert (f.tokens.prompt, f.tokens.completion, f.tokens.total) == (83562, 91461, 175023)
    assert f.tokens_per_point == 2159  # 175023 / 81.07
    assert f.tests_dir == "output/e2de1ca387cb/tests"
    assert f.cost_usd is None


def test_llm_calls_and_outcomes():
    f = facts()
    assert [(c.role, c.reasoning_effort, c.calls) for c in f.llm_calls] == [("writer", "medium", 31),
                                                                            ("fixer", "medium", 1)]
    assert (f.targets_accepted, f.targets_rejected, f.rejected_reasons) == (31, 0, {})
    # 31 writer answers: 3 needed failing tests pruned, 1 needed the Fixer after a compile error
    assert f.first_check_passes == 27
    assert (f.llm_fixes, f.mechanical_repairs, f.pruned_tests) == (1, 0, 3)
    assert (f.llm_timeouts, f.rate_limit_waits, f.rate_limit_wait_s) == (0, 0, 0.0)
    assert f.suspected_bugs == []


def test_tests_and_files():
    summary, _ = load()
    f = facts()
    assert f.tests_added == summary.tests_added and f.tests_added_count == 109
    assert f.test_files == summary.test_files and f.test_files_count == len(f.test_files) == 29
    assert len(f.per_file) == 54
    assert f.per_file[0].model_dump() == {"file": "describe.go", "before": 0.0, "after": 100.0}
    low = [(x.file, x.percent, x.uncovered_statements) for x in f.lowest_files]
    assert len(low) == 5
    assert low == sorted(low, key=lambda t: (t[1], -t[2], t[0]))
    assert all(p < 100 for _, p, _ in low)


def test_lowest_files_uncovered_counts_come_from_baseline_statements():
    f = facts()
    by = {x.file: x for x in f.per_file}
    for low in f.lowest_files:
        assert by[low.file].after == low.percent
        assert low.uncovered_statements > 0


def test_cost_when_prices_are_set():
    f = facts(price_input_per_m=0.15, price_output_per_m=0.60)
    assert f.cost_usd is not None
    assert f.cost_usd.input_usd == pytest.approx(0.0125, abs=1e-4)  # 83562 * 0.15 / 1e6
    assert f.cost_usd.output_usd == pytest.approx(0.0549, abs=1e-4)  # 91461 * 0.60 / 1e6
    assert f.cost_usd.total_usd == pytest.approx(0.0674, abs=1e-4)


def test_cost_needs_both_prices():
    assert cost_usd(100, 100, 0.15, None) is None
    assert cost_usd(100, 100, None, 0.6) is None
    assert cost_usd(1_000_000, 2_000_000, 0.15, 0.6).model_dump() == {"input_usd": 0.15, "output_usd": 1.2,
                                                                     "total_usd": 1.35}


def test_events_after_the_terminal_event_are_ignored():
    summary, events = load()
    extra = Event(seq=999, ts=0, type="rate_limited", data={"seconds": 30.0, "reason": "429"})
    f = build_facts(summary, [*events, extra], repo="stats", model="m", job_id="x")
    assert f.rate_limit_waits == 0


def test_counts_rejections_timeouts_repairs_and_waits():
    summary, events = load()
    end = next(i for i, e in enumerate(events) if e.type == "job_completed")
    more = [("candidate_rejected", {"index": 1, "file": "a.go", "reason": "no_gain"}),
            ("candidate_rejected", {"index": 1, "file": "b.go", "reason": "no_gain"}),
            ("candidate_rejected", {"index": 1, "file": "c.go", "reason": "too_large"}),
            ("validation_result", {"index": 1, "file": "c.go", "kind": "llm_timeout", "output": "", "failed_tests": []}),
            ("mechanical_repair", {"index": 1, "file": "a.go", "repair": 1, "description": "added import"}),
            ("rate_limited", {"seconds": 12.5, "reason": "tpm"}), ("rate_limited", {"seconds": 3.0, "reason": "429"})]
    inserted = [Event(seq=1000 + i, ts=0, type=t, data=d) for i, (t, d) in enumerate(more)]
    f = build_facts(summary, events[:end] + inserted + events[end:], repo="stats", model="m", job_id="x")
    assert (f.targets_rejected, f.rejected_reasons) == (3, {"no_gain": 2, "too_large": 1})
    assert (f.llm_timeouts, f.mechanical_repairs, f.rate_limit_waits, f.rate_limit_wait_s) == (1, 1, 2, 15.5)


def test_deferred_items_and_failed_calls_are_not_rejections_or_calls():
    summary, events = load()
    run, rest = events[:-1], events[-1:]
    assert rest[0].type == "job_completed"
    seq = run[-1].seq
    extra = [Event(seq=seq + 1, ts=1.0, type="llm_call", data={"index": 1, "file": "x.go", "role": "writer",
                                                             "prompt_tokens": 10, "completion_tokens": 5,
                                                             "total_tokens": 1, "reasoning_effort": None,
                                                             "failed": True}),
             Event(seq=seq + 2, ts=1.0, type="candidate_deferred",
                   data={"index": 1, "file": "x.go", "reason": "llm_unavailable"})]
    f = build_facts(summary, [*run, *extra, *rest], repo="stats", model="m", job_id="e2de1ca387cb")
    assert [(c.role, c.reasoning_effort, c.calls) for c in f.llm_calls] == [("writer", "medium", 31),
                                                                            ("fixer", "medium", 1)]
    assert (f.failed_llm_calls, f.targets_deferred) == (1, 1)
    assert (f.targets_rejected, f.rejected_reasons) == (0, {})


def test_counts_for_comparing_parallel_and_sequential_writers():
    summary, events = load()
    f = facts()
    assert (f.parallel_writers, f.duplicate_test_renames, f.helper_collision_fixes, f.no_gain_rejections) == (
        False, 0, 0, 0)  # an older log: no parallel_writers option, so it was sequential
    run, rest = events[:-1], events[-1:]
    started = events[0].model_copy(update={"data": {**events[0].data, "options": {
        **events[0].data["options"], "parallel_writers": True}}})
    at = {"index": 1, "file": "x.go"}
    more = [("validation_result", {**at, "kind": "compile_error", "output": "gohelper: duplicate declaration: TestX"}),
            ("mechanical_repair", {**at, "repair": 1, "description": "renamed duplicate test TestX to TestX_2"}),
            ("validation_result", {**at, "kind": "compile_error",
                                   "output": "./x_test.go:9:6: xCases redeclared in this block"}),
            ("fix_attempt", {**at, "attempt": 1, "kind": "compile_error"}),
            ("validation_result", {**at, "kind": "compile_error", "output": "undefined: foo"}),
            ("fix_attempt", {**at, "attempt": 2, "kind": "compile_error"}),  # not a collision
            ("candidate_rejected", {**at, "reason": "no_gain"})]
    seq = run[-1].seq
    extra = [Event(seq=seq + 1 + i, ts=1.0, type=t, data=d) for i, (t, d) in enumerate(more)]
    assert events[0].type == "job_started"
    f = build_facts(summary, [started, *run[1:], *extra, *rest], repo="stats", model="m", job_id="x")
    assert (f.parallel_writers, f.duplicate_test_renames, f.helper_collision_fixes, f.no_gain_rejections) == (
        True, 1, 1, 1)


FIXTURES = Path(__file__).parent / "fixtures"


def load_run(run_id):
    """A saved run trimmed to its run-level events and the items of one file (code omitted)."""
    path = FIXTURES / f"run_{run_id}" / "events.jsonl"
    events = [Event.model_validate_json(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    summary = Summary.model_validate(next(e.data for e in events if e.type == "job_completed"))
    return summary, events


def test_a_writer_claim_the_runtime_refuted_is_dropped_from_the_facts():
    """f910d155f3cd (stats, mode.go): the Writer claimed Mode returns the value twice for identical inputs. Its own
    test of that case failed (Go returned [5] for {5,5,5}, as mode.go does) and was pruned, and that same answer
    was accepted. Mode was also planned in a later round, whose accepted Fixer answer names no bug: the claim is
    inferred to come from the answer whose test plan names it ("uniform values expose duplicate bug")."""
    summary, events = load_run("f910d155f3cd")
    assert [b.function for b in summary.suspected_bugs] == ["Mode"]  # as the old run recorded it
    f = build_facts(summary, events, repo="stats", model="m", job_id="f910d155f3cd")
    assert f.suspected_bugs == []


@pytest.mark.parametrize("run_id,function", [("225c8beba1d9", "float64ToInt"), ("db3abc1f1b33", "Interp")])
def test_a_fixer_doc_contradiction_report_is_kept(run_id, function):
    """The Writer's test failed, the Fixer dropped the case and reported it as a suspected bug, and the Fixer's
    answer was accepted: failures before that answer never refute its claims."""
    summary, events = load_run(run_id)
    f = build_facts(summary, events, repo="r", model="m", job_id=run_id)
    assert [b.function for b in f.suspected_bugs] == [function]


def _item(labels, *more, file="a.go"):
    at = {"index": 1, "file": file}
    head = [("plan_created", {"index": 1, "items": [{"file": file, "functions": labels, "uncovered_statements": 1}]}),
            ("llm_call", {**at, "role": "writer"}),
            ("candidate_generated", {**at, "test_plan": []})]
    return [Event(seq=n, ts=0, type=t, data={**at, **d} if t != "plan_created" else d)
            for n, (t, d) in enumerate([*head, *more])]


def _pruned(*tests):
    return [("validation_result", {"kind": "test_failure", "failed_tests": list(tests)}),
            ("tests_pruned", {"tests": list(tests)})]


def bug(function):
    from app.models import SuspectedBug
    return SuspectedBug(function=function, description="d")


def test_a_failing_test_belongs_to_the_longest_planned_name_it_matches():
    from app.summary.facts import drop_refuted_bugs
    events = _item(["Sum", "SumOfSquares"], *_pruned("TestSumOfSquares_Big"), ("candidate_accepted", {}))
    assert drop_refuted_bugs([bug("Sum"), bug("SumOfSquares")], events) == [bug("Sum")]


def test_receiver_qualified_claims_match_their_own_receiver_only():
    from app.summary.facts import drop_refuted_bugs
    events = _item(["*A.String", "B.String"], *_pruned("TestA_String"), ("candidate_accepted", {}))
    assert drop_refuted_bugs([bug("(*A).String"), bug("B.String")], events) == [bug("B.String")]
    other_file = _item(["*A.String"], *_pruned("TestA_String"), ("candidate_accepted", {}))
    assert drop_refuted_bugs([bug("B.String")], other_file) == [bug("B.String")]  # never planned: kept


def test_newer_runs_record_which_answer_carried_each_claim():
    from app.summary.facts import drop_refuted_bugs
    carried = {"suspected_bugs": [{"function": "F", "description": "d"}]}
    refuted = _item(["F"], *_pruned("TestF_Case"), ("candidate_accepted", carried))
    assert drop_refuted_bugs([bug("F")], refuted) == []
    # a Fixer's accepted answer carrying the claim after the Writer's test of it failed: kept
    fixed = _item(["F"], ("validation_result", {"kind": "test_failure", "failed_tests": ["TestF_Case"]}),
                  ("fix_attempt", {"attempt": 1, "kind": "test_failure"}), ("llm_call", {"role": "fixer"}),
                  ("candidate_generated", {"test_plan": []}), ("candidate_accepted", carried))
    assert drop_refuted_bugs([bug("F")], fixed) == [bug("F")]
    # a failure that was neither pruned nor fixed refutes nothing
    failed_only = _item(["F"], ("validation_result", {"kind": "test_failure", "failed_tests": ["TestF_Case"]}),
                        ("candidate_accepted", carried))
    assert drop_refuted_bugs([bug("F")], failed_only) == [bug("F")]


def test_an_ambiguous_older_claim_is_kept():
    from app.summary.facts import drop_refuted_bugs
    first = _item(["F"], *_pruned("TestF_Case"), ("candidate_accepted", {}))
    second = [Event(seq=100 + e.seq, ts=0, type=e.type, data={**e.data, "index": 2}) for e in
              _item(["F"], ("candidate_accepted", {}))]
    second[0] = Event(seq=100, ts=0, type="plan_created", data={"index": 2, "items": [
        {"file": "a.go", "functions": ["F"], "uncovered_statements": 1}]})
    assert drop_refuted_bugs([bug("F")], first) == []  # one accepted answer for F: it carried the claim
    assert drop_refuted_bugs([bug("F")], first + second) == [bug("F")]  # two, neither plan names a bug: keep


def test_assertion_free_removals_are_counted_apart_from_failing_prunes():
    summary, events = load()
    seq = max(e.seq for e in events)
    extra = [Event(seq=seq + 1, ts=1.0, type="tests_pruned",
                   data={"index": 1, "file": "mean.go", "tests": ["TestA", "TestB"], "reason": "no_assertions"})]
    end = next(i for i, e in enumerate(events) if e.type == "job_completed")
    run = events[:end] + extra + events[end:]
    f = build_facts(summary, run, repo="stats", model="openai/gpt-oss-120b", job_id="e2de1ca387cb")
    assert (f.pruned_tests, f.pruned_no_assertions) == (3, 2)
    assert facts().pruned_no_assertions == 0  # older runs have no such prunes
