// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
"use client";
import { useState } from "react";
import { duration, pct, STOP_REASON_LABEL, tokenBreakdown, tokens } from "@/lib/format";
import type { Summary } from "@/lib/types";
import { Button, Card, SectionHeading } from "./ui";

/** `summaryTokens`: the AI summary calls' tokens, added to the run's own and broken out (as in the page header). */
export function SummaryCard({ summary, jobId, summaryTokens = 0, summaryCalls = 1 }:
  { summary: Summary; jobId: string; summaryTokens?: number; summaryCalls?: number }) {
  const run = summary.tokens.prompt_tokens + summary.tokens.completion_tokens;
  const breakdown = tokenBreakdown(run, summaryTokens, summaryCalls);
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
  const stats: [string, string, string?][] = [
    ["Coverage", `${pct(summary.baseline_percent)} → ${pct(summary.final_percent)}`],
    ["Tests added", String(summary.tests_added.length)],
    ["Test files", String(summary.test_files.length)],
    ["Duration", duration(summary.duration_s)],
    ["Tokens", tokens(run + summaryTokens), breakdown],
  ];
  return (
    <Card as="section">
      <SectionHeading>{STOP_REASON_LABEL[summary.stop_reason] ?? summary.stop_reason}</SectionHeading>
      <p className="mt-1 text-sm text-muted">{summary.message}</p>
      <dl className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-5">
        {stats.map(([k, v, note]) => (
          <div key={k}>
            <dt className="text-xs text-muted">{k}</dt>
            <dd className="font-mono text-sm tabular-nums">
              {v}
              {note && <span className="block text-xs text-muted">{note}</span>}
            </dd>
          </div>
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
