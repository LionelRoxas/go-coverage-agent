// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
// @vitest-environment jsdom
import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
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

  it("tells tests removed for having no assertions apart from failing tests, and what the fixer was given", () => {
    let n = 0;
    const e = (type: string, data: Record<string, unknown>): JobEvent => ({ seq: n++, ts: 1, type, data: { index: 1, file: "a.go", ...data } });
    const silent = "tests that check nothing (TestB: no t.Error*/t.Fatal* call and t passed to no helper); they are removed and the remaining tests are checked again";
    const { unmount } = renderRun([
      e("job_started", { repo_path: "r", target_coverage: 80, model: "m", options: { max_fix_attempts: 2 } }),
      e("iteration_started", { percent: 0 }),
      e("plan_created", { items: [{ file: "a.go", functions: ["A"], uncovered_statements: 1 }] }),
      e("candidate_generated", { code: "func TestA(t *testing.T) {}\nfunc TestB(t *testing.T) {}\nfunc TestC(t *testing.T) {}\n" }),
      e("validation_result", { kind: "no_assertions", output: silent, failed_tests: [], no_assertions: ["TestB"] }),
      e("tests_pruned", { tests: ["TestB"], reason: "no_assertions" }),
      e("validation_result", { kind: "test_failure", output: "--- FAIL: TestC (0.00s)\nFAIL", failed_tests: ["TestC"] }),
      e("tests_pruned", { tests: ["TestC"] }),
      e("validation_result", { kind: "accepted", output: "", failed_tests: [] }),
      e("candidate_accepted", { tests: ["TestA"], percent: 50, gain: 50 }),
    ]);
    expect(within(steps()[0]).getByText("Tests without assertions (no t.Error or t.Fatal)")).toBeInTheDocument();
    expect(within(steps()[0]).getByText(silent)).toBeInTheDocument();
    expect(within(steps()[1]).getByText("Removed the test without assertions, kept 2")).toBeInTheDocument();
    expect(within(steps()[2]).getByText("Removed the failing test, kept 1")).toBeInTheDocument();
    expect(screen.getByText("3 attempts · removed 2 tests")).toBeInTheDocument();
    unmount();

    n = 0;
    const all = "no new Test function checks its result (TestA: no t.Error*/t.Fatal* call and t passed to no helper). Every Test function must check its result with t.Error/t.Errorf/t.Fatal/t.Fatalf";
    renderRun([
      e("job_started", { repo_path: "r", target_coverage: 80, model: "m", options: { max_fix_attempts: 1 } }),
      e("iteration_started", { percent: 0 }),
      e("plan_created", { items: [{ file: "a.go", functions: ["A"], uncovered_statements: 1 }] }),
      e("candidate_generated", { code: "func TestA(t *testing.T) {}\n" }),
      e("validation_result", { kind: "no_assertions", output: all, failed_tests: [], no_assertions: ["TestA"] }),
      e("fix_attempt", { attempt: 1, kind: "no_assertions" }),
      e("candidate_generated", { code: "func TestA(t *testing.T) { t.Fatal() }\n" }),
      e("validation_result", { kind: "no_assertions", output: all, failed_tests: [], no_assertions: ["TestA"] }),
      e("candidate_rejected", { reason: "no_assertions" }),
    ]);
    expect(screen.getByText("Rewritten by the LLM fixer (fix 1 of 1), given the tests without assertions from ①")).toBeInTheDocument();
    expect(screen.getByText(/rejected after attempt 2: Tests without assertions\./)).toBeInTheDocument();
    expect(screen.queryByText(/failing test/)).not.toBeInTheDocument();
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

// Job 86b6d88b558c's events (trimmed), with the llm_request events the backend now sends before each Groq call.
const T0 = 1791539500;
const stuckFixer: JobEvent[] = [
  { seq: 0, ts: T0, type: "job_started", data: { repo_path: "semver", target_coverage: 100, options: { max_fix_attempts: 2 }, model: "openai/gpt-oss-120b" } },
  { seq: 3, ts: T0, type: "iteration_started", data: { index: 1, percent: 1.43 } },
  { seq: 4, ts: T0, type: "plan_created", data: { index: 1, items: [{ file: "constraints.go", functions: ["parseConstraint"], uncovered_statements: 100 }] } },
  { seq: 5, ts: T0, type: "llm_request", data: { index: 1, file: "constraints.go", role: "writer", reasoning_effort: "medium" } },
  { seq: 6, ts: T0 + 9, type: "llm_call", data: { index: 1, file: "constraints.go", role: "writer", prompt_tokens: 4518, completion_tokens: 3871, total_tokens: 8389, reasoning_effort: "medium" } },
  { seq: 7, ts: T0 + 9, type: "candidate_generated", data: { index: 1, file: "constraints.go", test_file: "constraints_test.go", code: "func TestParseConstraint_Uncovered(t *testing.T) {}\n" } },
  { seq: 8, ts: T0 + 9, type: "validation_result", data: { index: 1, file: "constraints.go", kind: "compile_error", output: "undefined: x", failed_tests: [] } },
  { seq: 9, ts: T0 + 9, type: "fix_attempt", data: { index: 1, file: "constraints.go", attempt: 1, kind: "compile_error" } },
  { seq: 10, ts: T0 + 10, type: "llm_request", data: { index: 1, file: "constraints.go", role: "fixer", reasoning_effort: "medium", attempt: 1 } },
];

describe("Timeline waiting on Groq", () => {
  afterEach(() => vi.useRealTimers());

  it("shows a ticking wait on the fixer step and the status chip instead of Fixing…", () => {
    vi.useFakeTimers();
    vi.setSystemTime((T0 + 10 + 102) * 1000);
    renderRun(stuckFixer);
    expect(screen.getByText("Waiting for Groq · fixer · medium reasoning · 1m 42s")).toBeInTheDocument();
    expect(screen.getByText("Waiting for Groq · 1m 42s")).toBeInTheDocument();
    expect(screen.queryByText("Fixing…")).not.toBeInTheDocument();
    expect(screen.queryByText("Running…")).not.toBeInTheDocument();
    act(() => { vi.advanceTimersByTime(1000); });
    expect(screen.getByText("Waiting for Groq · fixer · medium reasoning · 1m 43s")).toBeInTheDocument();
    expect(screen.getByText("Waiting for Groq · 1m 43s")).toBeInTheDocument();
  });

  it("shows the writer's wait before any attempt exists", () => {
    vi.useFakeTimers();
    vi.setSystemTime((T0 + 5) * 1000);
    renderRun(stuckFixer.slice(0, 4));
    expect(screen.getByText("Waiting for Groq · writer · medium reasoning · 5s")).toBeInTheDocument();
    expect(screen.getByText("Waiting for Groq · 5s")).toBeInTheDocument();
    expect(screen.queryByText("Writing…")).not.toBeInTheDocument();
    expect(screen.queryByText("No details yet.")).not.toBeInTheDocument();
  });

  it("stops the ticker once the answer arrives", () => {
    vi.useFakeTimers();
    vi.setSystemTime((T0 + 20) * 1000);
    const { rerender } = renderRun(stuckFixer);
    expect(vi.getTimerCount()).toBeGreaterThanOrEqual(1);
    const answered = [...stuckFixer, { seq: 11, ts: T0 + 20, type: "llm_call",
      data: { index: 1, file: "constraints.go", role: "fixer", prompt_tokens: 1, completion_tokens: 1, total_tokens: 1 } }];
    rerender(<Timeline iterations={answered.reduce(reduce, initialState).iterations} />);
    expect(vi.getTimerCount()).toBe(0);
    expect(screen.queryByText(/Waiting for Groq/)).not.toBeInTheDocument();
  });

  it("goes back to the plain labels once the answer arrives, and for old runs", () => {
    renderRun(movingFixed.slice(0, 7));
    expect(screen.getByText("Fixing…")).toBeInTheDocument();
    expect(screen.queryByText(/Waiting for Groq/)).not.toBeInTheDocument();
  });

  it("labels a Groq timeout instead of a generic model error", () => {
    renderRun([...stuckFixer, { seq: 11, ts: T0 + 250, type: "validation_result",
      data: { index: 1, file: "constraints.go", kind: "llm_timeout", output: "Groq did not answer within 240 s, twice", failed_tests: [] } },
      { seq: 12, ts: T0 + 250, type: "candidate_rejected", data: { index: 1, file: "constraints.go", reason: "llm_timeout" } }]);
    expect(screen.getByText(/Groq timed out: nothing to check/)).toBeInTheDocument();
    expect(screen.getByText("Groq did not answer within 240 s, twice")).toBeInTheDocument();
    expect(screen.getByText(/rejected after attempt 2: Groq timed out\./)).toBeInTheDocument();
    expect(screen.queryByText(/Model error/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Waiting for Groq/)).not.toBeInTheDocument();
  });

  it("shows an item that met a Groq outage as retried later, not rejected", () => {
    renderRun([...stuckFixer, { seq: 11, ts: T0 + 250, type: "validation_result",
      data: { index: 1, file: "constraints.go", kind: "llm_unavailable", output: "Groq is unreachable: 503", failed_tests: [] } },
      { seq: 12, ts: T0 + 250, type: "candidate_deferred", data: { index: 1, file: "constraints.go", reason: "llm_unavailable" } }]);
    expect(screen.getAllByText("Retried later (Groq unreachable)")[0]).toBeInTheDocument();
    expect(screen.getByText(/Groq unreachable: nothing to check/)).toBeInTheDocument();
    expect(screen.getByText(/does not count as failed and is planned again in a later round/)).toBeInTheDocument();
    expect(screen.queryByText(/rejected/i)).not.toBeInTheDocument();
  });

  it("marks a version that was cleaned up before its first check", () => {
    const cleaned: JobEvent[] = [...stuckFixer.slice(0, 5),
      { ...stuckFixer[5], seq: 7 },
      { seq: 8, ts: T0 + 9, type: "mechanical_repair", data: { index: 1, file: "constraints.go", repair: 0, description: "cleaned import path 'testing\\' → 'testing'" } },
      { ...stuckFixer[5], seq: 9 },
      { seq: 10, ts: T0 + 11, type: "validation_result", data: { index: 1, file: "constraints.go", kind: "accepted", output: "", failed_tests: [] } }];
    renderRun(cleaned);
    expect(steps()).toHaveLength(2);
    expect(within(steps()[0]).getByText("Not checked: auto-fixed first.")).toBeInTheDocument();
    expect(within(steps()[1]).getByText("Auto-fixed, no LLM call").parentElement)
      .toHaveTextContent("Auto-fixed, no LLM call: cleaned import path 'testing\\' → 'testing'");
  });
});
