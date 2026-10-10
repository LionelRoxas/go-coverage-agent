// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
"use client";
import { useState, type ReactNode } from "react";
import { AI_NOTE, costLine, EMPTY_PART, hasText, tidy, toMarkdown } from "@/lib/aiSummary";
import { api } from "@/lib/api";
import type { AiSummaryView } from "@/lib/runState";
import type { SummaryGenerated } from "@/lib/types";
import { GroqWait } from "./GroqWait";
import { Button, Card, Skeleton, SectionHeading, tabIds, Tabs } from "./ui";

type Audience = "business" | "technical";
const TABS = [
  { id: "business", label: "For stakeholders" },
  { id: "technical", label: "For engineering teams" },
] as const;
const PREFIX = "summary-";

/** `code` spans the model wrote in backticks, e.g. `go test ./...`. */
function Prose({ text }: { text: string }) {
  return tidy(text).split(/(`[^`]+`)/).map((part, i) =>
    part.length > 2 && part.startsWith("`") && part.endsWith("`")
      ? <code key={i} className="whitespace-nowrap rounded-sm border border-border bg-bg px-1 font-mono text-[0.8125rem]">{part.slice(1, -1)}</code>
      : part);
}

/** One labelled part of a summary; empty parts (the grounding check may empty them) are left out. */
function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid gap-1 sm:grid-cols-[10.5rem_minmax(0,1fr)] sm:gap-6">
      <dt className="text-sm text-muted">{label}</dt>
      <dd className="max-w-prose break-words text-sm leading-relaxed">{children}</dd>
    </div>
  );
}

function Bullets({ items }: { items: string[] }) {
  return <ul className="list-disc space-y-1 pl-4 marker:text-muted">{items.map((t, i) => <li key={i}><Prose text={t} /></li>)}</ul>;
}

function Headline({ text }: { text: string }) {
  if (!text) return null;
  return <p className="max-w-[40rem] text-lg font-semibold leading-snug tracking-tight text-balance sm:text-xl"><Prose text={text} /></p>;
}

/** Shown when the grounding check left nothing of a part. */
function Empty() {
  return <p className="text-sm text-muted">{EMPTY_PART} The summary card above has the run&apos;s measured results.</p>;
}

function Business({ ai }: { ai: SummaryGenerated }) {
  const b = ai.business;
  if (!hasText(b) && !ai.cost_usd) return <Empty />;
  return (
    <>
      {!hasText(b) && <Empty />}
      <Headline text={b.headline} />
      <dl className="space-y-4">
        {b.outcome && <Row label="Outcome"><Prose text={b.outcome} /></Row>}
        {(b.efficiency || ai.cost_usd) && (
          <Row label="Efficiency">
            {b.efficiency && <Prose text={b.efficiency} />}
            {ai.cost_usd && <span className="mt-1.5 block font-mono text-[0.8125rem] tabular-nums text-text">{costLine(ai.cost_usd)}</span>}
          </Row>
        )}
        {b.test_quality && <Row label="Test quality"><Prose text={b.test_quality} /></Row>}
        {b.risks.length > 0 && <Row label="Risks"><Bullets items={b.risks} /></Row>}
        {b.recommendation && (
          <Row label="Recommendation">
            <span className="block border-l-2 border-accent pl-3 font-medium"><Prose text={b.recommendation} /></span>
          </Row>
        )}
      </dl>
    </>
  );
}

function Technical({ ai }: { ai: SummaryGenerated }) {
  const t = ai.technical;
  if (!hasText(t)) return <Empty />;
  return (
    <>
      <Headline text={t.headline} />
      <dl className="space-y-4">
        {t.what_was_tested && <Row label="What was tested"><Prose text={t.what_was_tested} /></Row>}
        {t.test_quality && <Row label="Test quality"><Prose text={t.test_quality} /></Row>}
        {t.where_tests_live && <Row label="Where the tests live"><Prose text={t.where_tests_live} /></Row>}
        {t.how_to_run && <Row label="How to run"><Prose text={t.how_to_run} /></Row>}
        {t.gaps.length > 0 && (
          <Row label="Gaps">
            <ul className="divide-y divide-border rounded-sm border border-border">
              {t.gaps.map((g) => (
                <li key={g.file} className="grid gap-x-4 gap-y-0.5 px-3 py-2 sm:grid-cols-[minmax(0,14rem)_minmax(0,1fr)]">
                  <span className="break-all font-mono text-[0.8125rem]">{g.file}</span>
                  <span className="text-muted"><Prose text={g.detail} /></span>
                </li>
              ))}
            </ul>
          </Row>
        )}
        <Row label="Suspected bugs">
          {t.suspected_bugs.length > 0 ? <Bullets items={t.suspected_bugs} /> : <span className="text-muted">None reported.</span>}
        </Row>
        {t.rejected_or_failed && <Row label="Rejected or failed"><Prose text={t.rejected_or_failed} /></Row>}
        {t.next_steps.length > 0 && <Row label="Next steps"><Bullets items={t.next_steps} /></Row>}
      </dl>
    </>
  );
}

function CopyMarkdown({ markdown }: { markdown: string }) {
  const [copied, setCopied] = useState<"idle" | "done" | "failed">("idle");
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(markdown);
      setCopied("done");
    } catch {
      setCopied("failed");
    }
  };
  return (
    <Button size="sm" onClick={copy}>
      {copied === "done" ? "Copied" : copied === "failed" ? "Copy failed" : "Copy as Markdown"}
    </Button>
  );
}

/** The end-of-run summary under the summary card: two audiences in tabs, plus Write summary / Write again. */
export function AiSummary({ view, jobId, repo, model, onRequested }: {
  view: AiSummaryView; jobId: string; repo: string; model: string; onRequested: () => void;
}) {
  const [tab, setTab] = useState<Audience>("business");
  const [requesting, setRequesting] = useState(false);
  const [requestError, setRequestError] = useState<string | null>(null);
  const [stopping, setStopping] = useState(false);
  const [stopError, setStopError] = useState<string | null>(null);
  const waiting = view.status === "waiting";
  const cancelled = view.status === "failed" && view.error?.reason === "cancelled";
  const result = waiting ? undefined : view.result;

  const write = async () => {
    setRequesting(true);
    setRequestError(null);
    try {
      await api.writeSummary(jobId);
      onRequested();
    } catch (e) {
      setRequestError((e as Error).message);
    } finally {
      setRequesting(false);
    }
  };

  // Cancel during the summary call stops only the summary; the run keeps its result.
  const stop = async () => {
    setStopping(true);
    setStopError(null);
    try {
      await api.cancel(jobId);
    } catch (e) {
      setStopError((e as Error).message);
    } finally {
      setStopping(false);
    }
  };

  const action = view.status === "off" || view.status === "none" ? "Write summary"
    : view.status === "failed" && !result ? "Try again" : "Write again";
  const ids = tabIds(PREFIX, tab);

  return (
    <Card as="section" aria-labelledby="ai-summary-heading" className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <div className="space-y-0.5">
          <SectionHeading id="ai-summary-heading">Summary</SectionHeading>
          <p className="text-xs text-muted">{AI_NOTE.slice(0, -1)}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {result && view.generatedAt != null && (
            <CopyMarkdown markdown={toMarkdown(result, { repo, model, generatedAt: view.generatedAt })} />
          )}
          {waiting ? (
            <Button size="sm" variant="danger" onClick={stop} disabled={stopping}>
              {stopping ? "Stopping…" : "Stop summary"}
            </Button>
          ) : (
            <Button size="sm" onClick={write} disabled={requesting}>
              {requesting ? "Starting…" : action}
            </Button>
          )}
        </div>
      </div>

      {requestError && <p role="alert" className="text-sm text-danger">Couldn&apos;t start the summary: {requestError}</p>}
      {stopError && waiting && <p role="alert" className="text-sm text-danger">Couldn&apos;t stop the summary: {stopError}</p>}

      {waiting && (
        <div className="space-y-3">
          <p className="text-sm text-muted" aria-live="polite">
            Writing the summary…{view.pending && <> <GroqWait pending={view.pending} /></>}
          </p>
          <div aria-hidden className="max-w-[42rem] space-y-2.5">
            <Skeleton className="h-5 w-3/4" />
            {[92, 84, 88, 60].map((w, i) => <Skeleton key={i} className="h-3" style={{ width: `${w}%` }} />)}
          </div>
        </div>
      )}
      {view.status === "off" && <p className="text-sm text-muted">Summary was turned off for this run.</p>}
      {view.status === "none" && <p className="text-sm text-muted">No summary was written for this run.</p>}
      {cancelled && <p role="status" className="text-sm text-muted">The summary was stopped before it was written.</p>}
      {view.status === "failed" && view.error && !cancelled && (
        <p role="alert" className="text-sm text-danger">Couldn&apos;t write the summary: {view.error.message}</p>
      )}

      {result && (
        <div className="space-y-5">
          <Tabs label="Summary for" tabs={TABS} value={tab} onChange={setTab} idPrefix={PREFIX} />
          <div role="tabpanel" id={ids.panel} aria-labelledby={ids.tab} tabIndex={0} className="space-y-5">
            {tab === "business" ? <Business ai={result} /> : <Technical ai={result} />}
          </div>
          {result.dropped_sentences > 0 && (
            <p className="text-xs text-muted">
              {result.dropped_sentences === 1 ? "1 sentence was" : `${result.dropped_sentences} sentences were`} left out
              because {result.dropped_sentences === 1 ? "it" : "they"} named numbers or files that are not in this run&apos;s data.
            </p>
          )}
        </div>
      )}
    </Card>
  );
}
