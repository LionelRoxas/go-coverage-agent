// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
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

  it("lists each pruned failing test with where it came from and what the code returned, under one plain sentence", () => {
    render(<Disagreements items={[TTEST, { file: "mean.go", functions: ["Mean"], test: "TestMean_Edge", lines: [] }]} />);
    expect(screen.getByRole("heading", { level: 2, name: "Prediction disagreements (2)" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Prediction disagreements (2)" })).toBeInTheDocument();
    expect(screen.getByText(DISAGREEMENT_NOTE)).toBeInTheDocument();
    expect(DISAGREEMENT_NOTE).toMatch(/dropped rather than changed/);
    expect(DISAGREEMENT_NOTE).toMatch(/either the prediction or the code is wrong/);
    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(2);
    expect(items[0]).toHaveTextContent("TestTTest_ErrorsAndEdgeCases · ttest.go: TTest, Float64Data.TTest");
    expect(items[0]).toHaveTextContent("t statistic = 0.5477225575051661, want 0");
    expect(items[1]).toHaveTextContent("No assertion lines in the output.");
    expect(screen.queryByText(/bug/i)).not.toBeInTheDocument(); // never presented as a bug
  });
});
