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

  it("shows the description of an auto-fixed attempt, and no output block when it is empty", () => {
    const withText = item({ attempts: [{ kind: "mechanical_repair", output: "added import strings", failedTests: [] }] });
    const { container, rerender } = render(<Timeline iterations={[iteration([withText])]} />);
    expect(screen.getByText("added import strings")).toBeInTheDocument();
    expect(container.querySelectorAll("pre")).toHaveLength(1);

    const legacy = item({ attempts: [{ kind: "mechanical_repair", output: "", failedTests: [] }] });
    rerender(<Timeline iterations={[iteration([legacy])]} />);
    expect(screen.getByText(`Attempt 1: ${ATTEMPT_LABEL.mechanical_repair}`)).toBeInTheDocument();
    expect(container.querySelectorAll("pre")).toHaveLength(0);
  });

  it("shows the rejection reason label for a rejected item", () => {
    render(<Timeline iterations={[iteration([item({ status: "rejected", rejectReason: "too_large" })])]} />);
    expect(screen.getByText(REJECTION_LABEL.too_large)).toBeInTheDocument();
  });

  it("labels an oversized prompt honestly and still renders older model-error events", () => {
    const tooLarge = item({
      status: "rejected", rejectReason: "prompt_too_large",
      attempts: [{ kind: "prompt_too_large", output: "targets need ~3591 tokens; budget is 2191", failedTests: [] }],
    });
    const legacy = item({
      file: "stats/sum.go", status: "rejected", rejectReason: "llm_error",
      attempts: [{ kind: "llm_error", output: "model timed out", failedTests: [] }],
    });
    render(<Timeline iterations={[iteration([tooLarge, legacy])]} />);
    expect(screen.getByText("Prompt too large (no model call)")).toBeInTheDocument();
    expect(screen.getByText("Attempt 1: Prompt too large (no model call)")).toBeInTheDocument();
    expect(screen.getByText("Model error")).toBeInTheDocument();
    expect(screen.getByText("Attempt 1: Model error")).toBeInTheDocument();
  });

  it("shows a placeholder when there are no iterations", () => {
    render(<Timeline iterations={[]} />);
    expect(screen.getByText("Nothing yet.")).toBeInTheDocument();
  });
});
