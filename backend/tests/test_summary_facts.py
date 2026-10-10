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
