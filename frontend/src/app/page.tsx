// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
"use client";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { RepoPicker } from "@/components/RepoPicker";
import { RunsPanel } from "@/components/RunsPanel";
import { api, ApiError } from "@/lib/api";
import { tokens } from "@/lib/format";
import type { Health, JobOptions, JobSnapshot, RepoInfo } from "@/lib/types";

const DEFAULTS: Pick<JobOptions, "max_iterations" | "min_gain" | "targets_per_iteration" | "max_fix_attempts"> = {
  max_iterations: 20, min_gain: 1, targets_per_iteration: 3, max_fix_attempts: 2,
};

const inputCls = "rounded-sm border border-border bg-surface px-2 py-1.5 font-mono text-sm";

export default function SetupPage() {
  const router = useRouter();
  const [health, setHealth] = useState<Health | null>(null);
  const [repos, setRepos] = useState<RepoInfo[]>([]);
  const [running, setRunning] = useState(false);
  const [repo, setRepo] = useState("");
  const [target, setTarget] = useState(80);
  const [opts, setOpts] = useState(DEFAULTS);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [cloning, setCloning] = useState(false);

  useEffect(() => {
    Promise.all([api.health(), api.repos()])
      .then(([h, r]) => {
        setHealth(h);
        setRepos(r);
        setRepo((cur) => cur || r[0]?.path || "");
      })
      .catch((e) => setError(e.message));
  }, []);

  const onJobs = useCallback((jobs: JobSnapshot[]) => setRunning(jobs.some((j) => j.status === "running")), []);

  async function useSample() {
    setCloning(true);
    setError(null);
    try {
      const info = await api.cloneSample();
      setRepos(await api.repos());
      setRepo(info.path);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setCloning(false);
    }
  }

  async function start(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const { job_id } = await api.startJob({ repo_path: repo, target_coverage: target, options: opts });
      router.push(`/jobs/${job_id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
      setBusy(false);
    }
  }

  const targetValid = Number.isFinite(target) && target >= 1 && target <= 100;

  return (
    <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_22rem] lg:gap-12">
      <form onSubmit={start} className="min-w-0 space-y-8">
        <section>
          <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Raise Go test coverage, autonomously</h1>
          <p className="mt-3 max-w-prose text-sm leading-relaxed text-muted">
            Pick a Go module and a target. The agent measures coverage, plans what to test, writes tests with an LLM,
            compiles and runs them, keeps only the ones that pass and add coverage, and repeats.
          </p>
        </section>

        {health && !health.llm_configured && (
          <div role="alert" className="rounded-sm border border-warn border-l-4 px-4 py-3 text-sm">
            No Groq API key configured. Add <code className="font-mono">GROQ_API_KEY</code> to <code className="font-mono">.env</code> and restart <code className="font-mono">docker compose</code>.
          </div>
        )}
        <RepoPicker repos={repos} value={repo} onChange={setRepo} onUseSample={useSample} cloning={cloning} />

        <div className="space-y-2">
          <label htmlFor="target" className="text-sm font-medium">Target coverage</label>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
            <input id="target" type="range" min={10} max={100} step={1} value={Math.min(100, Math.max(10, target || 10))}
                   onChange={(e) => setTarget(Number(e.target.value))} className="w-full max-w-64 accent-[var(--accent)]" />
            <div className="flex items-center gap-2">
              <input type="number" min={1} max={100} value={Number.isNaN(target) ? "" : target} aria-label="Target coverage percent"
                     onChange={(e) => setTarget(e.target.value === "" ? NaN : Number(e.target.value))}
                     className={`w-20 ${inputCls}`} />
              <span className="text-sm text-muted">%</span>
            </div>
          </div>
          {!targetValid && <p className="text-xs text-danger">Enter a target between 1 and 100.</p>}
        </div>

        <details className="rounded-sm border border-border bg-surface px-4 py-3">
          <summary className="cursor-pointer text-sm font-medium">Advanced</summary>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            {([
              ["max_iterations", "Max iterations", 1, 30, 1],
              ["min_gain", "Stop when an iteration gains less than (pp)", 0, 10, 0.5],
              ["targets_per_iteration", "Files per iteration", 1, 5, 1],
              ["max_fix_attempts", "Fix attempts per file", 0, 4, 1],
            ] as const).map(([key, label, min, max, step]) => (
              <label key={key} className="space-y-1 text-sm">
                <span className="block text-muted">{label}</span>
                <input type="number" min={min} max={max} step={step} value={opts[key]}
                       onChange={(e) => setOpts({ ...opts, [key]: Number(e.target.value) })}
                       className={`w-24 ${inputCls}`} />
              </label>
            ))}
          </div>
        </details>

        <ul className="max-w-prose space-y-1 text-xs leading-relaxed text-muted">
          <li>Existing <code className="font-mono">_test.go</code> files are removed from a working copy. Your repository is never modified.</li>
          <li>Source code of the selected repository is sent to Groq.</li>
          {health && <li>Tests are written by <span className="font-mono">{health.model}</span> on Groq.</li>}
          {health && <li>About <span className="font-mono">{tokens(health.tokens_left_today)}</span> Groq tokens left today on this machine.</li>}
        </ul>

        {error && <p role="alert" className="text-sm text-danger">{error}</p>}

        <button type="submit" disabled={busy || !repo || !targetValid || !health?.llm_configured || running}
                className="rounded-sm bg-accent px-5 py-2 text-sm font-medium text-on-accent disabled:cursor-not-allowed disabled:opacity-40">
          {busy ? "Starting…" : "Start"}
        </button>
        {running && <p className="text-xs text-muted">A run is in progress. Follow it in the Runs panel.</p>}
      </form>
      <RunsPanel onJobs={onJobs} />
    </div>
  );
}
