// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
"use client";
import { useState } from "react";
import { duration, pct, STOP_REASON_LABEL, tokens } from "@/lib/format";
import type { Summary } from "@/lib/types";
import { Button, Card, SectionHeading } from "./ui";

export function SummaryCard({ summary, jobId }: { summary: Summary; jobId: string }) {
  const outPath = `./output/${jobId}/tests`;
  const [copied, setCopied] = useState<"idle" | "done" | "failed">("idle");
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(outPath);
      setCopied("done");
    } catch {
      setCopied("failed");
    }
  };
  const stats: [string, string][] = [
    ["Coverage", `${pct(summary.baseline_percent)} → ${pct(summary.final_percent)}`],
    ["Tests added", String(summary.tests_added.length)],
    ["Test files", String(summary.test_files.length)],
    ["Duration", duration(summary.duration_s)],
    ["Tokens", tokens(summary.tokens.prompt_tokens + summary.tokens.completion_tokens)],
  ];
  return (
    <Card as="section">
      <SectionHeading>{STOP_REASON_LABEL[summary.stop_reason] ?? summary.stop_reason}</SectionHeading>
      <p className="mt-1 text-sm text-muted">{summary.message}</p>
      <dl className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-5">
        {stats.map(([k, v]) => (
          <div key={k}><dt className="text-xs text-muted">{k}</dt><dd className="font-mono text-sm tabular-nums">{v}</dd></div>
        ))}
      </dl>
      <div className="mt-4 flex flex-wrap items-center gap-2 text-sm">
        <span className="text-muted">Generated tests saved to</span>
        <code className="break-all font-mono">{outPath}</code>
        <Button size="sm" onClick={copy}>
          {copied === "done" ? "Copied" : copied === "failed" ? "Copy failed" : "Copy"}
        </Button>
      </div>
    </Card>
  );
}
