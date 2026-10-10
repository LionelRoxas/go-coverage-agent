// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
import { delta, pct } from "@/lib/format";
import type { Summary } from "@/lib/types";

export function FileTable({ rows }: { rows: Summary["per_file"] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="text-left text-xs text-muted">
          <tr><th className="py-2 pr-4 font-medium">File</th><th className="pr-4 font-medium">Before</th><th className="pr-4 font-medium">After</th><th className="font-medium">Change</th></tr>
        </thead>
        <tbody className="font-mono tabular-nums">
          {rows.map((r) => (
            <tr key={r.file} className="border-t border-border">
              <td className="py-1.5 pr-4">{r.file}</td><td className="pr-4">{pct(r.before)}</td><td className="pr-4">{pct(r.after)}</td>
              <td className={r.after > r.before ? "text-accent" : "text-muted"}>{delta(r.after - r.before)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
