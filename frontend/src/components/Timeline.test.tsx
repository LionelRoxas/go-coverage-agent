// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Timeline } from "./Timeline";
import { ATTEMPT_LABEL, REJECTION_LABEL } from "@/lib/format";
import type { ItemView, IterationView } from "@/lib/runState";

const item = (over: Partial<ItemView>): ItemView => ({
  file: "stats/mean.go", functions: ["Mean"], uncovered: 4, status: "accepted",
  testPlan: [], attempts: [], pruned: [], tests: [], ...over,
});
const iteration = (items: ItemView[]): IterationView => ({ index: 1, startPercent: 10, endPercent: 20, items });

describe("Timeline", () => {
  it("shows attempts, compiler output and the accepted gain", () => {
    const accepted = item({
      status: "accepted", gain: 3.04, tests: ["TestMean"],
      attempts: [{ kind: "compile_error", output: "undefined: strings", failedTests: [] }, { kind: "mechanical_repair", output: "", failedTests: [] }],
    });
    render(<Timeline iterations={[iteration([accepted])]} />);
    expect(screen.getByText(`Attempt 1: ${ATTEMPT_LABEL.compile_error}`)).toBeInTheDocument();
    expect(screen.getByText(`Attempt 2: ${ATTEMPT_LABEL.mechanical_repair}`)).toBeInTheDocument();
    expect(ATTEMPT_LABEL.compile_error).toBe("Didn't compile");
    expect(ATTEMPT_LABEL.mechanical_repair).toBe("Auto-fixed (no LLM call)");
    expect(screen.getByText("undefined: strings")).toBeInTheDocument();
    expect(screen.getByText("Accepted +3.0 pp")).toBeInTheDocument();
  });

  it("shows the rejection reason label for a rejected item", () => {
    render(<Timeline iterations={[iteration([item({ status: "rejected", rejectReason: "too_large" })])]} />);
    expect(screen.getByText(REJECTION_LABEL.too_large)).toBeInTheDocument();
  });

  it("shows a placeholder when there are no iterations", () => {
    render(<Timeline iterations={[]} />);
    expect(screen.getByText("Nothing yet.")).toBeInTheDocument();
  });
});
