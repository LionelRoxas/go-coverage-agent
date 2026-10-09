// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
import type { ReactNode } from "react";

type Props = {
  n: number;
  title: ReactNode;
  hint: ReactNode;
  /** Fills the number marker once the step's input is valid. */
  done?: boolean;
  optional?: boolean;
  last?: boolean;
  id: string;
  children: ReactNode;
};

/** One numbered step of the New run form: a marker on a rail, an h2, a one-line hint, then the controls. */
export function Step({ n, title, hint, done = false, optional = false, last = false, id, children }: Props) {
  const marker = done
    ? "border-accent bg-accent text-on-accent"
    : optional
      ? "border-dashed border-border text-muted"
      : "border-accent text-accent";
  return (
    <li data-done={done} className="flex gap-3 sm:gap-4">
      <div aria-hidden className="flex w-6 shrink-0 flex-col items-center">
        <span className={`flex h-6 w-6 items-center justify-center rounded-full border-2 font-mono text-xs font-semibold tabular-nums transition-colors ${marker}`}>
          {n}
        </span>
        {!last && <span className="mt-1 w-px flex-1 bg-border" />}
      </div>
      <div className={`min-w-0 flex-1 space-y-3 ${last ? "" : "pb-8"}`}>
        <div className="space-y-1">
          <h2 id={id} className="text-base font-semibold leading-6">{title}</h2>
          <p className="max-w-prose text-sm leading-relaxed text-muted">{hint}</p>
        </div>
        {children}
      </div>
    </li>
  );
}
