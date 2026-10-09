# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
"""SUMMARY.md. frontend/src/lib/aiSummary.test.ts checks the same payload against the same Markdown."""
from app.summary.report import to_markdown, usd

PAYLOAD = {
    "business": {"headline": "Coverage rose from 0% to 81.1%.", "outcome": "The 80% goal was reached.",
                 "efficiency": "It took 5.2 minutes.", "risks": ["Five files are untested."],
                 "recommendation": "Adopt the tests."},
    "technical": {"headline": "81.07% covered.", "what_was_tested": "Tests cover mean.go.",
                  "where_tests_live": "In output/e2de1ca387cb/tests.",
                  "gaps": [{"file": "clip.go", "detail": "12 statements uncovered."}], "suspected_bugs": [],
                  "rejected_or_failed": "", "how_to_run": "Run `go test ./...`.", "next_steps": ["Review clip.go."]},
    "dropped_sentences": 0, "tokens": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    "cost_usd": {"input": 0.0125, "output": 0.0549, "total": 0.0674},
}

EXPECTED = """# AI summary: stats

_AI-written from this run's measured data. Generated 2026-10-09 with openai/gpt-oss-120b._

## For stakeholders

### Coverage rose from 0% to 81.1%.

The 80% goal was reached.

It took 5.2 minutes.

Estimated cost: $0.07 (input $0.01, output $0.05)

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


def test_markdown_without_cost():
    md = to_markdown({**PAYLOAD, "cost_usd": None}, repo="stats", model="m", generated_at=0)
    assert "Estimated cost" not in md and "Generated 1970-01-01 with m." in md


def test_usd():
    assert [usd(v) for v in (0, 0.0005, 0.01, 0.0674, 1.5)] == ["$0.00", "$0.0005", "$0.01", "$0.07", "$1.50"]
