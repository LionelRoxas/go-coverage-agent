// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

export const metadata: Metadata = { title: "How it works" };

const WALKTHROUGH = "https://claude.ai/artifact/RxXGC2s7651iEFZDF3kYQ8";

const code = "font-mono text-[0.8125rem]";

type Step = { title: string; plain: string; tech: ReactNode };

// Plain text for someone who has never written a test; `tech` is the precise version (checked against backend/app).
const STEPS: Step[] = [
  {
    title: "Make a safe copy and measure",
    plain: "It works on a copy of your project, so your own files are never changed. It removes the copy’s existing tests, so it starts from zero. Then it measures how much of the code is checked.",
    tech: <>The repository is copied into a scratch workspace; by default every existing <code className={code}>_test.go</code> file is deleted from the copy. A seed test file in each package makes untested packages count too. The baseline comes from <code className={code}>go test -count=2 -covermode=set -coverprofile</code>: covered statements divided by all statements.</>,
  },
  {
    title: "Pick what to work on (no AI)",
    plain: "It finds the parts of the code that no test reaches yet. It picks a few at a time, biggest gaps first. This step follows fixed rules, so it uses no AI.",
    tech: <>A deterministic planner groups each file’s functions with uncovered statements, largest first, into one item of at most 8 functions or 100 uncovered statements, then takes up to 3 items per round. Functions that failed twice, or that are too large for one request, are skipped.</>,
  },
  {
    title: "Write the checks (AI)",
    plain: "It sends that code to an AI model, which writes new tests for the lines nothing checks yet. It also lists the tests that already exist, so the AI does not repeat them.",
    tech: <>The Writer calls Groq (<code className={code}>openai/gpt-oss-120b</code>, reasoning effort <code className={code}>medium</code>). The request holds the target functions with uncovered lines marked <code className={code}>{"// UNCOVERED"}</code>, the names of existing tests, and nearby code, capped at <code className={code}>MAX_PROMPT_TOKENS</code> (12,000). An answer too large to finish splits the item in half and retries.</>,
  },
  {
    title: "Try them out",
    plain: "It runs the new tests for real. They must build, pass twice in a row, and reach code that was not checked before. Tests that would use the network or start other programs are refused before they run.",
    tech: <>Five gates in order: a guard (standard-library or same-module imports only; no <code className={code}>os/exec</code>, <code className={code}>net</code>, <code className={code}>unsafe</code>, <code className={code}>syscall</code>, process starts or build tags), merge into the package’s test file, compile, <code className={code}>go vet</code>, then <code className={code}>go test -count=2</code> with a coverage profile. The covered statements must be a strict superset of the previous set: nothing lost, something gained.</>,
  },
  {
    title: "Keep, repair or undo",
    plain: "If only some new tests fail, it drops those and keeps the rest. Simple mistakes, like a missing import, are fixed without AI; harder ones go back to the AI with everything tried so far, up to 2 more times. If nothing works, the change is undone, so the project is never left broken.",
    tech: <>Prune: when only new tests fail, and not all of them, they are removed and the rest re-checked. Mechanical repairs (no model call, up to 3): stray characters in import paths cleaned, forgotten imports added, self-qualified names fixed, a duplicate <code className={code}>Test…</code> name renamed to <code className={code}>_2</code>, <code className={code}>_3</code>. The Fixer (<code className={code}>medium</code> effort) gets the full attempt history, including failing assertions and their observed values; up to 2 Fixer attempts. A Groq timeout is retried once at <code className={code}>low</code> effort. Otherwise the test file, <code className={code}>go.mod</code> and <code className={code}>go.sum</code> are rolled back to the snapshot taken before the attempt.</>,
  },
];

const STOPS = [
  { rule: "It reached the goal", why: "Coverage hit the target you set (80% unless you change it)." },
  { rule: "The last rounds added very little", why: "Two rounds in a row each added less than 1 percentage point." },
  { rule: "It ran out of rounds (20 by default)", why: "A round is one pass through steps 2 to 5." },
  { rule: "It used up its AI budget", why: "Each run, and each day, has a limit on how much AI it may use." },
  { rule: "Nothing is left that it can work on", why: "Every remaining gap was tried twice without success, or is too big to send in one go." },
];

const RESULTS = [
  { id: "stats", repo: "montanaflynn/stats", what: "a statistics library", from: 0, to: 80.75, label: "0% → 80.75%", rounds: 12, time: "about 4 minutes" },
  { id: "semver", repo: "Masterminds/semver", what: "a version-number library", from: 1.43, to: 84.59, label: "1.4% → 84.6%", rounds: 4, time: "about 2 minutes" },
];

