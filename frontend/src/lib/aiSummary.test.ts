// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
// Same payload and expected Markdown as backend/tests/test_summary_report.py: Copy as Markdown equals SUMMARY.md.
import { describe, expect, it } from "vitest";
import { EMPTY_PART, toMarkdown, usd } from "./aiSummary";
import type { SummaryGenerated } from "./types";

const PAYLOAD: SummaryGenerated = {
  business: { headline: "Coverage rose from 0% to 81.1%.", outcome: "The 80% goal was reached.",
              efficiency: "It took 5.2 minutes.", risks: ["Five files are untested."], recommendation: "Adopt the tests." },
  technical: { headline: "81.07% covered.", what_was_tested: "Tests cover mean.go.",
               where_tests_live: "In output/e2de1ca387cb/tests.", gaps: [{ file: "clip.go", detail: "12 statements uncovered." }],
               suspected_bugs: [], rejected_or_failed: "", how_to_run: "Run `go test ./...`.", next_steps: ["Review clip.go."] },
  dropped_sentences: 0, tokens: { prompt_tokens: 1, completion_tokens: 1, total_tokens: 2 },
  cost_usd: { run: 0.0674, summary: 0.0014, input: 0.013, output: 0.0558, total: 0.0688 },
};

const EXPECTED = `# AI summary: stats

_AI-written from this run's measured data. Generated 2026-10-09 with openai/gpt-oss-120b._

## For stakeholders

### Coverage rose from 0% to 81.1%.

The 80% goal was reached.

It took 5.2 minutes.

Run cost $0.07 · summary $0.0014 · total $0.07 (input $0.01, output $0.06)

**Risks**

- Five files are untested.

**Recommendation:** Adopt the tests.

## For engineering teams

### 81.07% covered.

**What was tested:** Tests cover mean.go.

**Where the tests live:** In output/e2de1ca387cb/tests.

**Gaps**

- \`clip.go\`: 12 statements uncovered.

**How to run:** Run \`go test ./...\`.

**Next steps**

- Review clip.go.
`;

describe("toMarkdown", () => {
  it("matches SUMMARY.md: both sections, the note, and no empty parts", () => {
    expect(toMarkdown(PAYLOAD, { repo: "stats", model: "openai/gpt-oss-120b", generatedAt: 1791547516.4 })).toBe(EXPECTED);
  });

  it("leaves the cost out when prices are not set", () => {
    const md = toMarkdown({ ...PAYLOAD, cost_usd: undefined }, { repo: "stats", model: "m", generatedAt: 0 });
    expect(md).not.toContain("Estimated cost");
    expect(md).toContain("Generated 1970-01-01 with m.");
  });

  it("says so when the grounding check left a part empty, like the backend", () => {
    const business = { headline: "", outcome: "", efficiency: "", risks: [], recommendation: "" };
    const md = toMarkdown({ ...PAYLOAD, business, cost_usd: undefined }, { repo: "stats", model: "m", generatedAt: 0 });
    expect(md).toContain(`## For stakeholders

_${EMPTY_PART}_

## For engineering teams

### 81.07% covered.`);
    expect(md.split(EMPTY_PART)).toHaveLength(2);
  });

  it("formats dollars like the backend", () => {
    expect([0, 0.0005, 0.01, 0.0674, 1.5].map(usd)).toEqual(["$0.00", "$0.0005", "$0.01", "$0.07", "$1.50"]);
  });
});
