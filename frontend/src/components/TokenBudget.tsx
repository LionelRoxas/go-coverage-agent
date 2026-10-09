// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
"use client";
import { useId, useState } from "react";
import { tokens } from "@/lib/format";

/** Fallback for min_daily_tokens_to_start (backend/app/config.py), used only when /api/health does not report it. */
export const MIN_TOKENS_TO_START = 20_000;
/** Below this, a run can start but a long one may hit the daily cap and stop early. */
export const LOW_TOKENS = 200_000;

export const budgetBlocked = (left: number, min = MIN_TOKENS_TO_START) => left < min;

/** One line beside the Start button. `id` goes on the message so Start can point to it when blocked. */
export function TokenBudget({ left, min = MIN_TOKENS_TO_START, id }: { left: number; min?: number; id?: string }) {
  const [open, setOpen] = useState(false);
  const detailsId = useId();
  const blocked = budgetBlocked(left, min);
  const low = !blocked && left < LOW_TOKENS;
  const n = <span className="font-mono">{tokens(left)}</span>;

  return (
    <div className="min-w-0 max-w-sm text-xs leading-relaxed">
      <div className="flex items-start gap-1">
        <span id={id} className={blocked ? "font-medium text-danger" : low ? "text-warn" : "text-muted"}>
          {blocked ? (
            <>Only {n} tokens left today. A run needs at least <span className="font-mono">{tokens(min)}</span>; the budget resets at midnight UTC.</>
          ) : low ? (
            <>Running low: about {n} tokens left today. A long run may stop early.</>
          ) : (
            <>About {n} tokens left today</>
          )}
        </span>
        <button type="button" aria-label="About the token budget" aria-expanded={open} aria-controls={detailsId}
                onClick={() => setOpen((o) => !o)}
                className="-my-0.5 shrink-0 rounded-full p-0.5 text-muted hover:text-text aria-expanded:text-text">
          <svg aria-hidden viewBox="0 0 16 16" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round">
            <circle cx="8" cy="8" r="6.3" />
            <path d="M8 7.2v4" />
            <circle cx="8" cy="4.9" r="0.5" fill="currentColor" stroke="none" />
          </svg>
        </button>
      </div>
      <p id={detailsId} hidden={!open} className="mt-1 text-muted">
        Set by <code className="font-mono">DAILY_TOKEN_BUDGET</code> in <code className="font-mono">.env</code> and reset at midnight UTC.
        This is the app&apos;s own cap, not a Groq limit.
      </p>
    </div>
  );
}