const GLOSSARY = [
  { term: "Test", def: "A small program that runs a piece of the code and checks the answer is right." },
  { term: "Coverage", def: "The share of the code’s lines that at least one test runs." },
  { term: "AI model", def: "A language model on Groq’s servers that writes and fixes the tests. Nothing else in the loop uses AI." },
];

// Ten "lines of code", eight of them run by a test. Widths vary so it reads as code, not a progress bar.
const LINES = [72, 54, 88, 40, 64, 80, 30, 58, 76, 46];
const UNCOVERED = new Set([3, 7]);

const h2 = "text-xl font-semibold tracking-tight";

function Chevron() {
  return (
    <svg aria-hidden viewBox="0 0 16 16" className="h-3.5 w-3.5 transition-transform group-open:rotate-90 motion-reduce:transition-none" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="m6 3 5 5-5 5" />
    </svg>
  );
}

function CoverageLines() {
  return (
    <figure className="rounded-md border border-border bg-surface p-4 sm:p-5">
      <div role="img" aria-label="8 of 10 lines run by a test: 80% coverage" className="space-y-1.5">
        {LINES.map((w, i) => (
          <div key={i} className="flex items-center gap-3">
            <span aria-hidden className="w-4 text-right font-mono text-[11px] tabular-nums text-muted">{i + 1}</span>
            <span aria-hidden style={{ width: `${w}%` }}
                  className={UNCOVERED.has(i) ? "h-2.5 rounded-sm border border-dashed border-muted/70" : "h-2.5 rounded-sm bg-accent"} />
          </div>
        ))}
      </div>
      <figcaption className="mt-4 flex flex-wrap gap-x-5 gap-y-1 text-xs text-muted">
        <span className="flex items-center gap-1.5"><span aria-hidden className="h-2.5 w-4 rounded-sm bg-accent" />run by a test</span>
        <span className="flex items-center gap-1.5"><span aria-hidden className="h-2.5 w-4 rounded-sm border border-dashed border-muted/70" />not run by any test</span>
        <span className="font-medium text-text">8 of 10 = 80%</span>
      </figcaption>
    </figure>
  );
}

function RepeatBracket({ index }: { index: number }) {
  if (index === 0) return null;
  const shape = index === 1 ? "top-3 bottom-0 rounded-tr-md border-t-2"
    : index === STEPS.length - 1 ? "top-0 h-3 rounded-br-md border-b-2" : "inset-y-0";
  return (
    <span aria-hidden className={`absolute right-0 w-4 border-r-2 border-accent/60 ${shape}`}>
      {index === 1 && (
        <svg viewBox="0 0 8 12" className="absolute -left-1.5 -top-[7px] h-3 w-2 text-accent" fill="currentColor"><path d="M0 6 8 0v12z" /></svg>
      )}
    </span>
  );
}

