// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
// @vitest-environment jsdom
import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Timeline } from "./Timeline";
import { REJECTION_LABEL } from "@/lib/format";
import {
  constraintsFixTooLarge, constraintsNoGain, constraintsRenamed, loadFirstTry, movingFixed, normPruned,
} from "@/lib/fixtures/traceEvents";
import { initialState, reduce, type ItemView, type IterationView } from "@/lib/runState";
import type { JobEvent } from "@/lib/types";

const renderRun = (events: JobEvent[]) => render(<Timeline iterations={events.reduce(reduce, initialState).iterations} />);
const steps = () => Array.from(screen.getByRole("list", { name: "Attempts" }).children) as HTMLElement[];
// The fix request's validation_result, rewritten (the real log has the older llm_error kind).
const fixResult = (data: Record<string, string>) => constraintsFixTooLarge.map((e) =>
  e.type === "validation_result" && e.data.kind === "llm_error" ? { ...e, data: { ...e.data, ...data } } : e);

describe("Timeline attempt trace", () => {
  it("numbers every attempt of norm.go in a real ordered list, with source and check lines", () => {
    renderRun(normPruned);
    expect(screen.getByRole("list", { name: "Attempts" }).tagName).toBe("OL");
    expect(steps()).toHaveLength(3);
    expect(steps().map((li) => li.textContent?.slice(0, 1))).toEqual(["①", "②", "③"]);

    expect(screen.getByText("Written by the LLM · 2,556 output tokens")).toBeInTheDocument();
    const autoFix = within(steps()[1]).getByText("Auto-fixed, no LLM call");
    expect(autoFix).toHaveClass("text-accent"); // only the prefix: the check that follows may still fail
    expect(autoFix.parentElement).toHaveTextContent(/^Auto-fixed, no LLM call: added import strconv$/);
    expect(screen.getByText("Removed the 3 failing tests, kept 5")).toBeInTheDocument();
    expect(screen.getByText("Same code minus the removed tests.")).toBeInTheDocument();

    expect(within(steps()[0]).getByText("Didn't compile")).toBeInTheDocument();
    expect(within(steps()[0]).getByText(/undefined: strconv/)).toBeInTheDocument();
    expect(within(steps()[1]).getByText("3 of 8 tests failed")).toBeInTheDocument();
    expect(within(steps()[2]).getByText("Passed: compiles, go vet clean, tests pass twice, adds new coverage")).toBeInTheDocument();
  });

  it("shows the accepted-at status, the one-liner and the result line", () => {
    renderRun(normPruned);
    expect(screen.getByText("Accepted at attempt 3 · +4.9 pp")).toBeInTheDocument();
    expect(screen.getByText("3 attempts · auto-fix · removed 3 tests")).toBeInTheDocument();
    expect(screen.getByText("Result: accepted").parentElement).toHaveTextContent(
      "Result: accepted at attempt 3 · +4.9 pp (overall 3.0% → 7.9%)");
    expect(screen.getByText(/^Kept 5 tests:/)).toHaveTextContent("TestNormPpf_EdgeCases");
    expect(screen.getByText(/^norm\.go/)).toHaveTextContent("norm.go · NormPpf, NormMoment, Ncr +5 more");
  });

  it("lists each failing test once (go test -count=2 prints them twice) with its first message line", () => {
    renderRun(normPruned);
    const failing = steps()[1];
    expect(within(failing).getAllByText("TestNcr_BoundaryAndOverflow")).toHaveLength(1);
    expect(within(failing).getAllByText("norm_test.go:76: expected overflow sentinel MaxInt, got 7219428434016265740")).toHaveLength(1);
    expect(within(failing).getByText("norm_test.go:118: mismatch at 0: got 4 want 0")).toBeInTheDocument();
  });

  it("keeps the raw go test output behind a toggle", () => {
    renderRun(normPruned);
    const toggle = within(steps()[1]).getByText("Raw output");
    const details = toggle.closest("details") as HTMLDetailsElement;
    expect(details.open).toBe(false);
    expect(details.querySelector("pre")?.textContent).toContain("coverage: 10.3% of statements");
    fireEvent.click(toggle);
    expect(details.open).toBe(true);
  });

  it("toggles the code of an attempt", () => {
    renderRun(normPruned);
    const button = within(steps()[0]).getByRole("button", { name: "View code" });
    expect(button).toHaveAttribute("aria-expanded", "false");
    expect(within(steps()[0]).queryByText(/func TestNormPpf_EdgeCases/)).not.toBeInTheDocument();
    fireEvent.click(button);
    expect(button).toHaveTextContent("Hide code");
    expect(button).toHaveAttribute("aria-expanded", "true");
    expect(within(steps()[0]).getByText(/func TestNormPpf_EdgeCases/)).toBeInTheDocument();
    expect(within(steps()[2]).queryByRole("button")).not.toBeInTheDocument(); // the prune made no new code
  });

  it("shows a first-try accept", () => {
    renderRun(loadFirstTry);
    expect(screen.getByText("Accepted at attempt 1 · +3.0 pp")).toBeInTheDocument();
    expect(screen.getByText("1 attempt")).toBeInTheDocument();
    expect(screen.getByText("Written by the LLM · 989 output tokens")).toBeInTheDocument();
  });

  it("says what the LLM fixer was given and from which attempt", () => {
    renderRun(movingFixed);
    expect(screen.getByText("Rewritten by the LLM fixer (fix 1 of 2), given the compile error from ① · 1,634 output tokens")).toBeInTheDocument();
    expect(screen.getByText("2 attempts · LLM fix")).toBeInTheDocument();
    expect(screen.getByText("Accepted at attempt 2 · +5.2 pp")).toBeInTheDocument();
  });

  it("shows a rejection after the last attempt and that nothing changed", () => {
    renderRun(constraintsNoGain);
    expect(screen.getByText("Rejected after attempt 3")).toBeInTheDocument();
    expect(screen.getByText("3 attempts · 2 LLM fixes")).toBeInTheDocument();
    expect(screen.getByText("Rewritten by the LLM fixer (fix 2 of 2), given the no-new-coverage result from ② · 1,092 output tokens")).toBeInTheDocument();
    expect(screen.getByText(/rejected after attempt 3: No new coverage\. Changes rolled back, coverage unchanged\./)).toBeInTheDocument();
    // only the final failed check uses the danger color; checks that were followed by another attempt stay muted
    const checks = steps().map((li) => within(li).getByText("No new coverage").className);
    expect(checks).toEqual(["text-muted", "text-muted", "text-danger"]);
  });

  it("explains a fix request that never reached the model (older llm_error log)", () => {
    renderRun(constraintsFixTooLarge);
    expect(screen.getByText("Fix request too large — no model call (fix 1 of 2)")).toBeInTheDocument();
    expect(screen.getByText("targets need ~3591 tokens; budget is 2191")).toBeInTheDocument();
    expect(within(steps()[1]).queryByRole("button")).not.toBeInTheDocument();
    // the result agrees with the step: nothing was wrong with the model
    expect(screen.getByText(/rejected after attempt 2: Fix request too large for the prompt budget \(no model call\)\. Changes rolled back/)).toBeInTheDocument();
    expect(screen.queryByText(/Model error/)).not.toBeInTheDocument();
    expect(within(steps()[1]).getByText(/Prompt too large \(no model call\): nothing to check/)).toBeInTheDocument();
  });

  it("explains a prompt_too_large fix request and a fix request with a model error", () => {
    const { unmount } = renderRun(fixResult({ kind: "prompt_too_large", output: "fixer prompt does not fit" }));
    expect(screen.getByText("Fix request too large — no model call (fix 1 of 2)")).toBeInTheDocument();
    unmount();
    renderRun(fixResult({ output: "model timed out" }));
    expect(screen.getByText("Fix request failed (fix 1 of 2)")).toBeInTheDocument();
    expect(screen.getByText(/rejected after attempt 2: Model error\./)).toBeInTheDocument();
    expect(screen.getByText(/Model error: nothing to check/)).toBeInTheDocument();
  });

  it("names the safety guard and what the fixer was given after it", () => {
    let n = 0;
    const e = (type: string, data: Record<string, unknown>): JobEvent => ({ seq: n++, ts: 1, type, data: { index: 1, file: "a.go", ...data } });
    renderRun([
      e("job_started", { repo_path: "r", target_coverage: 80, model: "m", options: { max_fix_attempts: 2 } }),
      e("iteration_started", { percent: 0 }),
      e("plan_created", { items: [{ file: "a.go", functions: ["A"], uncovered_statements: 1 }] }),
      e("candidate_generated", { code: "func helper() {}\n" }),
      e("validation_result", { kind: "guard_rejected", output: "no `func TestXxx(t *testing.T)` found", failed_tests: [] }),
      e("fix_attempt", { attempt: 1, kind: "guard_rejected" }),
      e("candidate_generated", { code: "func TestA(t *testing.T) {}\n" }),
      e("validation_result", { kind: "test_failure", output: "panic: boom\nFAIL", failed_tests: [] }),
    ]);
    expect(screen.getByText("Rejected by the safety guard")).toBeInTheDocument();
    expect(screen.getByText("no `func TestXxx(t *testing.T)` found")).toBeInTheDocument();
    expect(screen.getByText("Rewritten by the LLM fixer (fix 1 of 2), given the safety guard's rejection from ①")).toBeInTheDocument();
    expect(screen.getByText("Tests failed")).toBeInTheDocument(); // a panic has no per-test FAIL lines to count
  });

  it("shows two duplicate-name auto-fixes", () => {
    renderRun(constraintsRenamed);
    expect(screen.getByText("4 attempts · 2 auto-fixes · removed 1 test")).toBeInTheDocument();
    expect(screen.getByText(/^Removed the failing test, kept \d+$/)).toBeInTheDocument();
    expect(screen.getByText(/renamed duplicate test TestConstraintGreaterThan_Uncovered to/)).toBeInTheDocument();
  });

  it("shows an item still being fixed", () => {
    renderRun(movingFixed.slice(0, 7));
    expect(screen.getByText("Running…")).toBeInTheDocument();
    expect(screen.getByText("Fixing…")).toBeInTheDocument();
    expect(screen.getByText("Rewritten by the LLM fixer (fix 1 of 2), given the compile error from ①")).toBeInTheDocument();
  });

  it("shows checking for a version that is still being validated", () => {
    renderRun(normPruned.slice(0, 8));
    expect(screen.getByText("Checking…")).toBeInTheDocument();
  });
});

const item = (over: Partial<ItemView>): ItemView => ({
  file: "stats/mean.go", functions: ["Mean"], uncovered: 4, status: "writing", testPlan: [], steps: [], tests: [], ...over,
});
const iteration = (items: ItemView[]): IterationView => ({ index: 1, startPercent: 10, endPercent: 20, items });

describe("Timeline", () => {
  it("explains a too-large item that was skipped without any attempt", () => {
    render(<Timeline iterations={[iteration([item({ status: "rejected", rejectReason: "too_large", functions: ["A", "B"] })])]} />);
    expect(screen.getByText(REJECTION_LABEL.too_large)).toBeInTheDocument();
    expect(screen.getByText(/skipped: too large for one request, even after narrowing it to fewer functions/)).toBeInTheDocument();
  });

  it("shows writing for an item with no events yet, and the placeholder", () => {
    const { rerender } = render(<Timeline iterations={[iteration([item({})])]} />);
    expect(screen.getByText("Writing…")).toBeInTheDocument();
    expect(screen.getByText("No details yet.")).toBeInTheDocument();
    rerender(<Timeline iterations={[]} />);
    expect(screen.getByText("Nothing yet.")).toBeInTheDocument();
  });
});
