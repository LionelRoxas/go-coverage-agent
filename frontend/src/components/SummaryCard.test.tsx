// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { SummaryCard } from "./SummaryCard";
import { STOP_REASON_LABEL } from "@/lib/format";
import type { Summary } from "@/lib/types";

const summary: Summary = {
  stop_reason: "target_reached", message: "Hit the target.", target: 80, baseline_percent: 0, final_percent: 80.5,
  iterations: [], test_files: ["a_test.go", "b_test.go"], tests_added: ["TestA", "TestB", "TestC"],
  suspected_bugs: [], per_file: [], tokens: { prompt_tokens: 1000, completion_tokens: 500 }, duration_s: 125,
};

// userEvent.setup() installs its own clipboard stub, so ours is defined after setup.
function mockClipboard(writeText: () => Promise<void>) {
  const spy = vi.fn(writeText);
  Object.defineProperty(navigator, "clipboard", { value: { writeText: spy }, configurable: true });
  return spy;
}

describe("SummaryCard", () => {
  it("renders the outcome, coverage change, counts and output path", () => {
    render(<SummaryCard summary={summary} jobId="j1" />);
    expect(screen.getByRole("heading", { name: STOP_REASON_LABEL.target_reached })).toBeInTheDocument();
    expect(screen.getByText("0.0% → 80.5%")).toBeInTheDocument();
    expect(screen.getByText("Tests added").nextSibling).toHaveTextContent("3");
    expect(screen.getByText("./output/j1/tests")).toBeInTheDocument();
  });

  it("shows the run's tokens alone, or the total with the summary call broken out", () => {
    const { rerender } = render(<SummaryCard summary={summary} jobId="j1" />);
    expect(screen.getByText("Tokens").nextSibling).toHaveTextContent(/^1\.5k$/);
    rerender(<SummaryCard summary={summary} jobId="j1" summaryTokens={500} summaryCalls={1} />);
    expect(screen.getByText("Tokens").nextSibling).toHaveTextContent("2.0k1.5k run + 500 summary");
  });

  it("copies the output path and confirms", async () => {
    const user = userEvent.setup();
    render(<SummaryCard summary={summary} jobId="j1" />);
    const writeText = mockClipboard(() => Promise.resolve());
    await user.click(screen.getByRole("button", { name: "Copy" }));
    expect(writeText).toHaveBeenCalledWith("./output/j1/tests");
    expect(await screen.findByRole("button", { name: "Copied" })).toBeInTheDocument();
  });

  it("reports when the clipboard write is rejected", async () => {
    const user = userEvent.setup();
    render(<SummaryCard summary={summary} jobId="j1" />);
    const writeText = mockClipboard(() => Promise.reject(new Error("denied")));
    await user.click(screen.getByRole("button", { name: "Copy" }));
    expect(writeText).toHaveBeenCalledWith("./output/j1/tests");
    expect(await screen.findByRole("button", { name: "Copy failed" })).toBeInTheDocument();
  });
});
