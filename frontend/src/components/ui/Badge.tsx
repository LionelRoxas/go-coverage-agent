// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
import type { HTMLAttributes } from "react";
import type { JobSnapshot } from "@/lib/types";
import { cx } from "./classes";

export type BadgeTone = "solid" | "accent" | "neutral" | "danger" | "warn";
const TONE: Record<BadgeTone, string> = {
  solid: "border-accent bg-accent text-on-accent",
  accent: "border-accent text-accent",
  neutral: "border-border-strong text-muted",
  danger: "border-danger text-danger",
  warn: "border-warn text-warn",
};

type BadgeProps = HTMLAttributes<HTMLSpanElement> & {
  tone?: BadgeTone;
  /** Monospace at normal weight, for values such as a model name; otherwise sans at medium weight. */
  mono?: boolean;
};

export function Badge({ tone = "neutral", mono = false, className, ...rest }: BadgeProps) {
  return (
    <span className={cx("inline-flex shrink-0 items-center rounded-full border px-2 py-0.5 text-xs leading-4",
                        mono ? "font-mono font-normal" : "font-medium", TONE[tone], className)} {...rest} />
  );
}

const STATUS: Record<JobSnapshot["status"], { label: string; tone: BadgeTone }> = {
  running: { label: "Running", tone: "solid" },
  completed: { label: "Completed", tone: "accent" },
  cancelled: { label: "Cancelled", tone: "neutral" },
  failed: { label: "Failed", tone: "danger" },
};

/** A run's status, drawn the same in Run history and on the run page. */
export function StatusChip({ status }: { status: JobSnapshot["status"] }) {
  const s = STATUS[status];
  return <Badge tone={s.tone}>{s.label}</Badge>;
}
