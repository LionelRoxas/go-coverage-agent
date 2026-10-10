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

// Ticks every second while mounted, i.e. only while the request is pending. The ticking text is hidden from
// screen readers (it would be announced every second); they get the same label without the time.
export function GroqWait({ pending, detailed = false }: { pending: PendingRequest; detailed?: boolean }) {
  const [now, setNow] = useState(() => Date.now() / 1000);
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now() / 1000), 1000);
    return () => clearInterval(t);
  }, []);
  const label = waitLabel(pending, now - pending.since, detailed);
  return (
    <>
      <span aria-hidden="true">{label}</span>
      <span className="sr-only">{label.slice(0, label.lastIndexOf(" · "))}</span>
    </>
  );
}
