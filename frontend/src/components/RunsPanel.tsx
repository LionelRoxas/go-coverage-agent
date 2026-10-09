// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
"use client";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
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

const CHIP: Record<JobSnapshot["status"], { label: string; cls: string }> = {
  running: { label: "Running", cls: "border-accent bg-accent text-on-accent" },
  completed: { label: "Completed", cls: "border-accent text-accent" },
  cancelled: { label: "Cancelled", cls: "border-border text-muted" },
  failed: { label: "Failed", cls: "border-danger text-danger" },
};

function Chip({ status }: { status: JobSnapshot["status"] }) {
  const c = CHIP[status];
  return <span className={`shrink-0 rounded-full border px-2 py-0.5 text-xs font-medium ${c.cls}`}>{c.label}</span>;
}

function RunningCard({ job, now, onChanged }: { job: JobSnapshot; now: number; onChanged: () => void }) {
  const [cancelling, setCancelling] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { percent } = job;
  const target = job.request.target_coverage;

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
    <li className="space-y-3 rounded-sm border border-border border-l-4 border-l-accent bg-bg p-3">
      <div className="flex items-start justify-between gap-2">
        <span className="min-w-0 break-all font-mono text-sm font-medium">{job.request.repo_path}</span>
        <Chip status="running" />
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
        <span className="font-mono text-xs tabular-nums text-muted">{duration(Math.max(0, now - job.created_at))}</span>
        <div className="flex items-center gap-2">
          <Link href={`/jobs/${job.id}`} className="rounded-sm bg-accent px-3 py-1 text-xs font-medium text-on-accent">Open</Link>
          <button type="button" onClick={cancel} disabled={cancelling}
                  className="rounded-sm border border-border px-3 py-1 text-xs hover:border-danger hover:text-danger disabled:cursor-not-allowed disabled:opacity-60">
            {cancelling ? "Cancelling…" : "Cancel"}
          </button>
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
      <Link href={`/jobs/${job.id}`} className="block space-y-1 rounded-sm border border-border bg-bg px-3 py-2 hover:border-accent">
        <span className="flex items-start justify-between gap-2">
          <span className="min-w-0 break-all font-mono text-sm">{job.request.repo_path}</span>
          <Chip status={job.status} />
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

  const anyRunning = !!jobs?.some((j) => j.status === "running");

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
  const running = sorted.filter((j) => j.status === "running");
  const past = sorted.filter((j) => j.status !== "running");

  return (
    <aside aria-labelledby="runs-heading"
           className="space-y-3 self-start rounded-md border border-border bg-surface p-4 lg:sticky lg:top-20 lg:max-h-[calc(100vh-6.5rem)] lg:overflow-y-auto">
      <h2 id="runs-heading" className="flex items-baseline justify-between gap-2 border-b border-border pb-3 text-sm font-semibold">
        Run history
        {jobs && <span aria-label={`${jobs.length} runs`} className="font-mono text-xs font-normal tabular-nums text-muted">{jobs.length}</span>}
      </h2>
      {error && <p role="alert" className="text-xs text-danger">Couldn&apos;t load runs: {error}</p>}
      {jobs && jobs.length === 0 && !error && (
        <p className="rounded-sm border border-dashed border-border px-3 py-4 text-sm text-muted">
          No runs yet. Start one and it will appear here.
        </p>
      )}
      {running.length > 0 && (
        <ul className="space-y-2" aria-label="Running">
          {running.map((j) => <RunningCard key={j.id} job={j} now={now} onChanged={() => void load()} />)}
        </ul>
      )}
      {past.length > 0 && (
        <ul className="space-y-2" aria-label="Past runs">
          {past.map((j) => <PastRow key={j.id} job={j} now={now} />)}
        </ul>
      )}
      <p className="text-xs leading-relaxed text-muted">Runs are kept while the backend is running; files stay in ./output.</p>
    </aside>
  );
}
