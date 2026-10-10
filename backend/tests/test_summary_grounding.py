# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
import pytest
from app.models import BusinessSummary, RunSummary, SummaryGap, SuspectedBug, TechnicalSummary
from app.summary.facts import CostFacts, FileFact, LowFile, RunFacts, TokenFacts
from pathlib import Path

from app.summary.grounding import FALLBACK_NOTE, _Checker, fill_empty, ground, number_tokens, tidy


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
    assert [(t.text, t.kind) for t in number_tokens(text)] == [
        ("0", "percent"), ("81.07", "percent"), ("81.1", "percent"), ("175,023", "count"), ("175K", "tokens"),
        ("$0.07", "currency"), ("1.2M", "tokens"), ("x2", "multiplier")]


def test_number_words_multipliers_ordinals_and_durations_are_tokens():
    text = ("Twenty-nine files, eleven rounds, a dozen tests, 3x, 3-fold, twice, doubled, the 11th round, "
            "two hours, 310s, half an hour, about an hour, 81 percent, 90 points.")
    assert [(t.text, t.kind, t.value) for t in number_tokens(text)] == [
        ("Twenty-nine", "count", 29), ("eleven", "count", 11), ("dozen", "count", 12), ("3x", "multiplier", 3),
        ("3-fold", "multiplier", 3), ("twice", "multiplier", 2), ("doubled", "multiplier", 2), ("11th", "count", 11),
        ("two", "duration", 2), ("310s", "duration", 310), ("half an hour", "duration", 0.5),
        ("an hour", "duration", 1), ("81", "percent", 81), ("90", "percent", 90)]


def test_plain_words_are_not_numbers():
    text = "Each one passes. Double-check the tests, then run `go test ./...` once more."
    assert list(number_tokens(text)) == []


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


def kept(text, **fact_overrides):
    out, dropped = ground(summary(business={"outcome": text}), facts(**fact_overrides))
    return dropped == 0


def test_dollar_amounts_must_match_the_cost_facts():
    assert not kept("It cost $5.", cost_usd=None)  # 5 would match duration_min 5.2 as a count
    assert not kept("It cost about $1.", cost_usd=None)  # 1 would match llm_fixes as a count
    assert not kept("It cost $11.")  # cost is set, but 11 is a count (rounds), not a cost
    assert kept("It cost $0.07, of which $0.05 was output.")


def test_multipliers_and_number_words_are_checked():
    for invented in ("Coverage went up 3x.", "That is x3 faster.", "A 3-fold gain.", "It ran twice as fast.",
                     "Coverage doubled.", "Half of the files are covered.", "It took two hours.",
                     "It took seven rounds.", "It took about an hour.", "It took half an hour."):
        assert not kept(invented), invented
    for true in ("It took eleven rounds.", "Twenty-nine test files were added.", "It took 5 minutes.",
                 "It took 310s.", "It took 5.2 minutes.", "Eleven rounds, then it stopped at the 11th."):
        assert kept(true), true


def test_percentages_and_counts_do_not_stand_in_for_each_other():
    assert kept("Coverage reached 81 percent, past the goal of 80%; it gained 81.07 points.")
    assert not kept("3% of the targets were rejected.")  # 3 is a count (pruned tests), not a percentage
    assert not kept("It took 81 rounds.")  # 81 is a percentage, not a count
    assert not kept("Coverage rose by 25 percent.")


def test_commands_and_ordinary_words_pass():
    assert kept("Run `go test ./...` and `go test -cover ./...` in the module root; each one passes.")
    assert kept("Double-check the 3 pruned tests before merging the 109 tests.")


def test_paths_must_be_known_files_or_the_export_folder():
    assert kept("See output/e2de1ca387cb/tests/mean_test.go and ./norm.go.")
    assert not kept("See internal/fake/clip.go.")
    assert not kept("See output/other/tests/mean_test.go.")


