// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { CoverageChart } from "@/components/CoverageChart";
import { CoverageMeter } from "@/components/CoverageMeter";
import { FileTable } from "@/components/FileTable";
import { GroqWait } from "@/components/GroqWait";
import { SummaryCard } from "@/components/SummaryCard";
import { TestFiles } from "@/components/TestFiles";
import { Timeline } from "@/components/Timeline";
import { api } from "@/lib/api";
import { duration, tokens } from "@/lib/format";
import { waitingOn } from "@/lib/runState";
import { useJobEvents } from "@/lib/useJobEvents";

function AllRuns() {
  return <Link href="/" className="inline-block text-sm text-muted hover:text-accent">← All runs</Link>;
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
  const { state, notFound, error, connection } = useJobEvents(id);
  const [cancelling, setCancelling] = useState(false);
  const [cancelError, setCancelError] = useState<string | null>(null);
  const running = state.status === "running" || state.status === "connecting";
  const elapsed = useElapsed(state.startedAt, running);
  const waiting = running ? waitingOn(state) : undefined;

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
      <div className="space-y-4">
        <AllRuns />
        <p className="text-sm">
          This run no longer exists (the backend was restarted). <Link className="text-accent underline-offset-4 hover:underline" href="/">Start a new one</Link>.
        </p>
      </div>
    );
  }

  if (error && state.status === "connecting") {
    return (
      <div className="space-y-4">
        <AllRuns />
        <section role="alert" className="space-y-2 rounded-md border border-danger p-4">
          <h1 className="font-semibold">Couldn&apos;t load this run</h1>
          <p className="text-sm">{error}</p>
          <Link className="text-sm text-accent underline-offset-4 hover:underline" href="/">Back to setup</Link>
        </section>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <AllRuns />
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div className="min-w-0">
          <h1 className="break-all font-mono text-lg font-semibold">{state.repoPath ?? "…"}</h1>
          <p className="text-xs text-muted">
            {state.model} · {state.status}{running && ` · ${duration(state.summary?.duration_s ?? elapsed)}`} · {tokens(state.tokens)} tokens
            {connection === "reconnecting" && running && " · reconnecting…"}
          </p>
        </div>
        {running && (
          <button type="button" onClick={cancel} disabled={cancelling}
                  className="rounded-md border border-border px-3 py-1.5 text-sm hover:border-danger hover:text-danger disabled:opacity-60">
            {cancelling ? "Cancelling…" : "Cancel"}
          </button>
        )}
      </header>

      {cancelError && <p role="alert" className="text-sm text-danger">Couldn&apos;t cancel: {cancelError}</p>}
      {error && <p role="alert" className="text-sm text-danger">{error}</p>}

      <CoverageMeter percent={state.percent} target={state.target} baseline={state.baseline?.percent} />
      <p className="text-sm text-muted" aria-live="polite">
        {waiting ? <><GroqWait pending={waiting} detailed /> ({waiting.file})</> : state.activity}
      </p>
      {state.removedTests.length > 0 && (
        <p className="text-xs text-muted">Removed {state.removedTests.length} existing test files from the working copy before starting.</p>
      )}

      {state.failure && (
        <section role="alert" className="space-y-2 rounded-md border border-danger p-4">
          <h2 className="font-semibold">Run failed: {state.failure.message}</h2>
          <p className="text-sm text-muted">Any accepted tests were saved to ./output/{id}/tests.</p>
          {state.failure.output && <pre className="max-h-64 overflow-auto whitespace-pre-wrap break-words rounded bg-surface p-2 font-mono text-xs">{state.failure.output}</pre>}
        </section>
      )}

      {state.summary && (
        <>
          <SummaryCard summary={state.summary} jobId={id} />
          <section className="space-y-3">
            <h2 className="text-sm font-medium">Coverage by iteration</h2>
            <CoverageChart history={state.history} target={state.target} />
          </section>
          {state.summary.suspected_bugs.length > 0 && (
            <section className="space-y-2">
              <h2 className="text-sm font-medium">Possible bugs found</h2>
              <ul className="list-disc pl-5 text-sm">
                {state.summary.suspected_bugs.map((b, i) => <li key={i}><span className="font-mono">{b.function}</span>: {b.description}</li>)}
              </ul>
            </section>
          )}
          <section className="space-y-3">
            <h2 className="text-sm font-medium">Generated tests</h2>
            <TestFiles jobId={id} files={state.summary.test_files} />
          </section>
          <section className="space-y-3">
            <h2 className="text-sm font-medium">Coverage by file</h2>
            <FileTable rows={state.summary.per_file} />
          </section>
        </>
      )}

      <section className="space-y-3">
        <h2 className="text-sm font-medium">Activity</h2>
        <Timeline iterations={state.iterations} />
      </section>
    </div>
  );
}
