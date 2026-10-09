// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
import { describe, expect, it } from "vitest";
import { initialState, reduce } from "./runState";
import type { JobEvent } from "./types";

const report = (percent: number) => ({ total_statements: 10, covered_statements: percent / 10, percent, files: [], functions: [] });
let seq = 0;
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const ev = (type: string, data: Record<string, any>, ts = 1000): JobEvent => ({ seq: seq++, ts, type, data });

function run(events: JobEvent[]) {
  return events.reduce(reduce, initialState);
}

describe("reduce", () => {
  it("builds a full run view from events", () => {
    seq = 0;
    const s = run([
      ev("job_started", { repo_path: "stats", target_coverage: 80, options: {}, model: "openai/gpt-oss-120b" }),
      ev("workspace_ready", { removed_tests: ["mean_test.go"], packages: ["m"] }),
      ev("baseline_measured", { report: report(0) }),
      ev("iteration_started", { index: 1, percent: 0 }),
      ev("plan_created", { index: 1, items: [{ file: "mean.go", functions: ["Mean"], uncovered_statements: 4 }] }),
      ev("llm_call", { index: 1, file: "mean.go", role: "writer", prompt_tokens: 100, completion_tokens: 50, total_tokens: 150 }),
      ev("candidate_generated", { index: 1, file: "mean.go", test_file: "mean_test.go", test_plan: [{ scenario: "empty", target: "Mean" }], code: "func TestMean" }),
      ev("validation_result", { index: 1, file: "mean.go", kind: "test_failure", output: "--- FAIL", failed_tests: ["TestMean"] }),
      ev("fix_attempt", { index: 1, file: "mean.go", attempt: 1, kind: "test_failure" }),
      ev("validation_result", { index: 1, file: "mean.go", kind: "accepted", output: "", failed_tests: [] }),
      ev("candidate_accepted", { index: 1, file: "mean.go", test_file: "mean_test.go", tests: ["TestMean"], percent: 40, gain: 40 }),
      ev("iteration_completed", { index: 1, start_percent: 0, end_percent: 40, accepted: 1, rejected: 0 }),
    ]);
    expect(s.status).toBe("running");
    expect(s.target).toBe(80);
    expect(s.removedTests).toEqual(["mean_test.go"]);
    expect(s.percent).toBe(40);
    expect(s.tokens).toBe(150);
    expect(s.history).toEqual([{ label: "Baseline", percent: 0 }, { label: "Iter 1", percent: 40 }]);
    const item = s.iterations[0].items[0];
    expect(item.status).toBe("accepted");
    expect(item.attempts.map((a) => a.kind)).toEqual(["test_failure"]);
    expect(item.testPlan[0].scenario).toBe("empty");
    expect(item.tests).toEqual(["TestMean"]);
  });

  it("records a mechanical repair as an attempt without leaving validating", () => {
    seq = 0;
    const s = run([
      ev("job_started", { repo_path: "stats", target_coverage: 80, options: {}, model: "m" }),
      ev("iteration_started", { index: 1, percent: 0 }),
      ev("plan_created", { index: 1, items: [{ file: "mean.go", functions: ["Mean"], uncovered_statements: 4 }] }),
      ev("candidate_generated", { index: 1, file: "mean.go", test_file: "mean_test.go", test_plan: [], code: "x" }),
      ev("mechanical_repair", { index: 1, file: "mean.go", repair: 1, description: "added import math" }),
    ]);
    const item = s.iterations[0].items[0];
    expect(item.status).toBe("validating");
    expect(item.attempts).toEqual([{ kind: "mechanical_repair", output: "added import math", failedTests: [] }]);
  });

  const start = () => ev("job_started", { repo_path: "stats", target_coverage: 80, options: {}, model: "m" });

  it("uses an empty output for a legacy mechanical_repair event without a description", () => {
    seq = 0;
    const s = run([
      ev("job_started", { repo_path: "stats", target_coverage: 80, options: {}, model: "m" }),
      ev("iteration_started", { index: 1, percent: 0 }),
      ev("plan_created", { index: 1, items: [{ file: "mean.go", functions: ["Mean"], uncovered_statements: 4 }] }),
      ev("mechanical_repair", { index: 1, file: "mean.go", repair: 1 }),
    ]);
    expect(s.iterations[0].items[0].attempts).toEqual([{ kind: "mechanical_repair", output: "", failedTests: [] }]);
  });

  it("points the activity at the next item still being written after an accept or reject", () => {
    seq = 0;
    const plan = () => ev("plan_created", { index: 1, items: [
      { file: "a.go", functions: ["A"], uncovered_statements: 4 },
      { file: "b.go", functions: ["B"], uncovered_statements: 3 },
      { file: "c.go", functions: ["C"], uncovered_statements: 2 },
    ] });
    let s = run([start(), ev("iteration_started", { index: 1, percent: 0 }), plan(),
                 ev("candidate_accepted", { index: 1, file: "a.go", test_file: "a_test.go", tests: ["TestA"], percent: 10, gain: 10 })]);
    expect(s.activity).toBe("Writing tests for b.go…");
    s = reduce(s, ev("candidate_rejected", { index: 1, file: "b.go", reason: "no_gain" }));
    expect(s.activity).toBe("Writing tests for c.go…");
    s = reduce(s, ev("candidate_rejected", { index: 1, file: "c.go", reason: "no_gain" }));
    expect(s.activity).toBe("Writing tests for c.go…"); // nothing left to write: activity unchanged
  });

  it("maps a job_failed with reason cancelled to the cancelled status", () => {
    seq = 0;
    const s = run([start(), ev("job_failed", { reason: "cancelled", message: "Cancelled before the baseline finished.", output: "" })]);
    expect(s.status).toBe("cancelled");
    expect(s.activity).toBe("Cancelled.");
    expect(s.failure).toBeUndefined();
  });

  it("ignores events it has already seen (reconnect replay)", () => {
    seq = 0;
    const first = ev("job_started", { repo_path: "stats", target_coverage: 80, options: {}, model: "m" });
    const once = reduce(initialState, first);
    expect(reduce(once, first)).toBe(once);
  });

  it("shows rate-limit waits and terminal states", () => {
    seq = 0;
    let s = run([ev("job_started", { repo_path: "stats", target_coverage: 80, options: {}, model: "m" }),
                 ev("rate_limited", { seconds: 41, reason: "tpm" })]);
    expect(s.activity).toContain("41s");
    s = reduce(s, ev("job_failed", { reason: "repo_does_not_build", message: "nope", output: "x" }));
    expect(s.status).toBe("failed");
    expect(s.failure?.reason).toBe("repo_does_not_build");
  });

  const started = () => ev("job_started", { repo_path: "stats", target_coverage: 80, options: {}, model: "m" });
  const planned = () => [
    started(),
    ev("iteration_started", { index: 1, percent: 0 }),
    ev("plan_created", { index: 1, items: [{ file: "mean.go", functions: ["Mean"], uncovered_statements: 4 }] }),
  ];

  it("records rejections, pruned tests and model errors", () => {
    seq = 0;
    const s = run([
      ...planned(),
      ev("validation_result", { index: 1, file: "mean.go", kind: "llm_error", output: "model timed out", failed_tests: [] }),
      ev("tests_pruned", { index: 1, file: "mean.go", tests: ["TestBad"] }),
      ev("candidate_rejected", { index: 1, file: "mean.go", reason: "no_gain" }),
    ]);
    const item = s.iterations[0].items[0];
    expect(item.attempts).toEqual([{ kind: "llm_error", output: "model timed out", failedTests: [] }]);
    expect(item.pruned).toEqual(["TestBad"]);
    expect(item.status).toBe("rejected");
    expect(item.rejectReason).toBe("no_gain");
  });

  it("handles a cancelled job", () => {
    seq = 0;
    const summary = { stop_reason: "cancelled", message: "Cancelled by user", final_percent: 12.5 };
    const s = run([started(), ev("job_cancelled", summary)]);
    expect(s.status).toBe("cancelled");
    expect(s.percent).toBe(12.5);
    expect(s.activity).toBe("Cancelled by user");
    expect(s.summary?.stop_reason).toBe("cancelled");
  });

  it("handles a plan with no items", () => {
    seq = 0;
    const s = run([started(), ev("iteration_started", { index: 1, percent: 0 }), ev("plan_created", { index: 1, items: [] })]);
    expect(s.iterations[0].items).toEqual([]);
    expect(s.activity).toBe("Iteration 1: choosing targets…");
  });

  it("ignores a lower-seq event even when its data differs", () => {
    seq = 0;
    const s = run([ev("job_started", { repo_path: "a", target_coverage: 80, options: {}, model: "m" }), ev("llm_call", { total_tokens: 99 })]);
    const stale: JobEvent = { seq: 0, ts: 1, type: "llm_call", data: { total_tokens: 5 } };
    expect(reduce(s, stale)).toBe(s);
    expect(s.tokens).toBe(99);
  });

  it("resets to the initial state", () => {
    seq = 0;
    const s = run([started(), ev("llm_call", { total_tokens: 7 })]);
    expect(reduce(s, { type: "reset" })).toBe(initialState);
  });
});
