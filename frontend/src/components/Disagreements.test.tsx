// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
// @vitest-environment jsdom
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Disagreements } from "./Disagreements";
import { DISAGREEMENT_NOTE } from "@/lib/format";
import type { Disagreement } from "@/lib/types";

const TTEST: Disagreement = {
  file: "ttest.go", functions: ["TTest", "Float64Data.TTest"], test: "TestTTest_ErrorsAndEdgeCases",
  lines: ["TestTTest_ErrorsAndEdgeCases/equal_means: ttest_test.go:41: t statistic = 0.5477225575051661, want 0"],
};

describe("Disagreements", () => {
  it("renders nothing when the run had none", () => {
    const { container } = render(<Disagreements items={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("lists each disagreement with where it came from, what the code returned and what became of it, under one plain sentence", () => {
    render(<Disagreements items={[
      { ...TTEST, pruned: true, outcome: "kept" },
      { file: "mean.go", functions: ["Mean"], test: "TestMean_Edge", lines: [] }, // an older run: no pruned / outcome
      { file: "mean.go", functions: ["Mean"], test: "TestMean_All", lines: ["TestMean_All: mean_test.go:3: got 1, want 2"],
        pruned: false, outcome: "not_accepted" },
    ]} />);
    expect(screen.getByRole("heading", { level: 2, name: "Prediction disagreements (3)" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Prediction disagreements (3)" })).toBeInTheDocument();
    expect(screen.getByText(DISAGREEMENT_NOTE)).toBeInTheDocument();
    expect(DISAGREEMENT_NOTE).toMatch(/at that point the failing test was removed/);
    expect(DISAGREEMENT_NOTE).toMatch(/either the prediction or the code is wrong/);
    expect(DISAGREEMENT_NOTE).not.toMatch(/rather than changed/); // a later fix may have adopted the code's value
    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(3);
    expect(items[0]).toHaveTextContent("TestTTest_ErrorsAndEdgeCases · ttest.go: TTest, Float64Data.TTest");
    // the line without the test name the entry already shows
    expect(within(items[0]).getByText("/equal_means: ttest_test.go:41: t statistic = 0.5477225575051661, want 0")).toBeInTheDocument();
    expect(items[0]).toHaveTextContent("Removed when it failed; a test of this name was kept after a fix and may now expect the code's value.");
    expect(items[1]).toHaveTextContent("No assertion lines in the output.");
    expect(items[1]).toHaveTextContent(/Removed when it failed\.$/);
    expect(within(items[2]).getByText("mean_test.go:3: got 1, want 2")).toBeInTheDocument();
    expect(items[2]).toHaveTextContent("Sent to the Fixer when it failed; its attempt was not accepted.");
    expect(screen.queryByText(/bug/i)).not.toBeInTheDocument(); // never presented as a bug
  });
});
