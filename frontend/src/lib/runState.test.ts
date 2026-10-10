// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
import { describe, expect, it } from "vitest";
import { initialState, reduce, summaryWaiting, waitingOn } from "./runState";
import type { JobEvent } from "./types";
import { statsSummary } from "./fixtures/aiSummary";
import { constraintsFixTooLarge, constraintsNoGain, constraintsRenamed, loadFirstTry, movingFixed, normPruned } from "./fixtures/traceEvents";

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
    expect(item.steps.map((st) => [st.source.type, st.check?.kind])).toEqual([["writer", "test_failure"], ["llm_fix", "accepted"]]);
    expect(item.testPlan[0].scenario).toBe("empty");
    expect(item.tests).toEqual(["TestMean"]);
  });

  it("records a mechanical repair as a step waiting for its code without leaving validating", () => {
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
    expect(item.steps.map((st) => st.source)).toEqual([
      { type: "writer", outputTokens: undefined }, { type: "auto_fix", description: "added import math" }]);
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
    expect(s.iterations[0].items[0].steps).toEqual([{ source: { type: "auto_fix", description: "" } }]);
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

  it("records a writer request that failed before producing code, and the rejection", () => {
    seq = 0;
    const s = run([
      ...planned(),
      ev("validation_result", { index: 1, file: "mean.go", kind: "llm_error", output: "model timed out", failed_tests: [] }),
      ev("candidate_rejected", { index: 1, file: "mean.go", reason: "llm_error" }),
    ]);
    const item = s.iterations[0].items[0];
    expect(item.steps).toEqual([{ source: { type: "writer", outputTokens: undefined },
                                  check: { kind: "llm_error", output: "model timed out", failedTests: [] } }]);
    expect(item.status).toBe("rejected");
    expect(item.rejectReason).toBe("llm_error");
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

// Driven by trimmed copies of real event logs (see ./fixtures/traceEvents.ts).
describe("reduce: attempt trace", () => {
  const itemOf = (events: JobEvent[]) => events.reduce(reduce, initialState).iterations[0].items[0];
  const shape = (events: JobEvent[]) =>
    itemOf(events).steps.map((st) => [st.source.type, st.code != null, st.check?.kind ?? null]);

  it("norm.go: writer, compile error, auto-fix, test failure, prune, accepted", () => {
    const item = itemOf(normPruned);
    expect(shape(normPruned)).toEqual([
      ["writer", true, "compile_error"], ["auto_fix", true, "test_failure"], ["prune", false, "accepted"]]);
    expect(item.steps[0].source).toEqual({ type: "writer", outputTokens: 2556 });
    expect(item.steps[0].testCount).toBe(8);
    expect(item.steps[1].source).toEqual({ type: "auto_fix", description: "added import strconv" });
    expect(item.steps[1].check?.failedTests).toHaveLength(3);
    expect(item.steps[2].source).toEqual({ type: "prune", kept: 5,
      tests: ["TestNcr_BoundaryAndOverflow", "TestNormStats_MomentsSelection", "TestNormLogCdf_PosNeg"] });
    expect(item.status).toBe("accepted");
    expect(item.gain).toBe(4.89);
    expect(item.percentBefore).toBeCloseTo(2.97);
    expect(item.percentAfter).toBe(7.86);
    expect(item.tests).toHaveLength(5);
  });

  it("load.go: accepted on the first try", () => {
    expect(shape(loadFirstTry)).toEqual([["writer", true, "accepted"]]);
    expect(itemOf(loadFirstTry).steps[0].source).toEqual({ type: "writer", outputTokens: 989 });
  });

  it("moving.go: compile error fixed by the LLM fixer", () => {
    const item = itemOf(movingFixed);
    expect(shape(movingFixed)).toEqual([["writer", true, "compile_error"], ["llm_fix", true, "accepted"]]);
    expect(item.steps[1].source).toEqual({ type: "llm_fix", attempt: 1, max: 2, given: "compile_error", givenStep: 1, outputTokens: 1634 });
  });

  it("constraints.go: every attempt adds no coverage, then it is rejected", () => {
    const item = itemOf(constraintsNoGain);
    expect(shape(constraintsNoGain)).toEqual([
      ["writer", true, "no_gain"], ["llm_fix", true, "no_gain"], ["llm_fix", true, "no_gain"]]);
    expect(item.steps[2].source).toMatchObject({ attempt: 2, max: 2, given: "no_gain", givenStep: 2 });
    expect(item.status).toBe("rejected");
    expect(item.rejectReason).toBe("no_gain");
  });

  it("a fix request that never produced code keeps its llm_error / prompt_too_large check", () => {
    expect(shape(constraintsFixTooLarge)).toEqual([["writer", true, "compile_error"], ["llm_fix", false, "llm_error"]]);
    expect(itemOf(constraintsFixTooLarge).steps[1].check?.output).toBe("targets need ~3591 tokens; budget is 2191");
    const modern = constraintsFixTooLarge.map((e) =>
      e.type === "validation_result" && e.data.kind === "llm_error" ? { ...e, data: { ...e.data, kind: "prompt_too_large" } } : e);
    expect(shape(modern)[1]).toEqual(["llm_fix", false, "prompt_too_large"]);
  });

  it("an item still in progress has a last step without a check", () => {
    const fixing = itemOf(movingFixed.slice(0, 7)); // up to fix_attempt
    expect(fixing.status).toBe("fixing");
    expect(fixing.steps[1]).toEqual({ source: { type: "llm_fix", attempt: 1, max: 2, given: "compile_error", givenStep: 1 } });
    const checking = itemOf(normPruned.slice(0, 8)); // up to the auto-fixed candidate
    expect(checking.status).toBe("validating");
    expect(checking.steps[1].check).toBeUndefined();
    expect(checking.steps[1].code).toBeDefined();
  });

  it("duplicate test names renamed twice by auto-fix", () => {
    const item = itemOf(constraintsRenamed);
    expect(shape(constraintsRenamed)).toEqual([
      ["writer", true, "compile_error"], ["auto_fix", true, "compile_error"], ["auto_fix", true, "test_failure"],
      ["prune", false, "accepted"]]);
    expect(item.steps[1].source).toEqual({ type: "auto_fix",
      description: "renamed duplicate test TestConstraintGreaterThan_Uncovered to TestConstraintGreaterThan_Uncovered_2" });
  });

  it("tolerates events with missing fields", () => {
    let n = 0;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const e = (type: string, data: Record<string, any>): JobEvent => ({ seq: n++, ts: 1, type, data });
    const s = [e("job_started", { repo_path: "r", target_coverage: 80, model: "m" }), e("iteration_started", { index: 1, percent: 0 }),
      e("plan_created", { index: 1, items: [{ file: "a.go", functions: ["A"], uncovered_statements: 1 }] }),
      e("candidate_generated", { index: 1, file: "a.go" }),
      e("tests_pruned", { index: 1, file: "a.go" }),
      e("validation_result", { index: 1, file: "a.go", kind: "accepted" }),
      e("candidate_accepted", { index: 1, file: "a.go" })].reduce(reduce, initialState);
    const item = s.iterations[0].items[0];
    expect(s.maxFixAttempts).toBeUndefined();
    expect(item.steps.map((st) => st.source.type)).toEqual(["writer", "prune"]);
    expect(item.steps[1].check).toEqual({ kind: "accepted", output: "", failedTests: [] });
    expect(item.tests).toEqual([]);
    expect(item.percentBefore).toBeUndefined();
  });
});

describe("waiting on Groq (llm_request)", () => {
  const start = () => {
    let n = 0;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const e = (type: string, data: Record<string, any>, ts = 100): JobEvent => ({ seq: n++, ts, type, data });
    const base = [e("job_started", { repo_path: "semver", target_coverage: 100, model: "m" }),
      e("iteration_started", { index: 1, percent: 0 }),
      e("plan_created", { index: 1, items: [{ file: "constraints.go", functions: ["A"], uncovered_statements: 1 }] })];
    return { e, base };
  };
  const at = { index: 1, file: "constraints.go" };
  const itemIn = (events: JobEvent[]) => run(events).iterations[0].items[0];

  it("records the pending writer request and clears it on the matching llm_call", () => {
    const { e, base } = start();
    const req = e("llm_request", { ...at, role: "writer", reasoning_effort: "medium" }, 500);
    expect(itemIn([...base, req]).pending).toEqual({ since: 500, role: "writer", effort: "medium" });
    expect(waitingOn(run([...base, req]))).toEqual({ file: "constraints.go", since: 500, role: "writer", effort: "medium" });
    const call = e("llm_call", { ...at, role: "writer", completion_tokens: 5, total_tokens: 9 });
    expect(itemIn([...base, req, call]).pending).toBeUndefined();
    expect(waitingOn(run([...base, req, call]))).toBeUndefined();
  });

  it("clears the pending fixer request on validation_result (a failed request), a rate-limit wait and cancel", () => {
    const { e, base } = start();
    const req = () => e("llm_request", { ...at, role: "fixer", reasoning_effort: "medium", attempt: 1 });
    expect(itemIn([...base, req(), e("validation_result", { ...at, kind: "llm_timeout", output: "Groq did not answer within 240 s, twice" })]).pending).toBeUndefined();
    const limited = run([...base, req(), e("rate_limited", { seconds: 12, reason: "429" })]);
    expect(limited.iterations[0].items[0].pending).toBeUndefined();
    expect(limited.activity).toMatch(/^Waiting 12s for the Groq rate limit/);
    expect(itemIn([...base, req(), e("job_cancelled", { message: "Cancelled.", final_percent: 0 })]).pending).toBeUndefined();
    expect(itemIn([...base, req(), e("job_failed", { reason: "cancelled" })]).pending).toBeUndefined();
  });

  it("clears the pending request when the item ends without an answer (too large) or is accepted", () => {
    const { e, base } = start();
    const req = e("llm_request", { ...at, role: "writer", reasoning_effort: "medium" });
    const tooLarge = run([...base, req, e("candidate_rejected", { ...at, reason: "too_large" })]);
    expect(tooLarge.iterations[0].items[0].pending).toBeUndefined();
    expect(waitingOn(tooLarge)).toBeUndefined();
    expect(itemIn([...base, e("llm_request", { ...at, role: "writer" }), e("candidate_accepted", { ...at, percent: 5, gain: 5 })]).pending)
      .toBeUndefined();
  });

  it("old runs without llm_request have nothing pending", () => {
    expect(waitingOn(run(normPruned))).toBeUndefined();
    expect(run(normPruned).iterations.flatMap((it) => it.items).every((i) => i.pending === undefined)).toBe(true);
  });
});

describe("items the run never finished", () => {
  const planned = () => [
    ev("job_started", { repo_path: "stats", model: "m", target_coverage: 80, options: {} }),
    ev("iteration_started", { index: 11, percent: 79.9 }),
    ev("plan_created", { index: 11, items: [
      { file: "ttest.go", functions: ["TTest"], uncovered_statements: 9 },
      { file: "clip.go", functions: ["Clip"], uncovered_statements: 3 },
      { file: "geometric_distribution.go", functions: ["ProbGeom"], uncovered_statements: 5 },
    ] }),
    ev("candidate_generated", { index: 11, file: "ttest.go", test_file: "ttest_test.go", test_plan: [], code: "func TestT" }),
    ev("candidate_accepted", { index: 11, file: "ttest.go", test_file: "ttest_test.go", tests: ["TestT"], percent: 81.07, gain: 1.2 }),
  ];
  const items = (s: ReturnType<typeof run>) => s.iterations[0].items;

  it("marks unstarted items as not needed when the goal was reached (run e2de1ca387cb)", () => {
    const s = run([...planned(), ev("job_completed", { stop_reason: "target_reached", final_percent: 81.07, message: "Reached" })]);
    expect(items(s).map((i) => [i.file, i.status, i.notRunReason])).toEqual([
      ["ttest.go", "accepted", undefined],
      ["clip.go", "not_run", "goal"],
      ["geometric_distribution.go", "not_run", "goal"],
    ]);
  });

  it("marks unfinished items as stopped when the run is cancelled", () => {
    const s = run([...planned(), ev("job_cancelled", { stop_reason: "cancelled", final_percent: 81.07, message: "Cancelled" })]);
    expect(items(s).filter((i) => i.status === "not_run").map((i) => i.notRunReason)).toEqual(["stopped", "stopped"]);
  });

  it("marks unfinished items as stopped when the job fails", () => {
    const s = run([...planned(), ev("job_failed", { reason: "llm_fatal", message: "boom" })]);
    expect(items(s).filter((i) => i.status === "not_run")).toHaveLength(2);
  });

  it("marks a run whose stream ended without a terminal event as interrupted, items stopped", () => {
    const writing = ev("llm_request", { index: 11, file: "clip.go", role: "writer", reasoning_effort: "medium" });
    const s = reduce(run([...planned(), writing]), { type: "stream_ended" });
    expect(s.status).toBe("interrupted");
    expect(items(s).map((i) => [i.status, i.notRunReason])).toEqual([
      ["accepted", undefined], ["not_run", "stopped"], ["not_run", "stopped"],
    ]);
    expect(waitingOn(s)).toBeUndefined();
    expect(s.percent).toBe(81.07);
  });

  it("leaves a finished run alone when its stream ends", () => {
    const s = run([...planned(), ev("job_completed", { stop_reason: "target_reached", final_percent: 81.07, message: "Reached" })]);
    expect(reduce(s, { type: "stream_ended" })).toBe(s);
  });

  it("fails a summary that never came when the stream ends", () => {
    const s = run([ev("job_started", { repo_path: "stats", model: "m", target_coverage: 80, options: { write_summary: true } }),
                   ev("job_completed", { stop_reason: "target_reached", final_percent: 81, message: "Reached" }),
                   ev("llm_request", { role: "summarizer", reasoning_effort: "medium" })]);
    expect(s.aiSummary?.status).toBe("waiting");
    const ended = reduce(s, { type: "stream_ended" });
    expect(ended.status).toBe("completed");
    expect(ended.aiSummary).toEqual({ status: "failed", pending: undefined,
                                      error: { reason: "interrupted", message: "The app stopped before the summary was written." } });
  });
});

describe("the end-of-run AI summary", () => {
  const done = { stop_reason: "target_reached", message: "Reached the 80% coverage target.", final_percent: 81.07 };
  const started = (options: Record<string, unknown>) =>
    ev("job_started", { repo_path: "stats", target_coverage: 80, options, model: "openai/gpt-oss-120b" });
  const generated = { business: statsSummary.business, technical: statsSummary.technical, dropped_sentences: 0,
                      tokens: { prompt_tokens: 2950, completion_tokens: 1480, total_tokens: 4430 } };

  it("waits after job_completed, shows the Groq wait, then the summary and its tokens", () => {
    seq = 0;
    let s = run([started({ write_summary: true }),
                 ev("llm_call", { index: 1, file: "a.go", role: "writer", prompt_tokens: 1, completion_tokens: 1, total_tokens: 1000 }),
                 ev("job_completed", done)]);
    expect(s.status).toBe("completed");
    expect(s.aiSummary).toEqual({ status: "waiting" });
    expect(summaryWaiting(s)).toBe(true);
    s = reduce(s, ev("llm_request", { role: "summarizer", reasoning_effort: "medium" }, 2000));
    expect(s.aiSummary?.pending).toEqual({ since: 2000, role: "summarizer", effort: "medium" });
    expect(waitingOn(s)).toBeUndefined(); // the run's own items are not waiting
    s = reduce(s, ev("summary_generated", generated, 2010));
    expect(s.aiSummary).toEqual({ status: "done", result: generated, generatedAt: 2010 });
    expect(summaryWaiting(s)).toBe(false);
    expect(s.tokens).toBe(5430);
  });

  it("records a failure and keeps an earlier summary", () => {
    seq = 0;
    let s = run([started({ write_summary: true }), ev("job_cancelled", { ...done, stop_reason: "cancelled" }),
                 ev("summary_generated", generated, 10)]);
    s = reduce(s, { type: "summary_requested" });
    expect(s.aiSummary?.status).toBe("waiting");
    expect(s.aiSummary?.result).toEqual(generated);
    s = reduce(s, ev("llm_request", { role: "summarizer", reasoning_effort: "medium" }));
    s = reduce(s, ev("summary_failed", { reason: "timeout", message: "Groq did not answer within 240 s, twice" }));
    expect(s.aiSummary).toMatchObject({ status: "failed", result: generated, pending: undefined,
                                        error: { reason: "timeout", message: "Groq did not answer within 240 s, twice" } });
    expect(summaryWaiting(s)).toBe(false);
  });

  it("is off when the run turned it off, and absent from older runs", () => {
    seq = 0;
    expect(run([started({ write_summary: false }), ev("job_completed", done)]).aiSummary).toEqual({ status: "off" });
    seq = 0;
    expect(run([started({}), ev("job_completed", done)]).aiSummary).toEqual({ status: "none" });
  });

  it("a rate-limit pause stops the summary's wait timer but keeps it waiting", () => {
    seq = 0;
    const s = run([started({ write_summary: true }), ev("job_completed", done),
                   ev("llm_request", { role: "summarizer", reasoning_effort: "medium" }),
                   ev("rate_limited", { seconds: 12, reason: "tpm" })]);
    expect(s.aiSummary).toEqual({ status: "waiting", pending: undefined });
  });

  it("a failed setup has no summary", () => {
    seq = 0;
    const s = run([started({ write_summary: true }), ev("job_failed", { reason: "repo_does_not_build", message: "x", output: "" })]);
    expect(s.aiSummary).toBeUndefined();
  });
});
