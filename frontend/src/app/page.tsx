// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
"use client";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { RepoPicker, type PickerTab } from "@/components/RepoPicker";
import { RunsPanel } from "@/components/RunsPanel";
import { TokenBudget, budgetBlocked } from "@/components/TokenBudget";
import { api, ApiError } from "@/lib/api";
import type { Health, JobOptions, JobSnapshot, RepoInfo, Sample } from "@/lib/types";

const DEFAULTS: Pick<JobOptions, "max_iterations" | "min_gain" | "targets_per_iteration" | "max_fix_attempts"> = {
  max_iterations: 20, min_gain: 1, targets_per_iteration: 3, max_fix_attempts: 2,
};

const TAB_KEY = "gca-repo-tab";

function pickTab(folders: RepoInfo[]): PickerTab {
  if (folders.length === 0) return "samples";
  try {
    const t = localStorage.getItem(TAB_KEY);
    if (t === "samples" || t === "folders") return t;
  } catch {
    // storage unavailable: fall through to the default
  }
  return "folders";
}

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
  const [samples, setSamples] = useState<Sample[]>([]);
  const [tab, setTab] = useState<PickerTab>("samples");
  const [samplesFailed, setSamplesFailed] = useState(false);

  const sampleIds = new Set(samples.map((s) => s.id));
  const folders = repos.filter((r) => !sampleIds.has(r.path));
  const selected = repos.find((r) => r.path === repo);

  useEffect(() => {
    Promise.allSettled([api.health(), api.repos(), api.samples()]).then(([h, r, s]) => {
      const list = r.status === "fulfilled" ? r.value : [];
      const sampleList = s.status === "fulfilled" ? s.value : [];
      const ids = new Set(sampleList.map((x) => x.id));
      const own = list.filter((x) => !ids.has(x.path));
      if (h.status === "fulfilled") setHealth(h.value);
      setRepos(list);
      setSamples(sampleList);
      setSamplesFailed(s.status === "rejected");
      setTab(pickTab(own));
      setRepo((cur) => cur || own[0]?.path || list[0]?.path || "");
      const failed = [h, r].find((x) => x.status === "rejected");
      if (failed && failed.status === "rejected") setError((failed.reason as Error).message);
    });
  }, []);

  function changeTab(t: PickerTab) {
    setTab(t);
    try {
      localStorage.setItem(TAB_KEY, t);
    } catch {
      // remembering the tab is a convenience only
    }
  }

  async function reload() {
    const [r, s] = await Promise.all([api.repos(), api.samples()]);
    setRepos(r);
    setSamples(s);
  }

  const onJobs = useCallback((jobs: JobSnapshot[]) => setRunning(jobs.some((j) => j.status === "running")), []);

  async function download(id: string) {
    const info = await api.downloadSample(id);
    setRepo(info.path);
    try {
      await reload();
    } catch {
      // the clone succeeded; the lists refresh on the next Refresh
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
  const noBudget = health != null && budgetBlocked(health.tokens_left_today);

  return (
    <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_23rem] lg:gap-14">
      <form onSubmit={start} className="min-w-0 max-w-2xl space-y-8">
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
        <RepoPicker tab={tab} onTabChange={changeTab} samples={samples} folders={folders} value={repo} onChange={setRepo}
                    onDownload={download} onRefresh={reload} hostDir={health?.host_repos_dir ?? null} samplesFailed={samplesFailed} />
        <div className="space-y-1.5">
          <p className="text-sm text-muted">
            {selected ? (
              <>Selected: <span className="font-mono text-text">{selected.path}</span> · <span className="font-mono">{selected.module}</span> · {selected.go_files} source files</>
            ) : "Nothing selected yet. Pick a repository above."}
          </p>
          <p className="max-w-prose text-xs leading-relaxed text-muted">
            {selected ? "Its" : "The selected repository's"} source code is sent to Groq{health ? <>, where <span className="font-mono">{health.model}</span> writes the tests</> : " to write the tests"}.
            {" "}The agent works on a copy with the existing <code className="font-mono">_test.go</code> files removed; your repository is never modified.
          </p>
        </div>

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

        <details className="group max-w-xl">
          <summary className="flex w-fit cursor-pointer list-none items-center gap-1.5 rounded-sm text-sm text-muted hover:text-text [&::-webkit-details-marker]:hidden">
            <svg aria-hidden viewBox="0 0 12 12" className="h-3 w-3 transition-transform group-open:rotate-90" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M4 2l4 4-4 4" /></svg>
            Advanced options
          </summary>
          <div className="mt-3 grid gap-x-6 gap-y-4 rounded-sm border border-border bg-surface/60 p-4 sm:grid-cols-2">
            {([
              ["max_iterations", "Max iterations", 1, 30, 1],
              ["min_gain", "Stop when an iteration gains less than (pp)", 0, 10, 0.5],
              ["targets_per_iteration", "Files per iteration", 1, 5, 1],
              ["max_fix_attempts", "Fix attempts per file", 0, 4, 1],
            ] as const).map(([key, label, min, max, step]) => (
              <label key={key} className="flex flex-col justify-between gap-1.5 text-sm">
                <span className="block text-xs leading-snug text-muted">{label}</span>
                <input type="number" min={min} max={max} step={step} value={opts[key]}
                       onChange={(e) => setOpts({ ...opts, [key]: Number(e.target.value) })}
                       className={`w-24 ${inputCls}`} />
              </label>
            ))}
          </div>
        </details>

        {error && <p role="alert" className="text-sm text-danger">{error}</p>}

        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
            <button type="submit" disabled={busy || !repo || !targetValid || !health?.llm_configured || running || noBudget}
                    aria-describedby={noBudget ? "budget-reason" : undefined}
                    className="shrink-0 rounded-sm bg-accent px-5 py-2 text-sm font-medium text-on-accent disabled:cursor-not-allowed disabled:opacity-40">
              {busy ? "Starting…" : "Start"}
            </button>
            {health && <TokenBudget left={health.tokens_left_today} id="budget-reason" />}
          </div>
          {running && <p className="text-xs text-muted">A run is in progress. Follow it in Run history.</p>}
        </div>
      </form>
      <RunsPanel onJobs={onJobs} />
    </div>
  );
}