export default function HowItWorksPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-16">
      <section className="space-y-4">
        <p className="text-base leading-relaxed text-muted sm:text-lg">
          Software teams write small automatic checks, called tests, that prove their code works.
        </p>
        <h1 className="text-2xl font-semibold leading-snug tracking-tight sm:text-[2rem] sm:leading-tight">
          This tool writes those checks for a Go project by itself, keeps only the ones that actually work, and stops when enough of the code is checked.
        </h1>
      </section>

      <section aria-labelledby="coverage-heading" className="grid items-center gap-6 sm:grid-cols-[1fr_15rem]">
        <div className="space-y-3">
          <h2 id="coverage-heading" className={h2}>What “coverage” means</h2>
          <p className="leading-relaxed text-muted">
            Coverage is the share of the code’s lines that the tests actually run. 80% means 8 in 10 lines are run by at least one test.
            The other 2 could be broken and no test would notice.
          </p>
        </div>
        <CoverageLines />
      </section>

      <section aria-labelledby="loop-heading" className="space-y-6">
        <div className="space-y-2">
          <h2 id="loop-heading" className={h2}>What happens in a run</h2>
          <p className="leading-relaxed text-muted">Five steps. Steps 2 to 5 form one round, and rounds repeat until it can stop.</p>
        </div>
        <ol>
          {STEPS.map((s, i) => (
            <li key={s.title} data-step={i + 1} className="relative flex gap-4 pr-8">
              <div aria-hidden className="relative flex w-7 shrink-0 flex-col items-center">
                <span className="flex h-7 w-7 items-center justify-center rounded-full border-2 border-accent text-sm font-semibold tabular-nums text-accent">{i + 1}</span>
                {i < STEPS.length - 1 && <span className="w-px flex-1 bg-border" />}
              </div>
              <div className="min-w-0 flex-1 space-y-1.5 pb-8 pt-0.5">
                <h3 className="font-semibold">{s.title}</h3>
                <p className="leading-relaxed text-muted">{s.plain}</p>
                <details className="group pt-1">
                  <summary className="inline-flex cursor-pointer list-none items-center gap-1 rounded-sm text-sm font-medium text-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent [&::-webkit-details-marker]:hidden">
                    <span>Technical detail</span><Chevron />
                  </summary>
                  <p className="mt-2 border-l-2 border-border pl-3 text-sm leading-relaxed text-muted">{s.tech}</p>
                </details>
              </div>
              <RepeatBracket index={i} />
            </li>
          ))}
        </ol>
        <p className="sr-only">After step 5 it starts again from step 2 with the new coverage, until it reaches the goal or a stop rule.</p>
        <p aria-hidden data-testid="repeat-connector" className="-mt-4 flex items-center justify-end gap-2 text-right text-sm text-muted">
          <svg viewBox="0 0 24 24" className="h-4 w-4 shrink-0 text-accent" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M3 12a9 9 0 0 1 15.5-6.2L21 8" /><path d="M21 3v5h-5" /><path d="M21 12a9 9 0 0 1-15.5 6.2L3 16" /><path d="M3 21v-5h5" />
          </svg>
          Back to step 2: repeat until the goal or a stop rule
        </p>
      </section>

      <div className="grid gap-12 md:grid-cols-2 md:gap-10">
        <section aria-labelledby="stop-heading" className="space-y-4">
          <h2 id="stop-heading" className={h2}>When does it stop?</h2>
          <ul className="space-y-3">
            {STOPS.map((s) => (
              <li key={s.rule} className="flex gap-3">
                <span aria-hidden className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
                <div>
                  <p className="font-medium">{s.rule}</p>
                  <p className="text-sm leading-relaxed text-muted">{s.why}</p>
                </div>
              </li>
            ))}
          </ul>
          <p className="text-sm text-muted">Whatever the reason, the tests it already kept stay.</p>
        </section>
        <section aria-labelledby="trust-heading" className="space-y-4">
          <h2 id="trust-heading" className={h2}>Can I trust the number?</h2>
          <ul className="space-y-3 leading-relaxed text-muted">
            <li>Only tests that pass, twice in a row, are kept.</li>
            <li>A failing test is dropped or undone, so it never counts toward the number.</li>
            <li>The result was also checked independently: for one stats run, the kept tests were re-run in a fresh copy of the project. They all passed and measured 80.5%.</li>
          </ul>
        </section>
      </div>

      <section aria-labelledby="result-heading" className="space-y-4">
        <div className="space-y-2">
          <h2 id="result-heading" className={h2}>Measured results</h2>
          <p className="leading-relaxed text-muted">Two real open-source Go projects, with their own tests removed first. Goal: 80%.</p>
        </div>
        <ul className="divide-y divide-border rounded-md border border-border bg-surface">
          {RESULTS.map((r) => (
            <li key={r.id} data-testid={`result-${r.id}`} className="space-y-3 p-4 sm:p-5">
              <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
                <p><span className="font-mono text-sm">{r.repo}</span> <span className="text-sm text-muted">({r.what})</span></p>
                <p className="font-mono text-lg font-semibold tabular-nums">{r.label}</p>
              </div>
              <div aria-hidden className="relative h-2 rounded-full bg-border">
                <span className="absolute inset-y-0 rounded-full bg-accent" style={{ left: `${r.from}%`, width: `${r.to - r.from}%` }} />
                <span className="absolute -inset-y-1 left-[80%] w-0.5 bg-text" title="80% goal" />
              </div>
              <p className="text-sm text-muted">{r.rounds} rounds, {r.time}. The goal line is at 80%.</p>
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="glossary-heading" className="space-y-4">
        <h2 id="glossary-heading" className={h2}>Words used on this page</h2>
        <dl className="grid gap-4 sm:grid-cols-3">
          {GLOSSARY.map((g) => (
            <div key={g.term} className="space-y-1">
              <dt className="font-medium">{g.term}</dt>
              <dd className="text-sm leading-relaxed text-muted">{g.def}</dd>
            </div>
          ))}
        </dl>
      </section>

      <footer className="flex flex-wrap items-center gap-x-6 gap-y-3 border-t border-border pt-6">
        <Link href="/" className="inline-block rounded-sm bg-accent px-5 py-2 text-sm font-medium text-on-accent">Start a run →</Link>
        <a href={WALKTHROUGH} target="_blank" rel="noopener noreferrer" className="text-sm text-accent underline-offset-4 hover:underline">Full walkthrough <span aria-hidden>↗</span></a>
      </footer>
    </div>
  );
}
