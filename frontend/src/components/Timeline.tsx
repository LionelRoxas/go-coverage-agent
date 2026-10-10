// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
"use client";
import { useId, useState } from "react";
import { GroqWait } from "@/components/GroqWait";
import {
  ATTEMPT_LABEL, checkLabel, circled, count, delta, FIX_GIVEN, parseTestFailures, pct, REJECTION_LABEL,
} from "@/lib/format";
import type { Check, ItemView, IterationView, Step } from "@/lib/runState";
import { Button, cardClass, codeBlockClass, EmptyState } from "./ui";

const SHOWN_FUNCTIONS = 3;
// Older logs recorded a fixer prompt that did not fit as llm_error with this message.
const TOO_LARGE_OUTPUT = /^targets need ~?\d+ tokens; budget is \d+/;

// A fix request that never produced code because its prompt did not fit the budget.
function fixTooLarge(step: Step): boolean {
  return step.source.type === "llm_fix" && step.code == null && step.check != null &&
    (step.check.kind === "prompt_too_large" || TOO_LARGE_OUTPUT.test(step.check.output));
}

const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;
const finished = (item: ItemView) => item.status === "accepted" || item.status === "rejected" || item.status === "not_run";

// The step whose check accepted the candidate (1-based).
function acceptedAt(item: ItemView): number {
  for (let i = item.steps.length - 1; i >= 0; i--) if (item.steps[i].check?.kind === "accepted") return i + 1;
  return item.steps.length;
}

function statusLabel(item: ItemView): string {
  switch (item.status) {
    case "accepted": {
      const at = item.steps.length ? `Accepted at attempt ${acceptedAt(item)}` : "Accepted";
      return item.gain != null ? `${at} · ${delta(item.gain)}` : at;
    }
    case "rejected":
      return item.steps.length ? `Rejected after attempt ${item.steps.length}`
                               : REJECTION_LABEL[item.rejectReason ?? ""] ?? "Rejected";
    case "not_run":
      if (item.steps.length) return "Stopped before it finished";
      return item.notRunReason === "goal" ? "Not needed: goal reached" : "Not started: the run stopped";
    default:
      return item.steps.length ? "Running…" : "Writing…";
  }
}

function oneLiner(steps: Step[]): string {
  let autoFixes = 0, llmFixes = 0, removed = 0;
  for (const { source: s } of steps) {
    if (s.type === "auto_fix") autoFixes++;
    else if (s.type === "llm_fix") llmFixes++;
    else if (s.type === "prune") removed += s.tests.length;
  }
  return [
    plural(steps.length, "attempt"),
    autoFixes && (autoFixes === 1 ? "auto-fix" : `${autoFixes} auto-fixes`),
    llmFixes && (llmFixes === 1 ? "LLM fix" : `${llmFixes} LLM fixes`),
    removed && `removed ${plural(removed, "test")}`,
  ].filter(Boolean).join(" · ");
}

function sourceLine(step: Step): string {
  const s = step.source;
  const tokens = "outputTokens" in s && s.outputTokens != null ? ` · ${count(s.outputTokens)} output tokens` : "";
  switch (s.type) {
    case "writer":
      return step.code == null && step.check ? "Writer request returned no code" : `Written by the LLM${tokens}`;
    case "auto_fix": // StepView shows the same text with the prefix in the accent colour
      return s.description ? `Auto-fixed, no LLM call: ${s.description}` : "Auto-fixed, no LLM call";
    case "prune": {
      const removed = s.tests.length === 1 ? "Removed the failing test" : `Removed the ${s.tests.length} failing tests`;
      return s.kept != null ? `${removed}, kept ${s.kept}` : removed;
    }
    case "llm_fix": {
      const which = `fix ${s.attempt}${s.max != null ? ` of ${s.max}` : ""}`;
      if (step.code == null && step.check) {
        return fixTooLarge(step) ? `Fix request too large — no model call (${which})` : `Fix request failed (${which})`;
      }
      const given = FIX_GIVEN[s.given] ?? `the ${String(s.given).replaceAll("_", " ")} result`;
      const from = s.givenStep != null ? ` from ${circled(s.givenStep)}` : "";
      return `Rewritten by the LLM fixer (${which}), given ${given}${from}${tokens}`;
    }
  }
}

const OUTPUT_PRE = `mt-1 max-h-48 whitespace-pre-wrap break-words ${codeBlockClass()}`;

