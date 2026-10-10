// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { RepoPicker, type PickerTab } from "@/components/RepoPicker";
import { isBusy, RunsPanel } from "@/components/RunsPanel";
import { MIN_TOKENS_TO_START, TokenBudget, budgetBlocked } from "@/components/TokenBudget";
import { WizardStepper, type StepState } from "@/components/WizardStepper";
import { Button, cardClass, cx, inlineLinkClass, inputClass, ledeClass, pageTitleClass, sectionHeadingClass } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { now } from "@/lib/clock";
import type { Health, JobOptions, JobSnapshot, RepoInfo, Sample } from "@/lib/types";
import type { PickedFile } from "@/lib/upload";

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

// Header and body share the columns, so the measured run sits above Run history and the aside starts level with the wizard.
const COLUMNS = "grid gap-10 lg:grid-cols-[minmax(0,1fr)_23rem] lg:gap-14";

// Coverage after each round of a real run: montanaflynn/stats, goal 100%, max_iterations 30, min_gain 0.5, run 0e1f8bf7442a
// (output/0e1f8bf7442a/report.json, iterations[].end_percent; 0% at the start, 612 s in total).
const MEASURED = [17.2, 33.9, 44.6, 51.6, 58.9, 64.7, 69.8, 72.0, 76.2, 80.0, 83.2, 86.0, 88.5, 90.8, 92.5, 94.2, 96.2, 97.0, 98.2, 99.4, 99.8, 100];

/** One column per round: the filled part is the share of code tested, the dashed part the gap still left. */
function MeasuredRun() {
  return (
    <figure className="min-w-0 max-w-md space-y-3 lg:max-w-none">
      <div role="img" aria-label={`Coverage after each of ${MEASURED.length} rounds, rising from 17.2% to 100%`}
           className="flex h-12 items-end gap-[3px] sm:h-16 border-b border-border pb-px">
        {MEASURED.map((p, i) => (
          <span key={i} aria-hidden className="flex h-full flex-1 flex-col">
            <span style={{ height: `${100 - p}%` }} className={p < 100 ? "rounded-t-[2px] border border-b-0 border-dashed border-border-strong" : ""} />
            <span style={{ height: `${p}%` }} className="rounded-t-[2px] bg-accent" />
          </span>
        ))}
      </div>
      <figcaption className="text-xs leading-relaxed text-muted">
        Measured on <span className="font-mono text-text">montanaflynn/stats</span>: 0% to 100% of the code tested in 22 rounds (goal 100%, up to 30 rounds), about 10 minutes.
      </figcaption>
    </figure>
  );
}

type Limits = typeof DEFAULTS;
type LimitKey = keyof Limits;

/** The four advanced limits: field, label, range, input step and whether only whole numbers are allowed. */
const LIMITS: readonly { key: LimitKey; label: string; min: number; max: number; step: number }[] = [
  { key: "max_iterations", label: "Max iterations", min: 1, max: 30, step: 1 },
  { key: "min_gain", label: "Stop when an iteration gains less than (pp)", min: 0, max: 10, step: 0.5 },
  { key: "targets_per_iteration", label: "Files per iteration", min: 1, max: 5, step: 1 },
  { key: "max_fix_attempts", label: "Fix attempts per file", min: 0, max: 4, step: 1 },
];

/** The error for one limit, or null when its value is usable. */
function limitError(value: number, { min, max, step }: (typeof LIMITS)[number]): string | null {
  const whole = step === 1;
  if (Number.isFinite(value) && value >= min && value <= max && (!whole || Number.isInteger(value))) return null;
  return whole ? `Enter a whole number from ${min} to ${max}.` : `Enter a number from ${min} to ${max}.`;
}

