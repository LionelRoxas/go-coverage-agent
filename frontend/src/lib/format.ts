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
};

// Why a single validation attempt did not pass (or was repaired without the model).
export const ATTEMPT_LABEL: Record<string, string> = {
  compile_error: "Didn't compile",
  vet_error: "go vet failed",
  test_failure: "Tests failed",
  no_gain: "No new coverage",
  guard_rejected: "Blocked by safety rules",
  llm_error: "Model error",
  mechanical_repair: "Auto-fixed (no LLM call)",
};

// Why a candidate was finally rejected.
export const REJECTION_LABEL: Record<string, string> = {
  compile_error: "Didn't compile",
  vet_error: "go vet failed",
  test_failure: "Tests failed",
  no_gain: "No new coverage",
  guard_rejected: "Blocked by safety rules",
  llm_error: "Model error",
  too_large: "Too large for one request",
};
