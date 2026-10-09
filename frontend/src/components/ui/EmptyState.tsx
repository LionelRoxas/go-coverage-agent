// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
import type { ReactNode } from "react";
import { cx } from "./classes";

/** "Nothing here yet" and "not available" messages: a dashed box with one muted sentence. */
export function EmptyState({ role, className, children }: { role?: "status"; className?: string; children: ReactNode }) {
  return (
    <p role={role} className={cx("rounded-md border border-dashed border-border-strong px-3 py-4 text-sm text-muted", className)}>
      {children}
    </p>
  );
}
