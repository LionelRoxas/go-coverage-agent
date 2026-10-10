// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
import type { StopReason } from "./types";

export const pct = (n?: number | null) => (n == null ? "—" : `${n.toFixed(1)}%`);
export const delta = (n: number) => `${n >= 0 ? "+" : "−"}${Math.abs(n).toFixed(1)} pp`;
export const duration = (s: number) =>
  s < 60 ? `${Math.floor(s)}s` : `${Math.floor(s / 60)}m ${Math.floor(s % 60)}s`;
export const tokens = (n: number) =>
  n >= 1_000_000 ? `${(n / 1_000_000).toFixed(1)}M` : n >= 1000 ? `${(n / 1000).toFixed(1)}k` : `${n}`;

export const STOP_REASON_LABEL: Record<StopReason, string> = {
  target_reached: "Target reached",
  marginal_gains: "Diminishing returns",
  max_iterations: "Iteration limit reached",
  no_remaining_targets: "Nothing left to try",
  budget_exhausted: "Token budget used up",
  cancelled: "Cancelled",
  llm_unavailable: "Groq unreachable",
};

// An item that met a Groq outage (candidate_deferred): neither accepted nor rejected.
export const DEFERRED_LABEL = "Retried later (Groq unreachable)";

// Why a single validation attempt did not pass (or was repaired without the model).
export const ATTEMPT_LABEL: Record<string, string> = {
  compile_error: "Didn't compile",
  vet_error: "go vet failed",
  test_failure: "Tests failed",
  no_gain: "No new coverage",
  guard_rejected: "Blocked by safety rules",
  no_assertions: "Tests without assertions",
  llm_error: "Model error",
  llm_timeout: "Groq timed out",
  llm_unavailable: "Groq unreachable",
  prompt_too_large: "Prompt too large (no model call)",
  mechanical_repair: "Auto-fixed (no LLM call)",
};

// Why a candidate was finally rejected.
export const REJECTION_LABEL: Record<string, string> = {
  compile_error: "Didn't compile",
  vet_error: "go vet failed",
  test_failure: "Tests failed",
  no_gain: "No new coverage",
  guard_rejected: "Blocked by safety rules",
  no_assertions: "Tests without assertions",
  llm_error: "Model error",
  llm_timeout: "Groq timed out",
  llm_unavailable: "Groq unreachable",
  prompt_too_large: "Prompt too large (no model call)",
  too_large: "Too large for one request",
};

// One-line verdict for a check of one attempt (validation_result kind). test_failure is counted by checkLabel.
export const CHECK_LABEL: Record<string, string> = {
  accepted: "Passed: compiles, go vet clean, every test asserts, tests pass twice, adds new coverage",
  compile_error: "Didn't compile",
  vet_error: "go vet failed",
  no_gain: "No new coverage",
  guard_rejected: "Rejected by the safety guard",
  no_assertions: "Tests without assertions (no t.Error or t.Fatal)",
  llm_error: "Model error",
  llm_timeout: "Groq timed out",
  llm_unavailable: "Groq unreachable",
  prompt_too_large: "Prompt too large (no model call)",
};

export function checkLabel(kind: string, failed: number, total?: number): string {
  if (kind !== "test_failure") return CHECK_LABEL[kind] ?? kind;
  if (failed <= 0) return "Tests failed"; // e.g. a panic or timeout: no per-test FAIL lines to count
  if (total != null && total >= failed) return `${failed} of ${total} tests failed`;
  return failed === 1 ? "1 test failed" : `${failed} tests failed`;
}

// What the LLM fixer was handed, by the kind of the check it is fixing.
export const FIX_GIVEN: Record<string, string> = {
  compile_error: "the compile error",
  vet_error: "the go vet error",
  test_failure: "the failing tests",
  no_gain: "the no-new-coverage result",
  guard_rejected: "the safety guard's rejection",
  no_assertions: "the tests without assertions",
};

// ① … ⑳ for step numbers; plain digits after that.
export const circled = (n: number) => (n >= 1 && n <= 20 ? String.fromCodePoint(0x2460 + n - 1) : `(${n})`);

export const count = (n: number) => n.toLocaleString("en-US");

export type TestFailure = { name: string; message?: string };

// Unique top-level failing tests from `go test` output, each with its first message line.
// -count=2 prints every failure twice; the first occurrence wins.
export function parseTestFailures(output: string): TestFailure[] {
  const seen = new Map<string, TestFailure>();
  let current: TestFailure | null = null;
  for (const line of output.split("\n")) {
    const top = /^--- FAIL: (\S+)/.exec(line);
    if (top) {
      current = seen.has(top[1]) ? null : { name: top[1] };
      if (current) seen.set(current.name, current);
      continue;
    }
    const text = line.trim();
    if (!current || current.message || !text) continue;
    if (!/^\s/.test(line)) { current = null; continue; } // FAIL, coverage:, ok … end the block
    if (/^(--- (FAIL|PASS|SKIP)|=== )/.test(text)) continue;
    current.message = text;
  }
  return [...seen.values()];
}
