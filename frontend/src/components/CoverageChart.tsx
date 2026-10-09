// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
"use client";
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export function CoverageChart({ history, target }: { history: { label: string; percent: number }[]; target: number }) {
  if (history.length < 2) return null;
  return (
    <div className="h-56 w-full" role="img" aria-label="Coverage after each iteration">
      <ResponsiveContainer>
        <LineChart data={history} margin={{ top: 8, right: 16, bottom: 0, left: -16 }}>
          <CartesianGrid stroke="var(--border)" vertical={false} />
          <XAxis dataKey="label" stroke="var(--muted)" fontSize={12} />
          <YAxis domain={[0, 100]} stroke="var(--muted)" fontSize={12} unit="%" />
          <Tooltip formatter={(v) => `${Number(v).toFixed(1)}%`}
                   contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", color: "var(--text)" }} />
          <ReferenceLine y={target} stroke="var(--text)" strokeDasharray="4 4" label={{ value: "target", fill: "var(--muted)", fontSize: 11 }} />
          <Line type="monotone" dataKey="percent" stroke="var(--accent)" strokeWidth={2} dot={{ r: 3 }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
