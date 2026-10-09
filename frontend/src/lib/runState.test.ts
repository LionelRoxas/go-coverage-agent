// AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
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
      ev("mechanical_repair", { index: 1, file: "mean.go", repair: 'added import "math"' }),
    ]);
    const item = s.iterations[0].items[0];
    expect(item.status).toBe("validating");
    expect(item.attempts).toEqual([{ kind: "mechanical_repair", output: 'added import "math"', failedTests: [] }]);
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
});
