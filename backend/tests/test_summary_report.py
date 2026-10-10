# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
"""SUMMARY.md. frontend/src/lib/aiSummary.test.ts checks the same payload against the same Markdown."""
from app.models import Disagreement
from app.summary.report import DISAGREEMENTS, EMPTY, disagreement_line, to_markdown, usd

PAYLOAD = {
    "business": {"headline": "Coverage rose from 0% to 81.1%.", "outcome": "The 80% goal was reached.",
                 "efficiency": "It took 5.2 minutes.", "risks": ["Five files are untested."],
                 "recommendation": "Adopt the tests."},
    "technical": {"headline": "81.07% covered.", "what_was_tested": "Tests cover mean.go.",
                  "where_tests_live": "In output/e2de1ca387cb/tests.",
                  "gaps": [{"file": "clip.go", "detail": "12 statements uncovered."}], "suspected_bugs": [],
                  "rejected_or_failed": "", "how_to_run": "Run `go test ./...`.", "next_steps": ["Review clip.go."]},
    "dropped_sentences": 0, "tokens": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    "cost_usd": {"run": 0.0674, "summary": 0.0014, "input": 0.013, "output": 0.0558, "total": 0.0688},
}

EXPECTED = """# AI summary: stats

_AI-written from this run's measured data. Generated 2026-10-09 with openai/gpt-oss-120b._

## For stakeholders

### Coverage rose from 0% to 81.1%.

The 80% goal was reached.

It took 5.2 minutes.

Run cost $0.0674 · this summary call $0.0014 · run + this call $0.0688 (input $0.0130, output $0.0558)

**Risks**

- Five files are untested.

**Recommendation:** Adopt the tests.

## For engineering teams

### 81.07% covered.

**What was tested:** Tests cover mean.go.

**Where the tests live:** In output/e2de1ca387cb/tests.

**Gaps**

- `clip.go`: 12 statements uncovered.

**How to run:** Run `go test ./...`.

**Next steps**

- Review clip.go.
"""


def test_markdown_has_both_sections_the_note_and_skips_empty_parts():
    generated_at = 1791547516.4  # 2026-10-09 UTC
    assert to_markdown(PAYLOAD, repo="stats", model="openai/gpt-oss-120b", generated_at=generated_at) == EXPECTED


def test_disagreements_are_listed_after_suspected_bugs_and_never_as_bugs():
    line = disagreement_line(Disagreement(file="ttest.go", functions=["TTest", "Float64Data.TTest"],
                                          test="TestTTest_Edge", lines=["TestTTest_Edge/a: x_test.go:4: got 1, want 0",
                                                                        "TestTTest_Edge/b: x_test.go:9: got 2, want 3"],
                                          outcome="kept"))
    assert line == ("`TestTTest_Edge` (ttest.go: TTest, Float64Data.TTest): TestTTest_Edge/a: x_test.go:4: got 1, want 0"
                    " | TestTTest_Edge/b: x_test.go:9: got 2, want 3 (removed when it failed; a test of this name was kept"
                    " after a fix and may now expect the code's value)")
    older = Disagreement(file="a.go", functions=["A"], test="TestA")  # an older report: no outcome
    assert disagreement_line(older) == "`TestA` (a.go: A): no assertion output (removed when it failed)"
    to_fixer = Disagreement(file="a.go", functions=["A"], test="TestA", pruned=False, outcome="not_accepted")
    assert disagreement_line(to_fixer).endswith("(sent to the Fixer when it failed; its attempt was not accepted)")
    dropped = Disagreement(file="a.go", functions=["A"], test="TestA", outcome="dropped")
    assert disagreement_line(dropped).endswith("(removed when it failed; not in the accepted tests)")
    payload = {**PAYLOAD, "technical": {**PAYLOAD["technical"], "suspected_bugs": ["Mean: odd"]},
               "disagreements": [line]}
    md = to_markdown(payload, repo="stats", model="openai/gpt-oss-120b", generated_at=1791547516.4)
    assert f"**Suspected bugs**\n\n- Mean: odd\n\n**{DISAGREEMENTS}**\n\n- {line}\n\n**How to run:**" in md
    assert "not confirmed bugs" in DISAGREEMENTS
    empty = to_markdown({**PAYLOAD, "disagreements": []}, repo="stats", model="openai/gpt-oss-120b",
                        generated_at=1791547516.4)
    assert empty == EXPECTED  # none (or an older payload without the key): no section


def test_markdown_without_cost():
    md = to_markdown({**PAYLOAD, "cost_usd": None}, repo="stats", model="m", generated_at=0)
    assert "Estimated cost" not in md and "Generated 1970-01-01 with m." in md


def test_usd():
    assert [usd(v) for v in (0, 0.0005, 0.0232, 0.9999, 1, 12.345)] == ["$0.0000", "$0.0005", "$0.0232", "$0.9999",
                                                                     "$1.00", "$12.35"]


def test_a_part_left_empty_by_the_grounding_check_says_so():
    empty_business = {"headline": "", "outcome": "", "efficiency": "", "risks": [], "recommendation": ""}
    md = to_markdown({**PAYLOAD, "business": empty_business, "cost_usd": None}, repo="stats", model="m", generated_at=0)
    assert f"## For stakeholders\n\n_{EMPTY}_\n\n## For engineering teams\n\n### 81.07% covered." in md
    assert md.count(EMPTY) == 1


def test_test_quality_follows_the_cost_and_what_was_tested_only_when_written():
    business = {**PAYLOAD["business"], "test_quality": "The tests caught 43 of 60 planted bugs."}
    technical = {**PAYLOAD["technical"], "test_quality": "Mutation score 71.7%."}
    md = to_markdown({**PAYLOAD, "business": business, "technical": technical}, repo="stats", model="m",
                     generated_at=1791547516.4)
    assert ("(input $0.0130, output $0.0558)\n\n**Test quality:** The tests caught 43 of 60 planted bugs.\n\n**Risks**"
            in md)
    assert "**What was tested:** Tests cover mean.go.\n\n**Test quality:** Mutation score 71.7%.\n\n**Where" in md
    empty = {**PAYLOAD, "business": {**business, "test_quality": ""}, "technical": {**technical, "test_quality": ""}}
    assert "Test quality" not in to_markdown(empty, repo="stats", model="m", generated_at=1791547516.4)
