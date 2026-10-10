// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { AiSummary } from "@/components/AiSummary";
import { CoverageChart } from "@/components/CoverageChart";
import { CoverageMeter } from "@/components/CoverageMeter";
import { Disagreements } from "@/components/Disagreements";
import { FileTable } from "@/components/FileTable";
import { MutationCard } from "@/components/MutationCard";
import { GroqWait } from "@/components/GroqWait";
import { SummaryCard } from "@/components/SummaryCard";
import { TestFiles } from "@/components/TestFiles";
import { Timeline } from "@/components/Timeline";
import {
  backLinkClass, Button, buttonClass, Card, codeBlockClass, LoadingStatus, pageTitleClass, SectionHeading, Skeleton, StatusChip, StatusPanel,
} from "@/components/ui";
import { api } from "@/lib/api";
import { duration, tokenLabel } from "@/lib/format";
import { runTokens, waitingAll } from "@/lib/runState";
import { useJobEvents } from "@/lib/useJobEvents";

function AllRuns() {
  return <Link href="/" className={backLinkClass}>← All runs</Link>;
}

function useElapsed(startedAt?: number, running?: boolean) {
  const [now, setNow] = useState(() => Date.now() / 1000);
  useEffect(() => {
    if (!running) return;
    const t = setInterval(() => setNow(Date.now() / 1000), 1000);
    return () => clearInterval(t);
  }, [running]);
  return startedAt ? Math.max(0, now - startedAt) : 0;
}

