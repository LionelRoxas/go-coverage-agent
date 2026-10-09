// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
import { ATTEMPT_LABEL, delta, pct, REJECTION_LABEL } from "@/lib/format";
import type { ItemView, IterationView } from "@/lib/runState";

const STATUS_STYLE: Record<ItemView["status"], string> = {
  writing: "text-muted", validating: "text-muted", fixing: "text-warn", accepted: "text-accent", rejected: "text-danger",
};

function itemLabel(item: ItemView): string {
  switch (item.status) {
    case "accepted": return item.gain != null ? `Accepted ${delta(item.gain)}` : "Accepted";
    case "rejected": return REJECTION_LABEL[item.rejectReason ?? ""] ?? "Rejected";
    case "fixing": return "Fixing…";
    case "validating": return "Running…";
    default: return "Writing…";
  }
}

// An auto-fix is a success (repaired without the model), not a failure.
const attemptStyle = (kind: string) => (kind === "mechanical_repair" ? "text-accent" : "text-muted");

function Item({ item }: { item: ItemView }) {
  const empty = item.testPlan.length === 0 && item.attempts.length === 0 && item.tests.length === 0 && item.pruned.length === 0;
  return (
    <details className="rounded-md border border-border px-3 py-2">
      <summary className="flex cursor-pointer flex-wrap items-center justify-between gap-x-4 gap-y-1 text-sm">
        <span className="min-w-0 break-all font-mono">{item.file} <span className="text-muted">· {item.functions.join(", ")}</span></span>
        <span className={`shrink-0 ${STATUS_STYLE[item.status]}`}>{itemLabel(item)}</span>
      </summary>
      <div className="mt-3 space-y-3 text-sm">
        {item.testPlan.length > 0 && (
          <div>
            <h4 className="text-xs font-medium uppercase tracking-wide text-muted">What it decided to test</h4>
            <ul className="mt-1 list-disc pl-5">
              {item.testPlan.map((s, i) => <li key={i}><span className="font-mono text-xs">{s.target}</span> — {s.scenario}</li>)}
            </ul>
          </div>
        )}
        {item.attempts.map((a, i) => (
          <div key={i}>
            <h4 className={`text-xs font-medium uppercase tracking-wide ${attemptStyle(a.kind)}`}>
              Attempt {i + 1}: {ATTEMPT_LABEL[a.kind] ?? a.kind}
            </h4>
            {a.output && <pre className="mt-1 max-h-48 overflow-auto whitespace-pre-wrap break-words rounded bg-surface p-2 font-mono text-xs">{a.output}</pre>}
          </div>
        ))}
        {item.pruned.length > 0 && <p className="text-xs text-muted">Removed failing tests: {item.pruned.join(", ")}</p>}
        {item.tests.length > 0 && <p className="break-words text-xs">Kept: <span className="font-mono">{item.tests.join(", ")}</span></p>}
        {empty && <p className="text-xs text-muted">No details yet.</p>}
      </div>
    </details>
  );
}

export function Timeline({ iterations }: { iterations: IterationView[] }) {
  if (iterations.length === 0) return <p className="text-sm text-muted">Nothing yet.</p>;
  return (
    <ol className="space-y-6">
      {iterations.map((it) => (
        <li key={it.index}>
          <h3 className="mb-2 text-sm font-medium">
            Iteration {it.index}{" "}
            <span className="font-mono text-muted">{pct(it.startPercent)}{it.endPercent != null && ` → ${pct(it.endPercent)}`}</span>
          </h3>
          <div className="space-y-2">{it.items.map((item, i) => <Item key={`${item.file}-${i}`} item={item} />)}</div>
        </li>
      ))}
    </ol>
  );
}
