// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
"use client";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { Button, buttonClass, cardClass, EmptyState, LoadingStatus, sectionHeadingClass, Skeleton, staticTileClass, StatusChip, tileClass } from "@/components/ui";
import { api } from "@/lib/api";
import { duration, pct } from "@/lib/format";
import type { JobSnapshot } from "@/lib/types";

const POLL_MS = 3000;

function ago(seconds: number) {
  if (seconds < 60) return "just now";
  const m = Math.floor(seconds / 60);
  if (m < 60) return `${m} min ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h} h ago`;
  return `${Math.floor(h / 24)} d ago`;
}

/** Running, or writing its AI summary: either way the backend refuses a new run until it is done. */
export const isBusy = (j: JobSnapshot) => j.status === "running" || !!j.writing_summary;

function RunningCard({ job, now, onChanged }: { job: JobSnapshot; now: number; onChanged: () => void }) {
  const [cancelling, setCancelling] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { percent } = job;
  const target = job.request.target_coverage;
  const summarizing = !!job.writing_summary;

  async function cancel() {
    setCancelling(true);
    setError(null);
    try {
      await api.cancel(job.id);
      onChanged();
    } catch (e) {
      setError((e as Error).message);
      setCancelling(false);
    }
  }

  return (
    <li className={`space-y-3 ${staticTileClass({ accent: true })}`}>
      <div className="flex items-start justify-between gap-2">
        <span className="min-w-0 break-all font-mono text-sm font-medium">{job.request.repo_path}</span>
        <StatusChip status={summarizing ? job.status : "running"} />
      </div>
      <div className="space-y-1.5">
        <div className="flex items-baseline justify-between gap-2 text-xs text-muted">
          <span className="font-mono text-base font-semibold tabular-nums text-text">
            {percent == null ? <span className="font-sans text-sm font-normal text-muted">Measuring baseline…</span> : pct(percent)}
          </span>
          <span>target {pct(target)}</span>
        </div>
        <div className="relative h-1.5 rounded-full bg-border" role="meter" aria-valuemin={0} aria-valuemax={100}
             aria-valuenow={percent == null ? undefined : Math.round(percent * 10) / 10}
             aria-label={`Coverage ${pct(percent)}, target ${pct(target)}`}>
          <div className="h-1.5 rounded-full bg-accent transition-[width] duration-500" style={{ width: `${Math.min(percent ?? 0, 100)}%` }} />
          <div data-testid="target-marker" className="absolute -top-1 h-3.5 w-0.5 bg-text" style={{ left: `${Math.min(target, 100)}%` }} />
        </div>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2">
        {summarizing
          ? <span className="text-xs text-muted">Writing summary…</span>
          : <span className="font-mono text-xs tabular-nums text-muted">{duration(Math.max(0, now - job.created_at))}</span>}
        <div className="flex items-center gap-2">
          <Link href={`/jobs/${job.id}`} className={buttonClass({ variant: "primary", size: "sm" })}>Open</Link>
          <Button variant="danger" size="sm" onClick={cancel} disabled={cancelling}>
            {cancelling ? "Cancelling…" : summarizing ? "Stop summary" : "Cancel"}
          </Button>
        </div>
      </div>
      {error && <p role="alert" className="text-xs text-danger">Couldn&apos;t cancel: {error}</p>}
    </li>
  );
}

function PastRow({ job, now }: { job: JobSnapshot; now: number }) {
  const s = job.summary;
  const result = s ? `${pct(s.baseline_percent)} → ${pct(s.final_percent)}` : "—";
  return (
    <li>
      <Link href={`/jobs/${job.id}`} className={`${tileClass()} block space-y-1`}>
        <span className="flex items-start justify-between gap-2">
          <span className="min-w-0 break-all font-mono text-sm">{job.request.repo_path}</span>
          <StatusChip status={job.status} />
        </span>
        <span className="flex flex-wrap items-baseline justify-between gap-x-3 text-xs text-muted">
          <span><span className="font-mono tabular-nums text-text">{result}</span> · target {pct(job.request.target_coverage)}</span>
          <span>{ago(now - job.created_at)}</span>
        </span>
      </Link>
    </li>
  );
}