function TestFailures({ output }: { output: string }) {
  const failures = parseTestFailures(output);
  return (
    <div className="mt-1 space-y-1">
      {failures.length > 0 && (
        <ul className="space-y-1">
          {failures.map((f) => (
            <li key={f.name} className="text-xs">
              <span className="break-all font-mono">{f.name}</span>
              {f.message && <span className="block break-words pl-3 text-muted">{f.message}</span>}
            </li>
          ))}
        </ul>
      )}
      <details>
        <summary className="cursor-pointer text-xs text-muted hover:text-text">Raw output</summary>
        <pre className={OUTPUT_PRE}>{output}</pre>
      </details>
    </div>
  );
}

function CheckView({ step, final }: { step: Step; final: boolean }) {
  const check = step.check as Check;
  if (step.code == null && step.source.type !== "prune") {
    // the request never produced code, so nothing was compiled or run
    return (
      <div className="text-xs text-muted">
        <p><span aria-hidden="true">✗ </span>{fixTooLarge(step) ? ATTEMPT_LABEL.prompt_too_large : ATTEMPT_LABEL[check.kind] ?? check.kind}: nothing to check</p>
        {check.output && <pre className={OUTPUT_PRE}>{check.output}</pre>}
      </div>
    );
  }
  const ok = check.kind === "accepted";
  const failed = check.kind === "test_failure" ? Math.max(check.failedTests.length, parseTestFailures(check.output).length) : 0;
  return (
    <div className="text-xs">
      <p className={ok ? "text-accent" : final ? "text-danger" : "text-muted"}>
        <span aria-hidden="true">{ok ? "✓ " : "✗ "}</span>
        {!ok && <span className="sr-only">Failed: </span>}
        {checkLabel(check.kind, failed, step.testCount)}
      </p>
      {check.kind === "test_failure" && check.output && <TestFailures output={check.output} />}
      {!ok && check.kind !== "test_failure" && check.output && <pre className={OUTPUT_PRE}>{check.output}</pre>}
    </div>
  );
}

function StepView({ step, n, item, next }: { step: Step; n: number; item: ItemView; next?: Step }) {
  const isLast = next == null;
  const [showCode, setShowCode] = useState(false);
  const codeId = useId();
  const winner = item.status === "accepted" && n === acceptedAt(item);
  return (
    <li className="relative pb-4 pl-8 before:absolute before:bottom-0 before:left-2.5 before:top-6 before:w-px before:bg-border last:pb-0 last:before:hidden">
      <span aria-hidden="true" className={`absolute left-0 top-0 w-5 text-center text-base leading-5 ${winner ? "text-accent" : "text-muted"}`}>
        {circled(n)}
      </span>
      <div className="flex min-w-0 flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <p className="min-w-0 break-words text-sm">
          {step.source.type === "auto_fix"
            ? <><span className="text-accent">Auto-fixed, no LLM call</span>{step.source.description && `: ${step.source.description}`}</>
            : sourceLine(step)}
        </p>
        {step.code != null && (
          <Button size="sm" onClick={() => setShowCode((v) => !v)} aria-expanded={showCode} aria-controls={codeId}>
            {showCode ? "Hide code" : "View code"}
          </Button>
        )}
      </div>
      {step.source.type === "prune" && <p className="text-xs text-muted">Same code minus the removed tests.</p>}
      {showCode && step.code != null && (
        <pre id={codeId} className={`mt-1 max-h-80 ${codeBlockClass()}`}>{step.code}</pre>
      )}
      <div className="mt-1">
        {step.check ? <CheckView step={step} final={item.status === "rejected" && isLast} />
          : isLast && !finished(item) ? (
            <p className="text-xs text-muted">
              {step.code == null && step.source.type !== "prune"
                ? item.pending ? <GroqWait pending={item.pending} detailed /> : "Fixing…"
                : "Checking…"}
            </p>
          ) : next?.source.type === "auto_fix" && ( // e.g. stray characters cleaned from import paths
            <p className="text-xs text-muted">Not checked: auto-fixed first.</p>
          )}
      </div>
    </li>
  );
}