export default function JobPage() {
  const { id } = useParams<{ id: string }>();
  const { state, notFound, error, connection, summaryRequested, mutationRequested } = useJobEvents(id);
  const [cancelling, setCancelling] = useState(false);
  const [cancelError, setCancelError] = useState<string | null>(null);
  // "connecting" returns early below, so the clock and Cancel only ever see a known status.
  const running = state.status === "running";
  const elapsed = useElapsed(state.startedAt, running);
  const [waiting, ...alsoWaiting] = running ? waitingAll(state) : [];

  const cancel = async () => {
    setCancelling(true);
    setCancelError(null);
    try {
      await api.cancel(id);
    } catch (e) {
      setCancelError((e as Error).message);
      setCancelling(false);
    }
  };

  if (notFound) {
    return (
      <div className="space-y-8">
        <AllRuns />
        <StatusPanel title="This run no longer exists"
                     actions={<Link href="/" className={buttonClass({ variant: "primary" })}>Start a new one</Link>}>
          <p>There is no run with this id in ./output. It may have been deleted, or it is older than the runs the app reloads on startup.</p>
        </StatusPanel>
      </div>
    );
  }

  if (error && state.status === "connecting") {
    return (
      <div className="space-y-8">
        <AllRuns />
        <StatusPanel tone="danger" role="alert" title={"Couldn’t load this run"}
                     actions={<Link href="/" className={buttonClass()}>Back to setup</Link>}>
          <p>{error}</p>
        </StatusPanel>
      </div>
    );
  }

  // Until the first event arrives nothing about the run is known: placeholders instead of "…" and a 0% meter.
  if (state.status === "connecting") {
    return (
      <div className="space-y-10">
        <AllRuns />
        <div data-testid="job-loading" className="space-y-8">
          <LoadingStatus>Loading this run…</LoadingStatus>
          <div aria-hidden className="space-y-3">
            <Skeleton className="h-9 w-48" />
            <Skeleton className="h-4 w-72 max-w-full" />
          </div>
          <div aria-hidden className="space-y-3">
            <div className="flex items-end justify-between gap-4"><Skeleton className="h-10 w-32" /><Skeleton className="h-4 w-40" /></div>
            <Skeleton className="h-2 w-full rounded-full" />
          </div>
        </div>
      </div>
    );
  }

  const job = state.status; // narrowed: "connecting" returned above
  // Run mutation test: a finished run (not a failed one) that kept at least one test file.
  const keptTests = state.iterations.some((it) => it.items.some((i) => i.status === "accepted"));
  const mutationCard = job !== "running" && job !== "failed" && (keptTests || state.mutation) && (
    <MutationCard view={state.mutation} jobId={id} coverage={state.percent} onRequested={mutationRequested} />
  );
  return (
    <div className="space-y-10">
      <AllRuns />
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0 space-y-2">
          <h1 className={`break-all font-mono ${pageTitleClass}`}>{state.repoPath}</h1>
          <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-muted">
            <StatusChip status={job} />
            <span>
              {state.model}{running && ` · ${duration(state.summary?.duration_s ?? elapsed)}`} · {tokenLabel(runTokens(state), state.summaryTokens, state.summaryCalls)}
              {connection === "reconnecting" && running && " · reconnecting…"}
            </span>
          </p>
        </div>
        {running && (
          <Button variant="danger" onClick={cancel} disabled={cancelling}>
            {cancelling ? "Cancelling…" : "Cancel"}
          </Button>
        )}
      </header>

      {cancelError && <p role="alert" className="text-sm text-danger">Couldn&apos;t cancel: {cancelError}</p>}
      {error && <p role="alert" className="text-sm text-danger">{error}</p>}

      <div className="space-y-3">
        <CoverageMeter percent={state.percent} target={state.target} baseline={state.baseline?.percent} />
        {/* While running this says what is happening now; afterwards the summary or failure below says it. */}
        {running && (
          <p className="text-sm text-muted" aria-live="polite">
            {waiting ? <><GroqWait pending={waiting} others={alsoWaiting} detailed />{!alsoWaiting.length && ` (${waiting.file})`}
              {state.rateLimited && ` · ${state.rateLimited.file} paused ${Math.round(state.rateLimited.seconds)}s for the rate limit`}</>
              : state.activity}
          </p>
        )}
        {job === "interrupted" && (
          <p role="status" className="text-sm text-muted">The app stopped before this run finished; the results up to that point are shown.</p>
        )}
        {state.removedTests.length > 0 && (
          <p className="text-xs text-muted">Removed {state.removedTests.length} existing test files from the working copy before starting.</p>
        )}
      </div>

      {state.failure && (
        <Card as="section" tone="danger" role="alert" className="space-y-2">
          <SectionHeading>Run failed: {state.failure.message}</SectionHeading>
          <p className="text-sm text-muted">Any accepted tests were saved to ./output/{id}/tests.</p>
          {state.failure.output && <pre className={`max-h-64 whitespace-pre-wrap break-words ${codeBlockClass()}`}>{state.failure.output}</pre>}
        </Card>
      )}

      {state.summary && (
        <>
          <div className="space-y-4">
            <SummaryCard summary={state.summary} jobId={id} summaryTokens={state.summaryTokens} summaryCalls={state.summaryCalls} />
            {state.aiSummary && (
              <AiSummary view={state.aiSummary} jobId={id} repo={state.repoPath ?? ""} model={state.model ?? ""}
                         onRequested={summaryRequested} />
            )}
            {mutationCard}
          </div>
          <section className="space-y-3">
            <SectionHeading>Coverage by iteration</SectionHeading>
            <CoverageChart history={state.history} target={state.target} />
          </section>
          {state.summary.suspected_bugs.length > 0 && (
            <section className="space-y-2">
              <SectionHeading>Possible bugs found</SectionHeading>
              <ul className="list-disc pl-5 text-sm">
                {state.summary.suspected_bugs.map((b, i) => <li key={i}><span className="font-mono">{b.function}</span>: {b.description}</li>)}
              </ul>
            </section>
          )}
          <Disagreements items={state.summary.disagreements ?? []} />
          <section className="space-y-3">
            <SectionHeading>Generated tests</SectionHeading>
            <TestFiles jobId={id} files={state.summary.test_files} />
          </section>
          <section className="space-y-3">
            <SectionHeading>Coverage by file</SectionHeading>
            <FileTable rows={state.summary.per_file} />
          </section>
        </>
      )}

      {!state.summary && mutationCard}

      <section className="space-y-3">
        <SectionHeading>Activity</SectionHeading>
        <Timeline iterations={state.iterations} />
      </section>
    </div>
  );
}