export function RunsPanel({ onJobs }: { onJobs?: (jobs: JobSnapshot[]) => void }) {
  const [jobs, setJobs] = useState<JobSnapshot[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [now, setNow] = useState(() => Date.now() / 1000);
  const inFlight = useRef(false);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  // Skips when a fetch is already pending (slow backend) and drops results that arrive after unmount.
  const load = useCallback(async () => {
    if (inFlight.current) return;
    inFlight.current = true;
    try {
      const j = await api.jobs();
      if (!mounted.current) return;
      setJobs(j);
      setNow(Date.now() / 1000);
      setError(null);
      onJobs?.(j);
    } catch (e) {
      if (mounted.current) setError((e as Error).message);
    } finally {
      inFlight.current = false;
    }
  }, [onJobs]);

  const anyRunning = !!jobs?.some(isBusy);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  useEffect(() => {
    if (!anyRunning) return;
    const t = setInterval(() => void load(), POLL_MS);
    return () => clearInterval(t);
  }, [anyRunning, load]);

  // The 1 s ticker drives the running cards' elapsed time, so it only runs while a job is running.
  useEffect(() => {
    if (!anyRunning) return;
    const t = setInterval(() => setNow(Date.now() / 1000), 1000);
    return () => clearInterval(t);
  }, [anyRunning]);

  const sorted = [...(jobs ?? [])].sort((a, b) => b.created_at - a.created_at);
  const running = sorted.filter(isBusy);
  const past = sorted.filter((j) => !isBusy(j));

  return (
    <aside aria-labelledby="runs-heading"
           className={`${cardClass()} space-y-3 self-start lg:sticky lg:top-20 lg:max-h-[calc(100vh-6.5rem)] lg:overflow-y-auto`}>
      <h2 id="runs-heading" className={`flex items-baseline justify-between gap-2 border-b border-border pb-3 ${sectionHeadingClass}`}>
        Run history
        {jobs && <span aria-label={`${jobs.length} runs`} className="font-mono text-xs font-normal tabular-nums text-muted">{jobs.length}</span>}
      </h2>
      {error && <p role="alert" className="text-xs text-danger">Couldn&apos;t load runs: {error}</p>}
      {jobs === null && !error && (
        <div data-testid="runs-loading" className="space-y-2">
          <LoadingStatus>Loading runs…</LoadingStatus>
          {[0, 1, 2].map((i) => (
            <div key={i} aria-hidden className={`space-y-2 ${staticTileClass()}`}>
              <span className="flex justify-between gap-4"><Skeleton className="h-4 w-28" /><Skeleton className="h-4 w-16 rounded-full" /></span>
              <span className="flex justify-between gap-4"><Skeleton className="h-3 w-40" /><Skeleton className="h-3 w-12" /></span>
            </div>
          ))}
        </div>
      )}
      {jobs && jobs.length === 0 && !error && (
        <EmptyState>Pick a repository and press Start — your runs appear here.</EmptyState>
      )}
      {running.length > 0 && (
        <ul className="space-y-2" aria-label="Running">
          {/* A new card once the run ends and its summary is being written, so "Cancelling…" does not stick. */}
          {running.map((j) => <RunningCard key={`${j.id}-${j.writing_summary ? "summary" : "run"}`} job={j} now={now}
                                           onChanged={() => void load()} />)}
        </ul>
      )}
      {past.length > 0 && (
        <ul className="space-y-2" aria-label="Past runs">
          {past.map((j) => <PastRow key={j.id} job={j} now={now} />)}
        </ul>
      )}
      <p className="text-xs leading-relaxed text-muted">Runs are saved in ./output and reload when the app restarts.</p>
    </aside>
  );
}
