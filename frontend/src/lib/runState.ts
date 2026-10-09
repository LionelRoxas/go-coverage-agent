// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
// Pure reducer: the same code handles live events and replay after a refresh or reconnect.
import type { CoverageReport, JobEvent, Scenario, Summary } from "./types";

export type ItemStatus = "writing" | "validating" | "fixing" | "accepted" | "rejected";

// What checking one version of the test code found (validation_result).
export type Check = { kind: string; output: string; failedTests: string[] };
// Where one version of the test code came from.
export type StepSource =
  | { type: "writer"; outputTokens?: number }
  | { type: "auto_fix"; description: string }
  | { type: "prune"; tests: string[]; kept?: number }
  | { type: "llm_fix"; attempt: number; max?: number; given: string; givenStep?: number; outputTokens?: number };
// One attempt: a version of the test code plus the result of checking it (no check yet while it runs).
export type Step = { source: StepSource; code?: string; testCount?: number; check?: Check };

export type ItemView = {
  file: string;
  functions: string[];
  uncovered: number;
  status: ItemStatus;
  testPlan: Scenario[];
  code?: string;
  steps: Step[];
  tests: string[];
  gain?: number;
  percentBefore?: number;
  percentAfter?: number;
  rejectReason?: string;
  writerTokens?: number; // the writer's llm_call arrives just before its candidate_generated
};
export type IterationView = { index: number; startPercent: number; endPercent?: number; items: ItemView[] };
export type RunState = {
  lastSeq: number;
  status: "connecting" | "running" | "completed" | "failed" | "cancelled";
  repoPath?: string;
  model?: string;
  startedAt?: number;
  target: number;
  maxFixAttempts?: number;
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

// After an item finishes, point the activity line at the next item still waiting for its tests.
function nextWriting(s: RunState, index: number): string {
  const next = s.iterations.find((it) => it.index === index)?.items.find((i) => i.status === "writing");
  return next ? `Writing tests for ${next.file}…` : s.activity;
}

const countTests = (code: string) => (code.match(/^func Test\w*\s*\(/gm) ?? []).length;
const last = <T>(xs: T[]): T | undefined => xs[xs.length - 1];
const withLast = (steps: Step[], fn: (st: Step) => Step) => [...steps.slice(0, -1), fn(steps[steps.length - 1])];

// A new candidate fills the step waiting for code (auto-fix, LLM fix); otherwise it is the writer's first version.
function addCode(i: ItemView, code: string): ItemView {
  const prev = last(i.steps);
  const testCount = countTests(code) || undefined;
  if (prev && !prev.check && prev.code == null && prev.source.type !== "prune")
    return { ...i, steps: withLast(i.steps, (st) => ({ ...st, code, testCount })) };
  return { ...i, writerTokens: undefined,
           steps: [...i.steps, { source: { type: "writer", outputTokens: i.writerTokens }, code, testCount }] };
}

function addCheck(i: ItemView, check: Check): ItemView {
  const prev = last(i.steps);
  if (prev && !prev.check) return { ...i, steps: withLast(i.steps, (st) => ({ ...st, check })) };
  // a check with no version before it: the writer's request failed (or an old log missed the candidate)
  return { ...i, steps: [...i.steps, { source: { type: "writer", outputTokens: i.writerTokens }, check }] };
}

export type RunAction = JobEvent | { type: "reset" };

export function reduce(state: RunState, ev: RunAction): RunState {
  if (!("seq" in ev)) return initialState; // "reset": a different job was opened
  if (ev.seq <= state.lastSeq) return state;
  const s: RunState = { ...state, lastSeq: ev.seq };
  const d = ev.data;
  switch (ev.type) {
    case "job_started":
      return { ...s, status: "running", repoPath: d.repo_path, model: d.model, target: d.target_coverage,
               maxFixAttempts: d.options?.max_fix_attempts, startedAt: ev.ts, activity: "Preparing a working copy…" };
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
                                            status: "writing", testPlan: [], steps: [], tests: [] })),
        })),
        activity: d.items.length ? `Writing tests for ${d.items[0].file}…` : s.activity,
      };
    case "llm_call": {
      const next = { ...s, tokens: d.total_tokens };
      if (d.role === "writer") return withItem(next, d.index, d.file, (i) => ({ ...i, writerTokens: d.completion_tokens }));
      if (d.role !== "fixer") return next;
      return withItem(next, d.index, d.file, (i) => {
        const prev = last(i.steps);
        if (prev?.source.type !== "llm_fix" || prev.code != null) return i;
        const source = { ...prev.source, outputTokens: d.completion_tokens };
        return { ...i, steps: withLast(i.steps, (st) => ({ ...st, source })) };
      });
    }
    case "rate_limited":
      return { ...s, activity: `Waiting ${Math.round(d.seconds)}s for the Groq rate limit (${d.reason === "tpm" ? "tokens per minute" : "HTTP 429"})…` };
    case "candidate_generated":
      return { ...withItem(s, d.index, d.file, (i) => ({ ...addCode(i, d.code ?? ""), status: "validating",
                                                          testPlan: d.test_plan ?? i.testPlan, code: d.code })),
               activity: `Compiling and running tests for ${d.file}…` };
    case "validation_result":
      return withItem(s, d.index, d.file, (i) =>
        addCheck(i, { kind: d.kind, output: d.output ?? "", failedTests: d.failed_tests ?? [] }));
    case "mechanical_repair":
      return withItem(s, d.index, d.file, (i) => ({
        ...i, steps: [...i.steps, { source: { type: "auto_fix", description: d.description ?? "" } }] }));
    case "tests_pruned":
      return withItem(s, d.index, d.file, (i) => {
        const tests: string[] = d.tests ?? [];
        const before = last(i.steps)?.testCount;
        const kept = before != null && before > tests.length ? before - tests.length : undefined;
        return { ...i, steps: [...i.steps, { source: { type: "prune", tests, kept }, testCount: kept }] };
      });
    case "fix_attempt":
      return { ...withItem(s, d.index, d.file, (i) => ({
                 ...i, status: "fixing",
                 steps: [...i.steps, { source: { type: "llm_fix", attempt: d.attempt, max: s.maxFixAttempts, given: d.kind,
                                                 givenStep: last(i.steps)?.check ? i.steps.length : undefined } }] })),
               activity: `Fixing ${String(d.kind).replace("_", " ")} in ${d.file} (attempt ${d.attempt})…` };
    case "candidate_accepted": {
      const next = withItem(s, d.index, d.file, (i) => ({
        ...i, status: "accepted", tests: d.tests ?? [], gain: d.gain, percentAfter: d.percent,
        percentBefore: d.percent != null && d.gain != null ? d.percent - d.gain : undefined }));
      return { ...next, percent: d.percent, activity: nextWriting(next, d.index) };
    }
    case "candidate_rejected": {
      const next = withItem(s, d.index, d.file, (i) => ({ ...i, status: "rejected", rejectReason: d.reason }));
      return { ...next, activity: nextWriting(next, d.index) };
    }
    case "iteration_completed":
      return { ...withIteration(s, d.index, (it) => ({ ...it, endPercent: d.end_percent })),
               history: [...s.history, { label: `Iter ${d.index}`, percent: d.end_percent }] };
    case "job_completed":
    case "job_cancelled":
      return { ...s, status: ev.type === "job_completed" ? "completed" : "cancelled", summary: d as Summary,
               percent: d.final_percent, activity: d.message };
    case "job_failed":
      // cancelled before the baseline finished: there is no Summary, so the backend reports it as a failure reason
      if (d.reason === "cancelled") return { ...s, status: "cancelled", activity: "Cancelled." };
      return { ...s, status: "failed", failure: { reason: d.reason, message: d.message, output: d.output },
               activity: d.message };
    default:
      return s;
  }
}
