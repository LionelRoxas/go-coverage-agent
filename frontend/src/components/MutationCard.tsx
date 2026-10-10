// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import { pct } from "@/lib/format";
import type { MutationView } from "@/lib/runState";
import type { Mutant } from "@/lib/types";
import { Button, Card, codeBlockClass, SectionHeading } from "./ui";

export const MUTATION_NOTE = "Plant small bugs in the code and check whether the kept tests catch them. No AI, no tokens.";

const caught = (m: Mutant) => m.status === "killed" || m.status === "timeout";
const OUTCOME: Record<Mutant["status"], string> = {
  killed: "caught", timeout: "caught (timed out)", survived: "missed", invalid: "skipped (does not build or fails go vet)",
};

/** `file:line  before → after`, e.g. `percentile.go:41  i < n → i <= n` (just the operators on older results). */
function Diff({ m }: { m: Mutant }) {
  return (
    <span className="flex min-w-0 flex-wrap items-baseline gap-x-3 font-mono text-[0.8125rem]">
      <span className="text-muted">{m.file}:{m.line}</span>
      <span className="break-all">{m.before ?? m.original} <span className="text-muted">→</span> {m.after ?? m.mutated}</span>
    </span>
  );
}

/** "Run mutation test" on a finished run: idle, running (live list), done (score, per file, missed bugs) or failed. */
export function MutationCard({ view, jobId, coverage, onRequested }: {
  view?: MutationView; jobId: string; coverage: number; onRequested: () => void;
}) {
  const [requesting, setRequesting] = useState(false);
  const [requestError, setRequestError] = useState<string | null>(null);
  const [stopping, setStopping] = useState(false);
  const [stopError, setStopError] = useState<string | null>(null);
  const running = view?.status === "running";
  const result = view?.status === "done" ? view.result : undefined;
  const cancelled = view?.status === "failed" && view.error?.reason === "cancelled";

  const start = async () => {
    setRequesting(true);
    setRequestError(null);
    try {
      await api.mutationTest(jobId);
      onRequested();
    } catch (e) {
      setRequestError((e as Error).message);
    } finally {
      setRequesting(false);
    }
  };

  // Cancel stops only the mutation test; the run keeps its result.
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

  const mutants = view?.mutants ?? [];
  const killed = mutants.filter(caught).length;
  const survived = mutants.filter((m) => m.status === "survived").length;

  return (
    <Card as="section" aria-labelledby="mutation-heading" className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <div className="space-y-0.5">
          <SectionHeading id="mutation-heading">Test quality</SectionHeading>
          <p className="text-xs text-muted">{MUTATION_NOTE}</p>
        </div>
        {running ? (
          <Button size="sm" variant="danger" onClick={stop} disabled={stopping}>{stopping ? "Cancelling…" : "Cancel"}</Button>
        ) : (
          <Button size="sm" onClick={start} disabled={requesting}>
            {requesting ? "Starting…" : view ? "Run again" : "Run mutation test"}
          </Button>
        )}
      </div>

      {requestError && <p role="alert" className="text-sm text-danger">Couldn&apos;t start the mutation test: {requestError}</p>}
      {stopError && running && <p role="alert" className="text-sm text-danger">Couldn&apos;t cancel: {stopError}</p>}

      {running && (
        <div className="space-y-3">
          <p className="text-sm text-muted" aria-live="polite">
            {view.total == null ? "Preparing a fresh copy and running the kept tests…"
              : `Mutant ${Math.min(mutants.length + 1, view.total)} of ${view.total} · ${killed} caught · ${survived} missed`}
          </p>
          {view.total != null && view.total > 0 && (
            <div className="h-1.5 rounded-full bg-border">
              <div className="h-1.5 rounded-full bg-accent transition-[width]" style={{ width: `${(100 * mutants.length) / view.total}%` }} />
            </div>
          )}
          {mutants.length > 0 && (
            <ol className="max-h-64 space-y-1 overflow-y-auto text-sm">
              {mutants.map((m) => (
                <li key={m.index} className="flex items-baseline gap-2">
                  <span aria-hidden className={caught(m) ? "text-accent" : m.status === "survived" ? "text-danger" : "text-muted"}>
                    {caught(m) ? "✓" : m.status === "survived" ? "✗" : "–"}
                  </span>
                  <Diff m={m} />
                  <span className="shrink-0 text-xs text-muted">{OUTCOME[m.status]}</span>
                </li>
              ))}
            </ol>
          )}
        </div>
      )}

      {cancelled && <p role="status" className="text-sm text-muted">The mutation test was cancelled before it finished.</p>}
      {view?.status === "failed" && !cancelled && view.error && (
        <div className="space-y-2">
          <p role="alert" className="text-sm text-danger">Mutation test failed: {view.error.message}</p>
          {view.error.output && (
            <pre className={`max-h-48 whitespace-pre-wrap break-words ${codeBlockClass()}`}>{view.error.output}</pre>
          )}
        </div>
      )}

      {result && (
        <div className="space-y-5">
          <div className="flex flex-wrap items-baseline gap-x-6 gap-y-1">
            <p>
              <span className="font-mono text-4xl font-semibold tabular-nums">{pct(result.score)}</span>
              <span className="ml-2 text-sm text-muted">mutation score</span>
            </p>
            <p className="text-sm text-muted">coverage <span className="font-mono tabular-nums text-text">{pct(coverage)}</span></p>
          </div>
          <p className="text-sm text-muted">
            {result.killed} of {result.killed + result.survived} planted bugs caught
            {result.timeouts > 0 && ` (${result.timeouts} by timing out)`}
            {result.invalid > 0 && ` · ${result.invalid} skipped because they do not build`} · {result.total} mutants sampled from covered code.
          </p>
          {result.per_file.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-left text-xs text-muted">
                  <tr><th className="py-2 pr-4 font-medium">File</th><th className="pr-4 font-medium">Caught</th><th className="pr-4 font-medium">Missed</th><th className="font-medium">Score</th></tr>
                </thead>
                <tbody className="font-mono tabular-nums">
                  {result.per_file.map((f) => (
                    <tr key={f.file} className="border-t border-border">
                      <td className="py-1.5 pr-4">{f.file}</td><td className="pr-4">{f.killed}</td><td className="pr-4">{f.survived}</td><td>{pct(f.score)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {result.survived > 0 && (
            <div className="space-y-2">
              <h3 className="text-sm font-medium">Missed bugs</h3>
              <ul className="space-y-1 text-sm">
                {result.mutants.filter((m) => m.status === "survived").map((m) => <li key={m.index}><Diff m={m} /></li>)}
              </ul>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}
