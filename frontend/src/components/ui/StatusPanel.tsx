// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
import type { ReactNode } from "react";
import { cx } from "./classes";
import { pageTitleClass } from "./Heading";

/**
 * A whole-page state: page not found, a crash, a run that can't be loaded. The page-title scale with a rule on
 * the left (red for errors), what happened in a sentence or two, then what to do next.
 */
export function StatusPanel({ title, children, actions, tone = "neutral", role }: {
  title: ReactNode; children?: ReactNode; actions?: ReactNode; tone?: "neutral" | "danger"; role?: "alert";
}) {
  return (
    <section role={role} data-tone={tone}
             className={cx("max-w-2xl space-y-4 border-l-2 pl-5 sm:pl-6", tone === "danger" ? "border-danger" : "border-accent")}>
      <h1 className={pageTitleClass}>{title}</h1>
      {children && <div className="space-y-2 text-base leading-relaxed text-muted sm:text-lg">{children}</div>}
      {actions && <div className="flex flex-wrap items-center gap-x-5 gap-y-3 pt-2">{actions}</div>}
    </section>
  );
}
