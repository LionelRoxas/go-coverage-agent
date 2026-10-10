// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
import { cx } from "@/components/ui";

/** "visited": opened before and reachable again, but not finished (the review step). */
export type StepState = "done" | "current" | "visited" | "upcoming";

type Props = {
  label: string;
  steps: readonly string[];
  /** Index of the step on screen. */
  current: number;
  /** State of each step, in order. Only "done" and "visited" steps can be clicked. */
  states: readonly StepState[];
  onJump: (index: number) => void;
};

function Check() {
  return (
    <svg aria-hidden viewBox="0 0 12 12" className="h-3 w-3 shrink-0" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2.5 6.2 5 8.6l4.5-5" />
    </svg>
  );
}

/**
 * The wizard's progress: a segmented track with one labelled segment per step. Done steps are buttons that jump
 * back; upcoming ones are plain text. Below sm it collapses to one line and a thin progress bar.
 */
export function WizardStepper({ label, steps, current, states, onJump }: Props) {
  const total = steps.length;
  return (
    <nav aria-label={label}>
      <div className="space-y-2 sm:hidden">
        <p aria-current="step" className="text-sm">
          <span className="font-medium">Step {current + 1} of {total}</span>
          <span className="text-muted"> · {steps[current]}</span>
        </p>
        <div aria-hidden className="h-1 overflow-hidden rounded-full bg-border">
          <div className="h-full rounded-full bg-accent transition-[width] duration-300 motion-reduce:transition-none"
               style={{ width: `${((current + 1) / total) * 100}%` }} />
        </div>
      </div>
      <ol className="hidden grid-cols-4 gap-2 sm:grid">
        {steps.map((title, i) => {
          const state = states[i];
          const clickable = state === "done" || state === "visited";
          const body = (
            <>
              <span aria-hidden className={cx("block h-1 rounded-full transition-colors",
                state === "upcoming" ? "bg-border" : "bg-accent")} />
              <span className={cx("flex items-start gap-1.5 pt-2 text-left text-xs leading-snug",
                state === "current" ? "font-semibold text-text" : clickable ? "text-text" : "text-muted")}>
                {state === "done" ? (
                  <span className="mt-px text-accent"><Check /></span>
                ) : (
                  <span aria-hidden className="w-3 shrink-0 font-mono tabular-nums">{i + 1}</span>
                )}
                <span>
                  {title}
                  {state === "done" && <span className="sr-only">, done</span>}
                </span>
              </span>
            </>
          );
          return (
            <li key={title} data-state={state} aria-current={state === "current" ? "step" : undefined} className="min-w-0">
              {clickable ? (
                <button type="button" onClick={() => onJump(i)}
                        className="block w-full rounded-sm pb-0.5 hover:[&>span:last-child]:text-accent">
                  {body}
                </button>
              ) : (
                <div className="pb-0.5">{body}</div>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
