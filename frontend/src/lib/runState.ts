// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
// Pure reducer: the same code handles live events and replay after a refresh or reconnect.
import type { CoverageReport, JobEvent, Scenario, Summary, SummaryGenerated } from "./types";

// "not_run": the run ended (goal reached, stopped or cancelled) before this planned item finished.
export type ItemStatus = "writing" | "validating" | "fixing" | "accepted" | "rejected" | "not_run";

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

// A request sent to Groq that has not answered yet (llm_request until its llm_call or validation_result).
export type PendingRequest = { since: number; role: string; effort?: string };

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
  notRunReason?: "goal" | "stopped";
  writerTokens?: number; // the writer's llm_call arrives just before its candidate_generated
  pending?: PendingRequest;
};
// The end-of-run AI summary. "waiting": expected or being written (pending once its Groq request is out);
// "off": write_summary was false; "none": an older run that predates the summary.
export type AiSummaryView = {
  status: "waiting" | "done" | "failed" | "off" | "none";
  pending?: PendingRequest;
  result?: SummaryGenerated;
  generatedAt?: number;
  error?: { reason: string; message: string };
};

export type IterationView = { index: number; startPercent: number; endPercent?: number; items: ItemView[] };
export type RunState = {
  lastSeq: number;
  // "interrupted": a saved run whose stream ended without a terminal event (the app stopped mid-run)
  status: "connecting" | "running" | "completed" | "failed" | "cancelled" | "interrupted";
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
  writeSummary?: boolean; // job_started options.write_summary; older logs lack it
  aiSummary?: AiSummaryView;
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

// No request is waiting any more: a rate-limit pause (its own activity line) or the end of the job.
// Items still writing/validating/fixing when the job ends never finish; mark them so the page stops showing "Writing…".
function settleUnfinished(s: RunState, reason: "goal" | "stopped"): RunState {
  const open = (i: ItemView) => i.status !== "accepted" && i.status !== "rejected" && i.status !== "not_run";
  if (!s.iterations.some((it) => it.items.some(open))) return s;
  return { ...s, iterations: s.iterations.map((it) => ({
    ...it, items: it.items.map((i) => (open(i) ? { ...i, status: "not_run" as const, notRunReason: reason, pending: undefined } : i)) })) };
}

function clearPending(s: RunState): RunState {
  if (!s.iterations.some((it) => it.items.some((i) => i.pending))) return s;
  return { ...s, iterations: s.iterations.map((it) => ({
    ...it, items: it.items.map((i) => (i.pending ? { ...i, pending: undefined } : i)) })) };
}

// The item whose Groq request is still waiting, if any (requests are made one at a time).
export function waitingOn(s: RunState): (PendingRequest & { file: string }) | undefined {
  for (const it of s.iterations) for (const i of it.items) {
    if (i.pending && i.status !== "accepted" && i.status !== "rejected") return { file: i.file, ...i.pending };
  }
  return undefined;
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

/** True while the event stream must stay open after the run ended: its summary is still to come. */
export const summaryWaiting = (s: RunState) => s.aiSummary?.status === "waiting";

// "summary_requested": Write summary / Write again was accepted; its events follow on a reopened stream.
// "stream_ended": the stream of a run that is not running (e.g. reloaded from ./output) replayed everything and ended.
export type RunAction = JobEvent | { type: "reset" } | { type: "summary_requested" } | { type: "stream_ended" };

// Nothing more will come: a run without its terminal event was interrupted, and a summary still "waiting" never came.
function streamEnded(s: RunState): RunState {
  if (s.status === "running")
    return { ...settleUnfinished(clearPending(s), "stopped"), status: "interrupted",
             activity: "The app stopped before this run finished." };
  if (s.aiSummary?.status === "waiting")
    return { ...s, aiSummary: { ...s.aiSummary, status: "failed", pending: undefined,
                                error: { reason: "interrupted", message: "The app stopped before the summary was written." } } };
  return s;
}

export function reduce(state: RunState, ev: RunAction): RunState {
  if (ev.type === "summary_requested")
    return { ...state, aiSummary: { ...state.aiSummary, status: "waiting", pending: undefined, error: undefined } };
  if (ev.type === "stream_ended") return streamEnded(state);
  if (!("seq" in ev)) return initialState; // "reset": a different job was opened
  if (ev.seq <= state.lastSeq) return state;
  const s: RunState = { ...state, lastSeq: ev.seq };
  const d = ev.data;
  switch (ev.type) {
    case "job_started":
      return { ...s, status: "running", repoPath: d.repo_path, model: d.model, target: d.target_coverage,
               maxFixAttempts: d.options?.max_fix_attempts, writeSummary: d.options?.write_summary, startedAt: ev.ts, activity: "Preparing a working copy…" };
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
    case "llm_request":
      if (d.role === "summarizer")
        return { ...s, aiSummary: { ...s.aiSummary, status: "waiting",
                                    pending: { since: ev.ts, role: d.role, effort: d.reasoning_effort ?? undefined } } };
      return withItem(s, d.index, d.file, (i) => ({
        ...i, pending: { since: ev.ts, role: d.role, effort: d.reasoning_effort ?? undefined } }));
    case "llm_call": {
      const next = withItem({ ...s, tokens: d.total_tokens }, d.index, d.file, (i) => ({ ...i, pending: undefined }));
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
      return { ...clearPending(s), aiSummary: s.aiSummary && { ...s.aiSummary, pending: undefined }, activity: `Waiting ${Math.round(d.seconds)}s for the Groq rate limit (${d.reason === "tpm" ? "tokens per minute" : "HTTP 429"})…` };
    case "candidate_generated":
      return { ...withItem(s, d.index, d.file, (i) => ({ ...addCode(i, d.code ?? ""), status: "validating",
                                                          testPlan: d.test_plan ?? i.testPlan, code: d.code })),
               activity: `Compiling and running tests for ${d.file}…` };
    case "validation_result":
      return withItem(s, d.index, d.file, (i) =>
        addCheck({ ...i, pending: undefined }, { kind: d.kind, output: d.output ?? "", failedTests: d.failed_tests ?? [] }));
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
        ...i, status: "accepted", pending: undefined, tests: d.tests ?? [], gain: d.gain, percentAfter: d.percent,
        percentBefore: d.percent != null && d.gain != null ? d.percent - d.gain : undefined }));
      return { ...next, percent: d.percent, activity: nextWriting(next, d.index) };
    }
    case "candidate_rejected": {
      const next = withItem(s, d.index, d.file, (i) => ({ ...i, status: "rejected", pending: undefined,
                                                         rejectReason: d.reason })); // e.g. too_large: no llm_call came
      return { ...next, activity: nextWriting(next, d.index) };
    }
    case "iteration_completed":
      return { ...withIteration(s, d.index, (it) => ({ ...it, endPercent: d.end_percent })),
               history: [...s.history, { label: `Iter ${d.index}`, percent: d.end_percent }] };
    case "job_completed":
    case "job_cancelled":
      return { ...settleUnfinished(clearPending(s), ev.type === "job_completed" && d.stop_reason === "target_reached" ? "goal" : "stopped"),
               status: ev.type === "job_completed" ? "completed" : "cancelled", summary: d as Summary,
               aiSummary: { status: s.writeSummary ? "waiting" : s.writeSummary === false ? "off" : "none" },
               percent: d.final_percent, activity: d.message };
    case "summary_generated":
      return { ...s, tokens: s.tokens + (d.tokens?.total_tokens ?? 0),
               aiSummary: { status: "done", result: d as SummaryGenerated, generatedAt: ev.ts } };
    case "summary_failed":
      return { ...s, aiSummary: { ...s.aiSummary, status: "failed", pending: undefined,
                                  error: { reason: d.reason, message: d.message } } };
    case "job_failed":
      // cancelled before the baseline finished: there is no Summary, so the backend reports it as a failure reason
      if (d.reason === "cancelled") return { ...settleUnfinished(clearPending(s), "stopped"), status: "cancelled", activity: "Cancelled." };
      return { ...settleUnfinished(clearPending(s), "stopped"), status: "failed", failure: { reason: d.reason, message: d.message, output: d.output },
               activity: d.message };
    default:
      return s;
  }
}
