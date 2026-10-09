// AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
import { pct } from "@/lib/format";

export function CoverageMeter({ percent, target, baseline }: { percent: number; target: number; baseline?: number }) {
  return (
    <div className="space-y-2" role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(percent * 10) / 10}
         aria-label={`Coverage ${pct(percent)}, target ${pct(target)}`}>
      <div className="flex flex-wrap items-baseline justify-between gap-x-4">
        <span className="font-mono text-4xl font-semibold tabular-nums">{pct(percent)}</span>
        <span className="text-sm text-muted">target {pct(target)}{baseline != null && ` · baseline ${pct(baseline)}`}</span>
      </div>
      <div className="relative h-2 rounded-full bg-border">
        <div className="h-2 rounded-full bg-accent transition-[width] duration-500" style={{ width: `${Math.min(percent, 100)}%` }} />
        <div className="absolute -top-1 h-4 w-0.5 bg-text" style={{ left: `${Math.min(target, 100)}%` }} title="Target" />
      </div>
    </div>
  );
}