const STEPS = ["Choose a repository", "Set a target", "Advanced options (optional)", "Review & start"] as const;
const HINTS = [
  "Pick a sample (it downloads the first time), or upload a Go project folder of your own.",
  "The share of the code you want tests to run. 80% is a good start; higher takes longer.",
  "The defaults work for most runs. Change them to limit how long a run keeps trying.",
  "Usually 1–5 minutes on a paid Groq key; free-trial keys take much longer. You can leave this page; the run keeps going.",
] as const;
const REVIEW = 3;
/**
 * Start ignores presses this soon after the review opens: Start sits where Next was, so the second click of a
 * double-click (or a double tap) on Next would otherwise start a run.
 */
const START_GRACE_MS = 500;

/** One line of the review: what was chosen, and an Edit link back to the step that chose it. */
function ReviewRow({ label, editLabel, onEdit, disabled, children }: {
  label: string; editLabel: string; onEdit: () => void; disabled: boolean; children: React.ReactNode;
}) {
  return (
    <div role="group" aria-label={label}
         className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-4 gap-y-0.5 py-3 sm:grid-cols-[9.5rem_minmax(0,1fr)_auto]">
      <p className="text-sm text-muted">{label}</p>
      <div className="col-start-1 row-start-2 min-w-0 text-sm sm:col-start-2 sm:row-start-1">{children}</div>
      <Button variant="link" size="sm" aria-label={editLabel} onClick={onEdit} disabled={disabled}
              className="col-start-2 row-span-2 row-start-1 self-start sm:col-start-3 sm:row-span-1">
        Edit
      </Button>
    </div>
  );
}

