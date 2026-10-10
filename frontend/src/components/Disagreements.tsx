// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
import { DISAGREEMENT_NOTE, DISAGREEMENT_OUTCOME, disagreementHow, observedLine } from "@/lib/format";
import type { Disagreement } from "@/lib/types";
import { SectionHeading } from "./ui";

/** New tests that failed because the model's prediction and the code disagree. Nothing when there are none. */
export function Disagreements({ items }: { items: Disagreement[] }) {
  if (items.length === 0) return null;
  return (
    <section className="space-y-2" aria-labelledby="disagreements-heading">
      <SectionHeading id="disagreements-heading">Prediction disagreements ({items.length})</SectionHeading>
      <p className="max-w-[42rem] text-sm text-muted">{DISAGREEMENT_NOTE}</p>
      <ul className="list-disc space-y-1 pl-5 text-sm">
        {items.map((d, i) => {
          const outcome = d.outcome ? DISAGREEMENT_OUTCOME[d.outcome] : undefined;
          return (
            <li key={i} className="min-w-0">
              <span className="break-all font-mono">{d.test}</span>
              <span className="text-muted"> · {d.file}: {d.functions.join(", ")}</span>
              {d.lines.length > 0 ? (
                d.lines.map((line, k) => (
                  <span key={k} className="block break-words font-mono text-xs text-muted">{observedLine(d.test, line)}</span>
                ))
              ) : (
                <span className="block text-xs text-muted">No assertion lines in the output.</span>
              )}
              <span className="block text-xs text-muted">{disagreementHow(d.pruned)}{outcome && `; ${outcome}`}.</span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
