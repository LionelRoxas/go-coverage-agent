// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
"use client";
import { useEffect, useState } from "react";
import { duration } from "@/lib/format";
import type { PendingRequest } from "@/lib/runState";

// "Waiting for Groq · fixer · medium reasoning · 1m 42s" (detailed) or "Waiting for Groq · 1m 42s".
export function waitLabel(p: PendingRequest, seconds: number, detailed: boolean): string {
  const who = detailed ? [p.role, p.effort && `${p.effort} reasoning`] : [];
  return ["Waiting for Groq", ...who, duration(Math.max(0, seconds))].filter(Boolean).join(" · ");
}

// Several requests at once (PARALLEL_WRITERS): "Waiting for Groq · 3 requests · writer · medium · 8s", timed from
// the oldest; the role and effort are named only when every request shares them.
export function waitManyLabel(ps: PendingRequest[], seconds: number): string {
  const shared = (key: "role" | "effort") => (ps.every((p) => p[key] === ps[0][key]) ? ps[0][key] : undefined);
  return ["Waiting for Groq", `${ps.length} requests`, shared("role"), shared("effort"), duration(Math.max(0, seconds))]
    .filter(Boolean).join(" · ");
}

// Ticks every second while mounted, i.e. only while the request is pending. The ticking text is hidden from
// screen readers (it would be announced every second); they get the same label without the time.
// `others`: further requests waiting at the same time; `pending` is the oldest.
export function GroqWait({ pending, detailed = false, others = [] }:
  { pending: PendingRequest; detailed?: boolean; others?: PendingRequest[] }) {
  const [now, setNow] = useState(() => Date.now() / 1000);
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now() / 1000), 1000);
    return () => clearInterval(t);
  }, []);
  const label = others.length ? waitManyLabel([pending, ...others], now - pending.since)
    : waitLabel(pending, now - pending.since, detailed);
  return (
    <>
      <span aria-hidden="true">{label}</span>
      <span className="sr-only">{label.slice(0, label.lastIndexOf(" · "))}</span>
    </>
  );
}
