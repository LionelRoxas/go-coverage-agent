// AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
// Pure reducer: the same code handles live events and replay after a refresh or reconnect.
import type { CoverageReport, JobEvent, Scenario, Summary } from "./types";

export type ItemStatus = "writing" | "validating" | "fixing" | "accepted" | "rejected";
export type Attempt = { kind: string; output: string; failedTests: string[] };
export type ItemView = {
  file: string;
  functions: string[];
  uncovered: number;
  status: ItemStatus;
  testPlan: Scenario[];
  code?: string;
  attempts: Attempt[];
  pruned: string[];
  tests: string[];
  gain?: number;
  rejectReason?: string;
};
export type IterationView = { index: number; startPercent: number; endPercent?: number; items: ItemView[] };
export type RunState = {
  lastSeq: number;
  status: "connecting" | "running" | "completed" | "failed" | "cancelled";
  repoPath?: string;
  model?: string;
  startedAt?: number;
  target: number;
  removedTests: string[];
  baseline?: CoverageReport;
  percent: number;
  history: { label: string; percent: number }[];
  iterations: IterationView[];
  activity: string;
  tokens: number;
  summary?: Summary;
  failure?: { reason: string; message: string; output: string };
};

export const initialState: RunState = {
  lastSeq: -1,
  status: "connecting",
  target: 0,
  removedTests: [],
  percent: 0,
  history: [],
  iterations: [],
  activity: "Connecting…",
  tokens: 0,
};

function withIteration(s: RunState, index: number, fn: (it: IterationView) => IterationView): RunState {
  return { ...s, iterations: s.iterations.map((it) => (it.index === index ? fn(it) : it)) };
}

function withItem(s: RunState, index: number, file: string, fn: (item: ItemView) => ItemView): RunState {
  return withIteration(s, index, (it) => ({ ...it, items: it.items.map((i) => (i.file === file ? fn(i) : i)) }));
}

export function reduce(state: RunState, ev: JobEvent): RunState {
  if (ev.seq <= state.lastSeq) return state;
  const s: RunState = { ...state, lastSeq: ev.seq };
  const d = ev.data;
  switch (ev.type) {
    case "job_started":
      return { ...s, status: "running", repoPath: d.repo_path, model: d.model, target: d.target_coverage,
               startedAt: ev.ts, activity: "Preparing a working copy…" };
    case "workspace_ready":
      return { ...s, removedTests: d.removed_tests, activity: "Measuring baseline coverage…" };
    case "baseline_measured":
      return { ...s, baseline: d.report, percent: d.report.percent,
               history: [{ label: "Baseline", percent: d.report.percent }], activity: "Planning what to test…" };
    case "iteration_started":
      return { ...s, iterations: [...s.iterations, { index: d.index, startPercent: d.percent, items: [] }],
               activity: `Iteration ${d.index}: choosing targets…` };
    case "plan_created":
      return {
        ...withIteration(s, d.index, (it) => ({
          ...it,
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          items: d.items.map((i: any) => ({ file: i.file, functions: i.functions, uncovered: i.uncovered_statements,
                                            status: "writing", testPlan: [], attempts: [], pruned: [], tests: [] })),
        })),
        activity: d.items.length ? `Writing tests for ${d.items[0].file}…` : s.activity,
      };
    case "llm_call":
      return { ...s, tokens: d.total_tokens };
    case "rate_limited":
      return { ...s, activity: `Waiting ${Math.round(d.seconds)}s for the Groq rate limit (${d.reason === "tpm" ? "tokens per minute" : "HTTP 429"})…` };
    case "candidate_generated":
      return { ...withItem(s, d.index, d.file, (i) => ({ ...i, status: "validating", testPlan: d.test_plan, code: d.code })),
               activity: `Compiling and running tests for ${d.file}…` };
    case "validation_result":
      return d.kind === "accepted" ? s : withItem(s, d.index, d.file, (i) => ({
        ...i, attempts: [...i.attempts, { kind: d.kind, output: d.output, failedTests: d.failed_tests }] }));
    case "mechanical_repair":
      return withItem(s, d.index, d.file, (i) => ({
        ...i, attempts: [...i.attempts, { kind: "mechanical_repair", output: d.repair, failedTests: [] }] }));
    case "tests_pruned":
      return withItem(s, d.index, d.file, (i) => ({ ...i, pruned: [...i.pruned, ...d.tests] }));
    case "fix_attempt":
      return { ...withItem(s, d.index, d.file, (i) => ({ ...i, status: "fixing" })),
               activity: `Fixing ${String(d.kind).replace("_", " ")} in ${d.file} (attempt ${d.attempt})…` };
    case "candidate_accepted":
      return { ...withItem(s, d.index, d.file, (i) => ({ ...i, status: "accepted", tests: d.tests, gain: d.gain })),
               percent: d.percent };
    case "candidate_rejected":
      return withItem(s, d.index, d.file, (i) => ({ ...i, status: "rejected", rejectReason: d.reason }));
    case "iteration_completed":
      return { ...withIteration(s, d.index, (it) => ({ ...it, endPercent: d.end_percent })),
               history: [...s.history, { label: `Iter ${d.index}`, percent: d.end_percent }] };
    case "job_completed":
    case "job_cancelled":
      return { ...s, status: ev.type === "job_completed" ? "completed" : "cancelled", summary: d as Summary,
               percent: d.final_percent, activity: d.message };
    case "job_failed":
      return { ...s, status: "failed", failure: { reason: d.reason, message: d.message, output: d.output },
               activity: d.message };
    default:
      return s;
  }
}
