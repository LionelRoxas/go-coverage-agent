# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
from app.models import BusinessSummary, RunSummary, SummaryGap, SuspectedBug, TechnicalSummary
from app.summary.facts import CostFacts, FileFact, LowFile, RunFacts, TokenFacts
from app.summary.grounding import ground, number_tokens


def facts(**kw) -> RunFacts:
    base = dict(
        repo="stats", module="github.com/montanaflynn/stats", model="openai/gpt-oss-120b", goal_percent=80.0,
        baseline_percent=0.0, final_percent=81.07, gain_points=81.07, stop_reason="target_reached",
        stop_message="Reached the 80% coverage target.", rounds=11, duration_s=310.1, duration_min=5.2,
        tokens=TokenFacts(prompt=83562, completion=91461, total=175023), tokens_per_point=2159,
        cost_usd=CostFacts(input_usd=0.0125, output_usd=0.0549, total_usd=0.0674), llm_calls=[],
        targets_accepted=31, targets_rejected=0, rejected_reasons={}, first_check_passes=27, llm_fixes=1,
        mechanical_repairs=0, pruned_tests=3, llm_timeouts=0, rate_limit_waits=0, rate_limit_wait_s=0.0,
        tests_added_count=109, tests_added=["TestMean", "TestNormPpf"], test_files_count=29,
        test_files=["mean_test.go", "norm_test.go"],
        tests_dir="output/e2de1ca387cb/tests",
        per_file=[FileFact(file="mean.go", before=0.0, after=100.0), FileFact(file="norm.go", before=0.0, after=94.37)],
        lowest_files=[LowFile(file="clip.go", percent=0.0, uncovered_statements=12)],
        suspected_bugs=[SuspectedBug(function="Mean", description="empty input")],
    )
    base.update(kw)
    return RunFacts(**base)


def summary(**kw) -> RunSummary:
    business = dict(headline="Coverage rose from 0% to 81.1%.", outcome="The goal of 80% was reached.",
                    efficiency="It took 5.2 minutes and 175K tokens.", risks=["Some files are still untested."],
                    recommendation="Adopt the tests.")
    technical = dict(headline="81.07% of statements are covered.", what_was_tested="Tests cover mean.go.",
                     where_tests_live="In output/e2de1ca387cb/tests.", gaps=[SummaryGap(file="clip.go", detail="12 statements uncovered.")],
                     suspected_bugs=["Mean: empty input"], rejected_or_failed="3 tests were pruned.",
                     how_to_run="Copy the files in and run `go test ./...` in the repo.", next_steps=["Review TestMean."])
    business.update(kw.pop("business", {}))
    technical.update(kw.pop("technical", {}))
    return RunSummary(business=BusinessSummary(**business), technical=TechnicalSummary(**technical))


def test_number_tokens():
    text = "From 0% to 81.07% (+81.1 pp), 175,023 tokens or 175K, $0.07, 1.2M, in go1.27 with gpt-oss-120b, x2, v1.2.3"
    assert [t.text for t in number_tokens(text)] == ["0", "81.07", "81.1", "175,023", "175K", "0.07", "1.2M"]


def test_grounded_summary_is_unchanged():
    s = summary()
    out, dropped = ground(s, facts())
    assert dropped == 0 and out == s


def test_rounding_and_scaling_match_the_facts():
    ok = "Coverage is 81%, 81.1% or 81.07%; 175K, 175.0K, 0.2M or 175,023 tokens; $0.07 (input $0.01); 2,159 per point."
    out, dropped = ground(summary(business={"outcome": ok}), facts())
    assert dropped == 0 and out.business.outcome == ok


def test_numbers_inside_fact_strings_are_allowed():
    out, dropped = ground(summary(business={"outcome": "It stopped at the 80% target."}), facts(goal_percent=75.0))
    assert dropped == 0


def test_invented_numbers_drop_only_their_sentence():
    text = "The goal was reached. It saved 40 hours of work. Coverage is 81.1%."
    out, dropped = ground(summary(business={"outcome": text}), facts())
    assert dropped == 1
    assert out.business.outcome == "The goal was reached. Coverage is 81.1%."


def test_wrong_precision_does_not_match():
    out, dropped = ground(summary(business={"headline": "Coverage reached 81.2%."}), facts())
    assert dropped == 1 and out.business.headline == ""


def test_list_items_with_invented_numbers_or_files_are_dropped():
    s = summary(business={"risks": ["Keep 3 pruned tests in mind.", "About 14 bugs remain.", "Fine."]},
                technical={"next_steps": ["Extend mean_test.go.", "Write tests for parser.go.", "Review TestNope."],
                           "gaps": [SummaryGap(file="clip.go", detail="12 statements uncovered."),
                                    SummaryGap(file="ghost.go", detail="Untested."),
                                    SummaryGap(file="norm.go", detail="99 statements left.")]})
    out, dropped = ground(s, facts())
    assert out.business.risks == ["Keep 3 pruned tests in mind.", "Fine."]  # 3 is a fact, 14 is not
    assert out.technical.next_steps == ["Extend mean_test.go."]
    assert [g.file for g in out.technical.gaps] == ["clip.go"]
    assert dropped == 5


def test_file_paths_and_test_names_must_exist():
    text = ("See output/e2de1ca387cb/tests/mean_test.go and ./norm.go. TestNormPpf passed. "
            "See sub/other_test.go. TestMissing failed.")
    out, dropped = ground(summary(technical={"what_was_tested": text}), facts())
    assert dropped == 2
    assert out.technical.what_was_tested == ("See output/e2de1ca387cb/tests/mean_test.go and ./norm.go. "
                                             "TestNormPpf passed.")


def test_no_cost_in_facts_means_no_dollar_amounts():
    out, dropped = ground(summary(business={"efficiency": "It cost $0.07. It was quick."}), facts(cost_usd=None))
    assert dropped == 1 and out.business.efficiency == "It was quick."


def test_the_hand_written_screenshot_summary_is_grounded_in_the_real_run():
    """tests/fixtures/run_e2de1ca387cb/ai_summary.json is the summary shown in docs/screenshots/gallery-summary-ai.png
    (frontend/src/lib/fixtures/aiSummary.ts); written by hand from that run's facts, since no Groq call was made."""
    import json
    from pathlib import Path

    from tests.test_summary_facts import facts as run_facts

    data = json.loads((Path(__file__).parent / "fixtures" / "run_e2de1ca387cb" / "ai_summary.json").read_text("utf-8"))
    written = RunSummary.model_validate(data)
    out, dropped = ground(written, run_facts(price_input_per_m=0.15, price_output_per_m=0.60))
    assert dropped == 0 and out == written