def test_suspected_bugs_come_from_the_facts():
    s = summary(technical={"suspected_bugs": ["Mean: returns 42 for empty input"]})
    out, _ = ground(s, facts())
    assert out.technical.suspected_bugs == ["Mean: empty input"]
    out, _ = ground(s, facts(suspected_bugs=[]))
    assert out.technical.suspected_bugs == []



# --- Real facts: run e2de1ca387cb (stats, 0% -> 81.07%) and the live run fc080d7fc500 (semver, 1.43% -> 83.33%) ---
LIVE = Path(__file__).parent / "fixtures" / "run_fc080d7fc500"


def live_facts():
    from app.models import Event, Summary
    from app.summary.facts import build_facts

    events = [Event.model_validate_json(line) for line in (LIVE / "events.jsonl").read_text("utf-8").splitlines() if line]
    summary = Summary.model_validate(next(e.data for e in events if e.type == "job_completed"))
    return build_facts(summary, events, repo="semver", model="openai/gpt-oss-120b", job_id="fc080d7fc500",
                       price_input_per_m=0.15, price_output_per_m=0.60)


def stats_facts():
    from tests.test_summary_facts import facts as run_facts
    return run_facts(price_input_per_m=0.15, price_output_per_m=0.60)


def test_zero_counts_are_kept_on_the_real_run():
    check = _Checker(stats_facts())  # its lowest files sit at 0%, which used to remove every 0 from the counts
    for true in ("All 31 targets were accepted and 0 were rejected.",
                 "There were 0 rejected targets, 0 timeouts and 0 rate-limit waits.", "There were zero rejected targets.",
                 "Rejected targets: 0.", "Coverage rose from zero to 81%.", "Coverage rose from 0 to 81.07%."):
        assert check.ok(true), true
    assert not check.ok("There were 2 rejected targets.")


def test_counts_do_not_match_percentages_or_durations():
    check = _Checker(stats_facts())
    assert not check.ok("It wrote 80 tests.")  # 80 is the goal, a percentage
    assert not check.ok("It took 310 rounds.")  # 310.1 is a duration in seconds
    assert check.ok("Five files are still at 0%.")  # five lowest files
    assert check.ok("A five-minute run.") and check.ok("About five minutes.")


def test_test_file_patterns_name_no_file():
    check = _Checker(live_facts())
    # the prompt's own wording: the sentence the live run dropped from "Where the tests live" (see the report)
    assert check.ok("The 3 test files are in output/fc080d7fc500/tests; copy the contents into the module root of "
                    "semver, keeping sub-folders, so each `_test.go` file sits next to its source file.")
    assert check.ok("Copy the `*_test.go` files into the module root.")
    assert check.ok("Copy output/fc080d7fc500/tests/version_test.go next to version.go.")
    assert not check.ok("Copy helpers_test.go too.")


def test_round_thousands_and_hundreds_match_like_k():
    check = _Checker(stats_facts())
    for true in ("Roughly 175,000 tokens.", "About 2,200 tokens per point.", "About 175 thousand tokens.",
                 "Roughly 175K tokens."):
        assert check.ok(true), true
    for invented in ("Roughly 180,000 tokens.", "About 2,300 tokens per point.", "About 200 thousand tokens."):
        assert not check.ok(invented), invented


def test_the_untested_share_and_the_margin_over_the_goal_are_allowed():
    check = _Checker(stats_facts())
    assert check.ok("The remaining 19% is untested.") and check.ok("That is 18.93% of the code.")
    assert check.ok("Coverage ended 1.07 points above the 80% goal.")
    assert not check.ok("Coverage ended 2 points above the goal.")
    assert not check.ok("It took 19 rounds.")  # a percentage is not a count


def test_spaced_percent_signs_are_tidied():
    assert tidy("From 1.43 % to 83.33\u202f% (80\u00a0% goal), +81.9 pp.") == "From 1.43% to 83.33% (80% goal), +81.9 pp."


