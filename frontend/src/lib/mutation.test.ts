// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
import { describe, expect, it } from "vitest";
import { initialState, mutationRunning, reduce } from "./runState";
import type { JobEvent } from "./types";

let seq = 0;
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const ev = (type: string, data: Record<string, any>): JobEvent => ({ seq: seq++, ts: 1000, type, data });
const mutant = (index: number, status: string) =>
  ({ index, file: "mut.go", line: 7, original: "+", mutated: "-", op: "arithmetic", status, before: "return a + b", after: "return a - b" });
const completed = () => [
  ev("job_started", { repo_path: "m", target_coverage: 80, options: { write_summary: false }, model: "x" }),
  ev("job_completed", { stop_reason: "target_reached", message: "done", final_percent: 80, tokens: { prompt_tokens: 0, completion_tokens: 0 } }),
];

describe("reduce: mutation test", () => {
  it("follows the four events and keeps the result", () => {
    seq = 0;
    let s = completed().reduce(reduce, initialState);
    s = reduce(s, { type: "mutation_requested" });
    expect(s.mutation).toEqual({ status: "running", mutants: [] });
    expect(mutationRunning(s)).toBe(true);
    s = reduce(s, ev("mutation_started", { total: 2 }));
    s = reduce(s, ev("mutant_result", mutant(1, "killed")));
    expect(s.mutation).toMatchObject({ status: "running", total: 2, mutants: [{ index: 1, status: "killed" }] });
    s = reduce(s, ev("mutant_result", mutant(2, "survived")));
    const result = { total: 2, killed: 1, survived: 1, invalid: 0, timeouts: 0, score: 50, per_file: [],
                     mutants: [mutant(1, "killed"), mutant(2, "survived")] };
    s = reduce(s, ev("mutation_completed", result));
    expect(s.mutation).toEqual({ status: "done", total: 2, mutants: result.mutants, result });
    expect(mutationRunning(s)).toBe(false);
    expect(s.status).toBe("completed");
    s = reduce(s, ev("mutation_failed", { reason: "baseline_failed", message: "no", output: "FAIL" }));
    expect(s.mutation).toMatchObject({ status: "failed", error: { reason: "baseline_failed", message: "no", output: "FAIL" } });
  });

  it("a failure before mutation_started still ends the test", () => {
    seq = 0;
    const s = reduce(reduce(completed().reduce(reduce, initialState), { type: "mutation_requested" }),
                     ev("mutation_failed", { reason: "cancelled", message: "Cancelled." }));
    expect(s.mutation).toEqual({ status: "failed", mutants: [], error: { reason: "cancelled", message: "Cancelled.", output: undefined } });
  });

  it("an interrupted run's replay is not shown as running, and a test cut by a restart ends as failed", () => {
    seq = 0;
    let s = [ev("job_started", { repo_path: "m", target_coverage: 80, options: {}, model: "x" }),
             ev("mutation_started", { total: 3 }), ev("mutant_result", mutant(1, "timeout"))].reduce(reduce, initialState);
    expect(s.status).toBe("interrupted");
    s = reduce(s, { type: "stream_ended", saved: "interrupted" });
    expect(s.mutation).toMatchObject({ status: "failed", error: { reason: "interrupted" }, mutants: [{ status: "timeout" }] });
  });
});