export default function SetupPage() {
  const router = useRouter();
  const [health, setHealth] = useState<Health | null>(null);
  const [repos, setRepos] = useState<RepoInfo[]>([]);
  const [running, setRunning] = useState(false);
  const [repo, setRepo] = useState("");
  const [target, setTarget] = useState(80);
  const [opts, setOpts] = useState<Limits>(DEFAULTS);
  const [writeSummary, setWriteSummary] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [samples, setSamples] = useState<Sample[]>([]);
  const [tab, setTab] = useState<PickerTab>("samples");
  const [samplesFailed, setSamplesFailed] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [step, setStep] = useState(0);
  /** The furthest step reached; steps before it stay done (and clickable) when the user goes back. */
  const [furthest, setFurthest] = useState(0);
  /** Downloads and uploads in flight: their result replaces the selection, so step 1 waits for them. */
  const [pending, setPending] = useState(0);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const focusHeading = useRef(false);
  const startRef = useRef<HTMLButtonElement>(null);
  /** When the review step last opened, from `now()`. */
  const reviewSince = useRef(0);

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
      setLoaded(true);
      setTab(pickTab(own));
      setRepo((cur) => cur || own[0]?.path || list[0]?.path || "");
      const failed = [h, r].find((x) => x.status === "rejected");
      if (failed && failed.status === "rejected") setError((failed.reason as Error).message);
    });
  }, []);

  // Move focus to the new step's heading (it names the step and its position) after Back, Next, Skip or a jump,
  // but not on the first render.
  useEffect(() => {
    if (!focusHeading.current) return;
    focusHeading.current = false;
    headingRef.current?.focus();
  }, [step]);

  function goTo(i: number) {
    if (busy) return; // a run is being started: stay on the review
    if (i === REVIEW) reviewSince.current = now();
    focusHeading.current = true;
    setStep(i);
    setFurthest((f) => Math.max(f, i));
  }

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

  const onJobs = useCallback((jobs: JobSnapshot[]) => setRunning(jobs.some(isBusy)), []);

  /** Runs a download or upload, keeping Next disabled until its result is selected. */
  async function tracked<T>(work: () => Promise<T>): Promise<T> {
    setPending((n) => n + 1);
    try {
      return await work();
    } finally {
      setPending((n) => n - 1);
    }
  }

  const download = (id: string) => tracked(async () => {
    const info = await api.downloadSample(id);
    setRepo(info.path);
    try {
      await reload();
    } catch {
      // the clone succeeded; the lists refresh on the next Refresh
    }
  });

  const upload = (files: PickedFile[], name: string | undefined, onProgress: (fraction: number) => void) => tracked(async () => {
    const info = await api.uploadRepo(files, name, onProgress);
    setRepo(info.path);
    try {
      await reload();
    } catch {
      // the upload succeeded; the lists refresh on the next Refresh
    }
    return info;
  });

  const targetValid = Number.isFinite(target) && target >= 1 && target <= 100;
  const limitErrors = LIMITS.map((l) => limitError(opts[l.key], l));
  const valid = [!!selected && pending === 0, targetValid, limitErrors.every((e) => e === null), true];
  // Done: finished before and still valid, along with every step before it. The review is never done; once it has
  // been opened it stays reachable ("visited") while the steps before it are valid.
  const states: StepState[] = STEPS.map((_, i) => {
    if (i === step) return "current";
    if (!valid.slice(0, i + 1).every(Boolean)) return "upcoming";
    if (i === REVIEW) return furthest === REVIEW ? "visited" : "upcoming";
    return i < furthest ? "done" : "upcoming";
  });
  const changed = LIMITS.filter((l) => opts[l.key] !== DEFAULTS[l.key]);
  const anyChanged = changed.length > 0 || !writeSummary;

  const tokensLeft = typeof health?.tokens_left_today === "number" ? health.tokens_left_today : null;
  const minTokens = health?.min_daily_tokens_to_start ?? MIN_TOKENS_TO_START;
  const noBudget = tokensLeft != null && budgetBlocked(tokensLeft, minTokens);
  const canStart = !busy && !!selected && targetValid && valid[2] && !!health?.llm_configured && !running && !noBudget;

  async function start() {
    setBusy(true);
    setError(null);
    try {
      const { job_id } = await api.startJob({ repo_path: repo, target_coverage: target,
                                                options: { ...opts, write_summary: writeSummary } });
      router.push(`/jobs/${job_id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
      setBusy(false);
    }
  }

  // Only a press of Start itself submits, on the review step, once the grace period has passed. Enter in a field
  // (implicit submission has no Start submitter) and the tail of a double-click on Next do nothing.
  function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const submitter = (e.nativeEvent as SubmitEvent).submitter;
    if (step !== REVIEW || !canStart || !submitter || submitter !== startRef.current) return;
    if (now() - reviewSince.current < START_GRACE_MS) return;
    void start();
  }

  return (
    <div className="space-y-10">
      <header className={`${COLUMNS} items-end border-b border-border pb-8 sm:pb-10`}>
        <div className="min-w-0 max-w-2xl space-y-4">
          <h1 className={pageTitleClass}>Fill the gaps in a Go project’s tests</h1>
          <p className={`${ledeClass} max-w-[38rem]`}>
            Point it at a Go project and it writes unit tests with AI, keeping only the ones that pass and test code no other test reaches.
          </p>
          <p className="text-sm text-muted">
            New to this? <Link href="/how-it-works" className={inlineLinkClass}>How it works</Link> explains each step in plain words.
          </p>
        </div>
        <MeasuredRun />
      </header>

      <div className={COLUMNS}>
        <div className="min-w-0 max-w-2xl space-y-6">
          {health && !health.llm_configured && (
            <div role="alert" className={`${cardClass({ tone: "warn" })} border-l-4 text-sm`}>
              No Groq API key configured. Add <code className="font-mono">GROQ_API_KEY</code> to <code className="font-mono">.env</code> and restart <code className="font-mono">docker compose</code>.
            </div>
          )}

          <form onSubmit={submit} noValidate className={cardClass({ padded: false })}>
            <div className="border-b border-border px-4 pb-4 pt-4 sm:px-6 sm:pt-5">
              <WizardStepper label="Steps to start a run" steps={STEPS} current={step} states={states} onJump={goTo} />
            </div>

            <div className="space-y-5 px-4 py-5 sm:px-6 sm:py-6">
              <div className="space-y-1">
                <h2 ref={headingRef} tabIndex={-1} className={cx(sectionHeadingClass, "text-lg")}>
                  <span className="sr-only">Step {step + 1} of {STEPS.length}:</span>{" "}{STEPS[step]}
                </h2>
                <p className="max-w-prose text-sm leading-relaxed text-muted">{HINTS[step]}</p>
              </div>

              {step === 0 && (
                <>
                  <RepoPicker tab={tab} onTabChange={changeTab} samples={samples} folders={folders} value={repo} onChange={setRepo}
                              onDownload={download} onRefresh={reload} onUpload={upload} uploadLimits={health?.upload_limits}
                              hostDir={health?.host_repos_dir ?? null} samplesFailed={samplesFailed} loading={!loaded} />
                  <p className="text-sm text-muted">
                    {selected ? (
                      <>Selected: <span className="font-mono text-text">{selected.path}</span> · <span className="font-mono">{selected.module}</span> · {selected.go_files} source files</>
                    ) : "Nothing selected yet. Pick a repository above."}
                  </p>
                </>
              )}

              {step === 1 && (
                <div className="space-y-2">
                  <label htmlFor="target" className="sr-only">Target coverage</label>
                  <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
                    <input id="target" type="range" min={1} max={100} step={1} value={Math.min(100, Math.max(1, target || 1))}
                           onChange={(e) => setTarget(Number(e.target.value))} className="w-full max-w-64 accent-[var(--accent)]" />
                    <div className="flex items-center gap-2">
                      <input type="number" min={1} max={100} value={Number.isNaN(target) ? "" : target} aria-label="Target coverage percent"
                             aria-invalid={!targetValid} aria-describedby={targetValid ? undefined : "target-error"}
                             onChange={(e) => setTarget(e.target.value === "" ? NaN : Number(e.target.value))}
                             className={`w-20 ${inputClass}`} />
                      <span className="text-sm text-muted">%</span>
                    </div>
                  </div>
                  {!targetValid && <p id="target-error" className="text-xs text-danger">Enter a target between 1 and 100.</p>}
                </div>
              )}

              {step === 2 && (
                <div className="grid max-w-xl gap-x-6 gap-y-4 sm:grid-cols-2">
                  {anyChanged && (
                    <p id="skip-note" className="text-xs text-muted sm:col-span-2">
                      You changed {changed.length + (writeSummary ? 0 : 1) === 1 ? "an option" : "some options"}. Skip (use defaults) discards these changes.
                    </p>
                  )}
                  {LIMITS.map((l, i) => {
                    const err = limitErrors[i];
                    const id = `limit-${l.key}`;
                    return (
                      <div key={l.key} className="flex flex-col gap-1.5">
                        <label htmlFor={id} className="block text-xs leading-snug text-muted">{l.label}</label>
                        <input id={id} type="number" min={l.min} max={l.max} step={l.step}
                               value={Number.isNaN(opts[l.key]) ? "" : opts[l.key]}
                               aria-invalid={err !== null} aria-describedby={err ? `${id}-error` : undefined}
                               onChange={(e) => setOpts({ ...opts, [l.key]: e.target.value === "" ? NaN : Number(e.target.value) })}
                               className={`w-24 ${inputClass}`} />
                        {err && <p id={`${id}-error`} className="text-xs text-danger">{err}</p>}
                      </div>
                    );
                  })}
                  <div className="flex items-start gap-2.5 sm:col-span-2">
                    <input id="write-summary" type="checkbox" checked={writeSummary} onChange={(e) => setWriteSummary(e.target.checked)}
                           aria-describedby="write-summary-hint" className="mt-0.5 h-4 w-4 shrink-0 accent-[var(--accent)]" />
                    <div className="space-y-0.5">
                      <label htmlFor="write-summary" className="block text-sm">Write an AI summary at the end</label>
                      <p id="write-summary-hint" className="text-xs leading-snug text-muted">
                        One more Groq call writes a summary for stakeholders and one for engineering teams from the run&apos;s measured data.
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {step === REVIEW && (
                <>
                  <div className="divide-y divide-border border-y border-border">
                    <ReviewRow label="Repository" editLabel="Edit repository" onEdit={() => goTo(0)} disabled={busy}>
                      {selected && (
                        <>
                          <span className="block break-all font-mono text-text">{selected.path}</span>
                          <span className="block break-all font-mono text-xs text-muted">{selected.module} · {selected.go_files} source files</span>
                        </>
                      )}
                    </ReviewRow>
                    <ReviewRow label="Target" editLabel="Edit target" onEdit={() => goTo(1)} disabled={busy}>
                      <span className="font-mono">{target}%</span> <span className="text-muted">of the code tested</span>
                    </ReviewRow>
                    <ReviewRow label="Advanced options" editLabel="Edit advanced options" onEdit={() => goTo(2)} disabled={busy}>
                      {changed.length === 0 ? (
                        <span className="block text-muted">Defaults</span>
                      ) : (
                        <ul className="space-y-0.5">
                          {changed.map((l) => <li key={l.key}>{l.label}: <span className="font-mono">{opts[l.key]}</span></li>)}
                        </ul>
                      )}
                      <span className="mt-0.5 block">AI summary at the end: {writeSummary ? "on" : <span className="font-medium">off</span>}</span>
                    </ReviewRow>
                  </div>

                  <section aria-labelledby="next-heading" className="max-w-prose space-y-1.5 border-l-2 border-border pl-3 text-xs leading-relaxed text-muted">
                    <h3 id="next-heading" className="font-medium text-text">What happens next</h3>
                    <ul className="space-y-1">
                      <li>You land on the run page, which shows coverage and each step as it happens.</li>
                      <li>When it finishes, the new tests are saved in <code className="font-mono text-text">./output/&lt;run id&gt;/tests</code>.</li>
                      <li>For a plain explanation of what it does, read <Link href="/how-it-works" className={inlineLinkClass}>How it works</Link>.</li>
                    </ul>
                  </section>
                </>
              )}

              {error && <p role="alert" className="text-sm text-danger">{error}</p>}
            </div>

            <div className="space-y-2 rounded-b-md border-t border-border bg-surface px-4 py-3 max-sm:sticky max-sm:bottom-0 max-sm:z-10 max-sm:pb-[max(0.75rem,env(safe-area-inset-bottom))] sm:px-6 sm:py-4">
              {/* On phones the budget line takes its own row above Back and Start, so the sticky bar stays two rows. */}
              <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
                {step > 0 && <Button onClick={() => goTo(step - 1)} disabled={busy} className="max-sm:order-2">Back</Button>}
                {step === REVIEW && tokensLeft != null && (
                  <div className="max-sm:order-1 max-sm:w-full sm:ml-auto">
                    <TokenBudget left={tokensLeft} min={minTokens} id="budget-reason" />
                  </div>
                )}
                <div className="ml-auto flex items-center gap-3 max-sm:order-3">
                  {step === 2 && (
                    <Button variant="ghost" aria-describedby={anyChanged ? "skip-note" : undefined}
                            onClick={() => { setOpts(DEFAULTS); setWriteSummary(true); goTo(REVIEW); }}>
                      Skip (use defaults)
                    </Button>
                  )}
                  {step < REVIEW ? (
                    <Button key="next" variant="primary" disabled={!valid[step]} onClick={() => goTo(step + 1)}>Next</Button>
                  ) : (
                    // Its own key: reusing the Next button's element as a submit button would let the click that
                    // opens the review also submit the form.
                    <Button key="start" ref={startRef} type="submit" variant="primary" disabled={!canStart}
                            onClick={(e) => { if (e.detail > 1) e.preventDefault(); /* the 2nd+ click of a multi-click */ }}
                            aria-describedby={noBudget ? "budget-reason" : undefined}>
                      {busy ? "Starting…" : "Start"}
                    </Button>
                  )}
                </div>
              </div>
              {step === REVIEW && running && <p className="text-right text-xs text-muted">A run is in progress. Follow it in Run history.</p>}
            </div>
          </form>
        </div>
        <RunsPanel onJobs={onJobs} />
      </div>
    </div>
  );
}
