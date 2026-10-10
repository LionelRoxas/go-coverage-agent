// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
// Mirrors backend/app/models.py and the event payload contract in the implementation plan.

export type FuncKey = { file: string; receiver: string; name: string };
export type FileCoverage = { file: string; statements: number; covered: number; percent: number };
export type FuncCoverage = { key: FuncKey; statements: number; covered: number; uncovered_lines: [number, number][] };
export type CoverageReport = {
  total_statements: number;
  covered_statements: number;
  percent: number;
  files: FileCoverage[];
  functions: FuncCoverage[];
};

export type Scenario = { scenario: string; target: string };
export type SuspectedBug = { function: string; description: string };

export type StopReason =
  | "target_reached"
  | "marginal_gains"
  | "max_iterations"
  | "no_remaining_targets"
  | "budget_exhausted"
  | "cancelled";

export type Summary = {
  stop_reason: StopReason;
  message: string;
  target: number;
  baseline_percent: number;
  final_percent: number;
  iterations: { index: number; start_percent: number; end_percent: number; accepted: number; rejected: number }[];
  test_files: string[];
  tests_added: string[];
  suspected_bugs: SuspectedBug[];
  per_file: { file: string; before: number; after: number }[];
  tokens: { prompt_tokens: number; completion_tokens: number };
  duration_s: number;
};

export type JobOptions = {
  max_iterations: number; // backend default: 20
  min_gain: number;
  patience: number;
  targets_per_iteration: number;
  max_fix_attempts: number;
  delete_existing_tests: boolean;
  max_llm_tokens: number;
  exclude_patterns: string[];
  write_summary: boolean; // backend default: true
};

/** The end-of-run AI summary (summary_generated), written from the run's measured facts. */
export type BusinessSummary = { headline: string; outcome: string; efficiency: string; risks: string[]; recommendation: string };
export type TechnicalSummary = {
  headline: string;
  what_was_tested: string;
  where_tests_live: string;
  gaps: { file: string; detail: string }[];
  suspected_bugs: string[];
  rejected_or_failed: string;
  how_to_run: string;
  next_steps: string[];
};
/** run: the run itself (what the text talks about); summary: the summary call; input/output/total: both together. */
export type CostUsd = { run: number; summary: number; input: number; output: number; total: number };
export type SummaryGenerated = {
  business: BusinessSummary;
  technical: TechnicalSummary;
  dropped_sentences: number;
  tokens: { prompt_tokens: number; completion_tokens: number; total_tokens: number };
  /** Only when GROQ_PRICE_*_PER_M are set. */
  cost_usd?: CostUsd;
};

export type StartJobBody = { repo_path: string; target_coverage: number; options?: Partial<JobOptions> };

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type JobEvent = { seq: number; ts: number; type: string; data: Record<string, any> };

/** read_only: a module in HOST_REPOS_DIR (path `host/<rel>`), mounted read-only; absent on older backends. */
export type RepoInfo = { path: string; module: string; go_files: number; test_files: number; read_only?: boolean };

export type SkipReason = "git" | "vendor" | "node_modules" | "hidden" | "too_large" | "binary";
export type SkipCounts = Record<SkipReason, number>;
/** POST /api/repos/upload: the saved module plus the files the backend skipped, by reason. */
export type UploadResult = RepoInfo & { skipped: SkipCounts };
export type UploadLimits = { max_files: number; max_bytes: number; max_file_bytes: number };

export type Sample = {
  id: string;
  name: string;
  description: string;
  license: string;
  ref: string | null;
  path: string;
  downloaded: boolean;
};

export type Health = {
  status: string;
  go_version: string;
  model: string;
  llm_configured: boolean;
  tokens_left_today: number;
  /** Below this many tokens left today the backend refuses a new job. Older backends omit it. */
  min_daily_tokens_to_start?: number;
  storage_writable: boolean;
  host_repos_dir?: string | null;
  /** Folder upload limits (UPLOAD_MAX_*). Older backends omit it. */
  upload_limits?: UploadLimits;
};

export type JobSnapshot = {
  id: string;
  /** "interrupted": a run reloaded from ./output that never finished (the app stopped mid-run). */
  status: "running" | "completed" | "failed" | "cancelled" | "interrupted";
  request: { repo_path: string; target_coverage: number; options: JobOptions };
  created_at: number;
  percent: number | null;
  event_count: number;
  summary: Summary | null;
  /** The run has ended and its AI summary is being written; the job still counts as busy. Older backends omit it. */
  writing_summary?: boolean;
  /** The last AI summary event: "generated" or "failed"; null when none. Older backends omit it. */
  ai_summary?: "generated" | "failed" | null;
};