function ResultLine({ item }: { item: ItemView }) {
  if (item.status === "accepted") {
    const overall = item.percentBefore != null && item.percentAfter != null
      ? ` (overall ${pct(item.percentBefore)} → ${pct(item.percentAfter)})` : "";
    return (
      <div className="space-y-1 border-t border-border pt-2 text-sm">
        <p>
          <span className="font-medium text-accent">Result: accepted</span>
          {item.steps.length > 0 && ` at attempt ${acceptedAt(item)}`}{item.gain != null && ` · ${delta(item.gain)}`}{overall}
        </p>
        {item.tests.length > 0 && (
          <p className="break-words text-xs">Kept {plural(item.tests.length, "test")}: <span className="font-mono">{item.tests.join(", ")}</span></p>
        )}
      </div>
    );
  }
  if (item.status !== "rejected") return null;
  let text: string;
  if (item.rejectReason === "too_large" && item.steps.length === 0) {
    const narrowed = item.functions.length > 1 ? ", even after narrowing it to fewer functions" : "";
    text = `skipped: too large for one request${narrowed}. These functions are not tried again; coverage unchanged.`;
  } else {
    const lastStep = item.steps[item.steps.length - 1];
    const reason = lastStep && fixTooLarge(lastStep)
      ? "Fix request too large for the prompt budget (no model call)"
      : REJECTION_LABEL[item.rejectReason ?? ""] ?? item.rejectReason ?? "unknown reason";
    const after = item.steps.length ? ` after attempt ${item.steps.length}` : "";
    text = `rejected${after}: ${reason}. Changes rolled back, coverage unchanged.`;
  }
  return <p className="border-t border-border pt-2 text-sm"><span className="font-medium">Result:</span> {text}</p>;
}

function Item({ item }: { item: ItemView }) {
  const shown = item.functions.slice(0, SHOWN_FUNCTIONS).join(", ");
  const more = item.functions.length - SHOWN_FUNCTIONS;
  const statusColor = item.status === "accepted" ? "text-accent" : item.status === "rejected" ? "text-danger" : "text-muted";
  const empty = item.testPlan.length === 0 && item.steps.length === 0 && !finished(item);
  return (
    <details className={`${cardClass({ padded: false })} px-3 py-2`}>
      <summary className="cursor-pointer text-sm">
        <span className="inline-flex w-[calc(100%-1.25rem)] flex-wrap items-baseline justify-between gap-x-4 gap-y-0.5 align-top">
          <span className="min-w-0 break-all font-mono">
            {item.file} <span className="text-muted">· {shown}{more > 0 && ` +${more} more`}</span>
          </span>
          <span className={`shrink-0 ${statusColor}`}>
            {item.pending && !finished(item) ? <GroqWait pending={item.pending} /> : statusLabel(item)}
          </span>
          {item.steps.length > 0 && <span className="basis-full text-xs text-muted">{oneLiner(item.steps)}</span>}
        </span>
      </summary>
      <div className="mt-3 space-y-4">
        {item.testPlan.length > 0 && (
          <details>
            <summary className="cursor-pointer text-sm text-muted hover:text-text">What it decided to test</summary>
            <ul className="mt-1 list-disc space-y-0.5 pl-5 text-sm">
              {item.testPlan.map((s, i) => <li key={i} className="break-words"><span className="font-mono text-xs">{s.target}</span>: {s.scenario}</li>)}
            </ul>
          </details>
        )}
        {item.steps.length > 0 && (
          <ol aria-label="Attempts">
            {item.steps.map((st, i) => <StepView key={i} step={st} n={i + 1} item={item} next={item.steps[i + 1]} />)}
          </ol>
        )}
        <ResultLine item={item} />
        {empty && <p className="text-xs text-muted">{item.pending ? <GroqWait pending={item.pending} detailed /> : "No details yet."}</p>}
      </div>
    </details>
  );
}

export function Timeline({ iterations }: { iterations: IterationView[] }) {
  if (iterations.length === 0) return <EmptyState>Nothing yet.</EmptyState>;
  return (
    <ol className="space-y-6">
      {iterations.map((it) => (
        <li key={it.index}>
          <h3 className="mb-2 text-sm font-semibold">
            Iteration {it.index}{" "}
            <span className="font-mono text-muted">{pct(it.startPercent)}{it.endPercent != null && ` → ${pct(it.endPercent)}`}</span>
          </h3>
          <div className="space-y-2">{it.items.map((item, i) => <Item key={`${item.file}-${i}`} item={item} />)}</div>
        </li>
      ))}
    </ol>
  );
}