def test_the_live_summary_is_grounded_and_tidied():
    """report.json of the live run holds the summary as grounded then (1 sentence dropped); it passes again."""
    import json
    data = json.loads((LIVE / "ai_summary.json").read_text("utf-8"))
    written = RunSummary.model_validate({"business": data["business"], "technical": data["technical"]})
    out, dropped = ground(written, live_facts())
    assert dropped == 0
    assert out.business.headline == "Coverage rose from 1.43% to 83.33%, exceeding the 80% goal."
    assert "\u202f%" not in out.model_dump_json()


def test_prediction_disagreements_are_a_grounded_count():
    text = "7 failing tests disagreed with the model's prediction and were left for review."
    out, dropped = ground(summary(technical={"rejected_or_failed": text}), facts(prediction_disagreements=7))
    assert dropped == 0 and out.technical.rejected_or_failed == text
    _, dropped = ground(summary(technical={"rejected_or_failed": text}), facts())
    assert dropped == 1


def test_assertion_free_removals_are_a_grounded_count():
    text = "7 tests without assertions were removed."
    out, dropped = ground(summary(technical={"rejected_or_failed": text}), facts(pruned_no_assertions=7))
    assert dropped == 0 and out.technical.rejected_or_failed == text
    _, dropped = ground(summary(technical={"rejected_or_failed": text}), facts())
    assert dropped == 1


REQUIRED = {"business": ["headline", "outcome", "efficiency", "recommendation"],
            "technical": ["headline", "what_was_tested", "where_tests_live", "rejected_or_failed", "how_to_run"]}


@pytest.mark.parametrize("part,name", [(p, n) for p, names in REQUIRED.items() for n in names])
def test_an_emptied_required_field_gets_deterministic_text_from_the_facts(part, name):
    """Every sentence of the field is ungrounded, so grounding empties it; the fallback fills it, marked as such,
    and leaves the other fields alone. The fallback itself passes the grounding check."""
    s = summary(**{part: {name: "It saved 40 hours of work."}})
    grounded, dropped = ground(s, facts())
    assert dropped == 1 and getattr(getattr(grounded, part), name) == ""
    out, filled = fill_empty(grounded, facts())
    text = getattr(getattr(out, part), name)
    assert filled == [f"{part}.{name}"] and text.endswith(FALLBACK_NOTE)
    assert out.model_copy(update={part: getattr(out, part).model_copy(update={name: ""})}) == grounded
    again, dropped = ground(out, facts())
    assert dropped == 0 and again == out


def test_fallback_texts_name_the_facts():
    empty = summary(business={n: "" for n in REQUIRED["business"]},
                    technical={n: "" for n in REQUIRED["technical"]})
    out, filled = fill_empty(empty, facts())
    assert len(filled) == 9
    assert out.technical.where_tests_live.startswith("The generated tests are saved in output/e2de1ca387cb/tests.")
    assert out.business.headline.startswith("Coverage went from 0% to 81.07% against a goal of 80%.")
    assert "$0.0674" in out.business.efficiency and "175,023 tokens" in out.business.efficiency
    assert out.technical.what_was_tested.startswith("The new tests raise coverage in mean.go, norm.go.")
    assert "$" not in fill_empty(empty, facts(cost_usd=None))[0].business.efficiency


def test_a_grounded_summary_needs_no_fallback():
    s = summary()
    assert fill_empty(s, facts()) == (s, [])


def test_the_live_summarys_empty_where_tests_live_is_filled():
    """run_fc080d7fc500 shipped `where_tests_live: ""` (blind review W7)."""
    import json
    data = json.loads((LIVE / "ai_summary.json").read_text("utf-8"))
    written = RunSummary.model_validate({"business": data["business"], "technical": data["technical"]})
    out, filled = fill_empty(ground(written, live_facts())[0], live_facts())
    assert filled == ["technical.where_tests_live"]
    assert out.technical.where_tests_live.startswith("The generated tests are saved in output/fc080d7fc500/tests.")
