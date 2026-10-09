// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
import type { Metadata } from "next";
import Link from "next/link";
import { type SectionId, walkthroughHref } from "../walkthrough/sections";

export const metadata: Metadata = { title: "How it works" };

type Step = { title: string; plain: string; more: SectionId };

// Plain text for someone who has never written a test; the precise version of each step is on the Walkthrough page.
const STEPS: Step[] = [
  {
    title: "Make a safe copy and measure",
    plain: "It works on a copy of your project, so your own files are never changed. It removes the copy’s existing tests, so it starts from zero and the result shows only what this tool wrote. Then it measures how much of the code is checked.",
    more: "prepare",
  },
  {
    title: "Pick what to work on (no AI)",
    plain: "It finds the parts of the code that no test reaches yet. It picks a few at a time, biggest gaps first. This step follows fixed rules, so it uses no AI.",
    more: "plan",
  },
  {
    title: "Write the checks (AI)",
    plain: "It sends that code to an AI model, which writes new tests for the lines nothing checks yet. It also lists the tests that already exist, so the AI does not repeat them.",
    more: "write",
  },
  {
    title: "Try them out",
    plain: "It runs the new tests for real. They must be valid code the computer accepts, pass twice in a row, and run code that no test ran before. Tests that would use the network or start other programs are refused before they run.",
    more: "validate",
  },
  {
    title: "Keep, repair or undo",
    plain: "Tests that fail are dropped if the rest still work. Small slips are fixed automatically without AI; harder ones go back to the AI, with everything tried so far, for up to 2 more tries. If nothing works, the change is undone, so the project is never left broken.",
    more: "keep",
  },
];

const STOPS = [
  { rule: "It reached the goal", why: "Coverage hit the target you set (80% unless you change it)." },
  { rule: "The last rounds added very little", why: "Two rounds in a row each raised coverage by less than 1% (for example, from 60% to 60.5%)." },
  { rule: "It ran out of rounds (20 by default)", why: "A round is one pass through steps 2 to 5." },
  { rule: "It used up its AI budget", why: "Each run, and each day, has a limit on how much AI it may use." },
  { rule: "Nothing is left that it can work on", why: "Every remaining gap was tried twice without success, or is too big to send in one go." },
];

const RESULTS = [
  { id: "stats", repo: "montanaflynn/stats", what: "Ready-made code for statistics", from: 0, to: 80.75, label: "0% → 80.75%", rounds: 12, time: "about 4 minutes" },
  { id: "semver", repo: "Masterminds/semver", what: "Ready-made code for comparing version numbers", from: 1.43, to: 84.59, label: "1.4% → 84.6%", rounds: 4, time: "about 2 minutes" },
];

// Ten "lines of code", eight of them run by a test. Widths vary so it reads as code, not a progress bar.
const LINES = [72, 54, 88, 40, 64, 80, 30, 58, 76, 46];
const UNCOVERED = new Set([3, 7]);

const h2 = "text-xl font-semibold tracking-tight";

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
    : index === STEPS.length - 1 ? "inset-y-0 rounded-br-md border-b-2" : "inset-y-0";
  return (
    <span aria-hidden className={`absolute right-0 w-4 border-r-2 border-accent/60 lg:hidden ${shape}`}>
      {index === 1 && (
        <svg viewBox="0 0 8 12" className="absolute -left-1.5 -top-[7px] h-3 w-2 text-accent" fill="currentColor"><path d="M0 6 8 0v12z" /></svg>
      )}
    </span>
  );
}

export default function HowItWorksPage() {
  return (
    <div className="space-y-16 [&>*:not(#loop)]:mx-auto [&>*:not(#loop)]:max-w-3xl">
      <section className="space-y-4">
        <p className="text-base leading-relaxed text-muted sm:text-lg">
          Software teams write small automatic checks, called tests, that prove their code works.
        </p>
        <h1 className="text-2xl font-semibold leading-snug tracking-tight sm:text-[2rem] sm:leading-tight">
          This tool writes those checks for a project written in Go (a programming language) by itself, keeps only the ones that actually work, and stops when enough of the code is checked.
        </h1>
      </section>

      <section aria-labelledby="coverage-heading" className="grid items-center gap-6 sm:grid-cols-[1fr_15rem]">
        <div className="space-y-3">
          <h2 id="coverage-heading" className={h2}>What “coverage” means</h2>
          <p className="leading-relaxed text-muted">
            Coverage is the share of the code’s lines that the tests actually run. 80% means 8 in 10 lines are run by at least one test.
            The other 2 could be broken and no test would notice. Code with no tests at all still counts in the total, so nothing is hidden.
          </p>
        </div>
        <CoverageLines />
      </section>

      <section id="loop" aria-labelledby="loop-heading" className="space-y-6">
        <div className="mx-auto max-w-3xl space-y-2">
          <h2 id="loop-heading" className={h2}>What happens in a run</h2>
          <p className="leading-relaxed text-muted">Five steps. Steps 2 to 5 form one round, and rounds repeat until it can stop.</p>
        </div>
        <div className="mx-auto max-w-3xl lg:max-w-none">
          <div aria-hidden data-testid="loop-phases" className="mb-1 hidden grid-cols-5 items-end gap-3 text-xs lg:grid">
            <div className="space-y-1.5 text-muted">
              <p className="text-center">Once at the start</p>
              <div className="mx-4 h-2 rounded-t-sm border-x-2 border-t-2 border-border" />
            </div>
            <div className="col-span-4 space-y-4">
              <p className="text-center font-medium text-accent">Each round</p>
              <div aria-hidden data-testid="repeat-connector" className="relative h-7">
                <div className="absolute inset-y-0 rounded-t-md border-x-2 border-t-2 border-accent/60"
                     style={{ left: "calc((100% - 2.25rem) / 8)", right: "calc((100% - 2.25rem) / 8)" }}>
                  <svg viewBox="0 0 12 8" className="absolute -bottom-1 -left-[7px] h-2 w-3 text-accent" fill="currentColor"><path d="M0 0h12L6 8z" /></svg>
                  <span className="absolute -top-2.5 left-1/2 -translate-x-1/2 whitespace-nowrap bg-bg px-3 text-sm leading-5 text-muted">repeat until the goal or a stop rule</span>
                </div>
              </div>
            </div>
          </div>
          <ol className="lg:grid lg:grid-cols-5 lg:gap-x-3">
            {STEPS.map((s, i) => {
              const card = i === 0 ? "lg:border-dashed lg:border-border" : "lg:border-border lg:bg-surface";
              return (
                <li key={s.title} data-step={i + 1}
                    className="relative grid grid-cols-[1.75rem_minmax(0,1fr)] gap-x-4 pr-8 lg:row-span-2 lg:grid-cols-1 lg:grid-rows-subgrid lg:pr-0">
                  <div aria-hidden className="relative row-span-2 flex flex-col items-center lg:hidden">
                    <span className="flex h-7 w-7 items-center justify-center rounded-full border-2 border-accent text-sm font-semibold tabular-nums text-accent">{i + 1}</span>
                    {i < STEPS.length - 1 && <span className="w-px flex-1 bg-border" />}
                  </div>
                  <div className={`min-w-0 space-y-1.5 pt-0.5 lg:rounded-t-md lg:border lg:border-b-0 lg:px-4 lg:pt-4 ${card}`}>
                    <span aria-hidden className="mb-3 hidden h-7 w-7 items-center justify-center rounded-full border-2 border-accent text-sm font-semibold tabular-nums text-accent lg:flex">{i + 1}</span>
                    <h3 className="font-semibold lg:text-[0.9375rem] lg:leading-snug">{s.title}</h3>
                    <p className="leading-relaxed text-muted lg:text-sm">{s.plain}</p>
                  </div>
                  {/* Row 2 of the card's subgrid, so every Read more link sits at the same height. */}
                  <div className={`min-w-0 pb-8 pt-2 lg:rounded-b-md lg:border lg:border-t-0 lg:px-4 lg:pb-4 lg:pt-3 ${card}`}>
                    <Link href={walkthroughHref(s.more)}
                          className="rounded-sm text-sm font-medium text-accent underline-offset-4 hover:underline">
                      Read more<span className="sr-only">: {s.title}</span> <span aria-hidden>→</span>
                    </Link>
                  </div>
                  <RepeatBracket index={i} />
                </li>
              );
            })}
          </ol>
          <p className="sr-only">Step 1 happens once, at the start. After step 5 it starts again from step 2 with the new coverage, until it reaches the goal or a stop rule.</p>
          <p aria-hidden data-testid="repeat-connector-narrow" className="mt-2 flex items-center justify-end gap-2 text-right text-sm text-muted lg:hidden">
            <svg viewBox="0 0 24 24" className="h-4 w-4 shrink-0 text-accent" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M3 12a9 9 0 0 1 15.5-6.2L21 8" /><path d="M21 3v5h-5" /><path d="M21 12a9 9 0 0 1-15.5 6.2L3 16" /><path d="M3 21v-5h5" />
            </svg>
            Back to step 2: repeat until the goal or a stop rule
          </p>
        </div>
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
            <li>A new test also has to run at least one piece of code that no earlier test ran. One that only repeats what is already checked adds nothing, so it isn’t kept.</li>
            <li>A failing test is dropped or undone, so it never counts toward the number.</li>
            <li>The result was also checked independently: an earlier stats run (which reached 80.51%) had its kept tests re-run in a fresh copy of the project. They all passed and measured 80.5%.</li>
          </ul>
        </section>
      </div>

      <section aria-labelledby="result-heading" className="space-y-4">
        <div className="space-y-2">
          <h2 id="result-heading" className={h2}>Measured results</h2>
          <p className="leading-relaxed text-muted">Two real open-source Go projects, with their own tests removed first, so they start at or near 0%. Goal: 80%.</p>
        </div>
        <ul className="divide-y divide-border rounded-md border border-border bg-surface">
          {RESULTS.map((r) => (
            <li key={r.id} data-testid={`result-${r.id}`} className="grid gap-x-6 gap-y-2 p-4 sm:grid-cols-[minmax(0,1fr)_12rem] sm:items-center">
              <div className="min-w-0">
                <p className="font-mono text-sm">{r.repo}</p>
                <p className="text-sm text-muted">{r.what}: {r.rounds} rounds, {r.time}</p>
              </div>
              <div className="space-y-1.5">
                <p className="font-mono font-semibold tabular-nums sm:text-right">{r.label}</p>
                <div aria-hidden className="relative h-1.5 rounded-full bg-border">
                  <span className="absolute inset-y-0 rounded-full bg-accent" style={{ left: `${r.from}%`, width: `${r.to - r.from}%` }} />
                  <span className="absolute -inset-y-1 left-[80%] w-0.5 bg-text" title="80% goal" />
                </div>
              </div>
            </li>
          ))}
        </ul>
      </section>

      <footer className="flex flex-wrap items-center gap-x-6 gap-y-3 border-t border-border pt-6">
        <Link href="/" className="inline-block rounded-sm bg-accent px-5 py-2 text-sm font-medium text-on-accent">Start a run →</Link>
        <Link href="/walkthrough" className="text-sm font-medium text-accent underline-offset-4 hover:underline">Read the full walkthrough →</Link>
      </footer>
    </div>
  );
}
