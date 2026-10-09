// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = { title: "How it works" };

const WALKTHROUGH = "https://claude.ai/artifact/RxXGC2s7651iEFZDF3kYQ8";

const STEPS = [
  { title: "Copy & measure", body: <>Copies the repo into a scratch workspace and deletes existing tests. Measures baseline coverage with <code className="font-mono">go test -cover</code>.</> },
  { title: "Plan (no AI)", body: <>Ranks functions by uncovered statements. Picks up to 3 targets per iteration, each at most 8 functions or 100 statements.</> },
  { title: "Write (Groq)", body: <>The model writes table-driven Go tests from a compact context of the target code.</> },
  { title: "Validate (5 gates)", body: <>Import guard, merge, compile, <code className="font-mono">go vet</code>, then tests pass twice with coverage.</> },
  { title: "Keep or roll back", body: <>Kept only if tests pass and covered blocks are a strict superset. Otherwise one mechanical repair or LLM fix, else rolled back to the snapshot.</> },
];

const STOPS = ["Target reached", "Gains become marginal", "Iteration limit (20 by default)", "Token budget used", "No remaining targets"];

const RESULT = [
  { label: "Coverage", value: "0% → 80.75%" },
  { label: "Iterations", value: "12" },
  { label: "Time", value: "about 4 min" },
  { label: "Model errors", value: "0" },
];

const h2 = "text-lg font-semibold tracking-tight";

export default function HowItWorksPage() {
  return (
    <div className="space-y-14">
      <section className="space-y-4">
        <h1 className="max-w-3xl text-2xl font-semibold leading-snug tracking-tight sm:text-3xl">
          Give it a Go repository and a target. It writes unit tests with an LLM, keeps only the ones that pass and add coverage, and stops at the target.
        </h1>
        <a href={WALKTHROUGH} target="_blank" rel="noopener noreferrer" className="inline-block text-sm text-accent underline-offset-4 hover:underline">Full walkthrough <span aria-hidden>↗</span></a>
      </section>

      <section aria-labelledby="loop-heading" className="space-y-5">
        <h2 id="loop-heading" className={h2}>The loop</h2>
        <ol className="grid gap-3 lg:grid-cols-5">
          {STEPS.map((s, i) => (
            <li key={s.title} className="flex gap-3 rounded-sm border border-border bg-surface p-4 lg:flex-col lg:gap-2">
              <span aria-hidden className="font-mono text-sm font-semibold tabular-nums text-accent">{i + 1}</span>
              <div className="space-y-1.5">
                <h3 className="text-sm font-semibold">{s.title}</h3>
                <p className="text-sm leading-relaxed text-muted">{s.body}</p>
              </div>
            </li>
          ))}
        </ol>
        <p className="sr-only">Then it repeats from step 2 with the new coverage, until the target or a stop rule is reached.</p>
        <div aria-hidden data-testid="repeat-connector" className="hidden lg:block">
          <div className="relative h-10">
            <div className="absolute inset-y-0 rounded-b-md border-x-2 border-b-2 border-accent/60"
                 style={{ left: "calc((100% - 48px) / 5 * 1.5 + 12px)", right: "calc((100% - 48px) / 10)" }}>
              <svg viewBox="0 0 12 8" className="absolute -left-[7px] -top-1 h-2 w-3 text-accent" fill="currentColor"><path d="M6 0 12 8H0z" /></svg>
              <span className="absolute -bottom-2.5 left-1/2 -translate-x-1/2 whitespace-nowrap bg-bg px-3 text-xs text-muted">repeat until the target or a stop rule</span>
            </div>
          </div>
        </div>
        <p aria-hidden data-testid="repeat-connector-narrow" className="flex items-center gap-2 border-l-2 border-accent/60 pl-3 text-sm text-muted lg:hidden">
          <svg viewBox="0 0 24 24" className="h-4 w-4 shrink-0 text-accent" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M3 12a9 9 0 0 1 15.5-6.2L21 8" /><path d="M21 3v5h-5" /><path d="M21 12a9 9 0 0 1-15.5 6.2L3 16" /><path d="M3 21v-5h5" />
          </svg>
          Back to Plan (step 2) until the target or a stop rule
        </p>
      </section>

      <div className="grid gap-10 md:grid-cols-2">
        <section className="space-y-3">
          <h2 className={h2}>How the percentage is calculated</h2>
          <p className="text-sm leading-relaxed text-muted">
            Covered statements divided by total statements, from Go&apos;s coverage profile. A seed file makes every package count, even untested ones.
          </p>
          <p className="text-sm leading-relaxed text-muted">Failing or flaky tests are never kept, so they never count.</p>
        </section>
        <section className="space-y-3">
          <h2 className={h2}>When it stops</h2>
          <ul className="space-y-1.5 text-sm">
            {STOPS.map((s) => (
              <li key={s} className="flex items-center gap-2"><span aria-hidden className="h-1.5 w-1.5 rounded-full bg-accent" />{s}</li>
            ))}
          </ul>
        </section>
      </div>

      <section aria-labelledby="result-heading" className="space-y-4">
        <h2 id="result-heading" className={h2}>Measured result</h2>
        <p className="text-sm text-muted">
          <span className="font-mono">montanaflynn/stats</span> with its tests deleted.
        </p>
        <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-sm border border-border bg-border sm:grid-cols-4">
          {RESULT.map((r) => (
            <div key={r.label} className="bg-surface p-4">
              <dt className="text-xs text-muted">{r.label}</dt>
              <dd className="mt-1 font-mono text-lg font-semibold tabular-nums">{r.value}</dd>
            </div>
          ))}
        </dl>
      </section>

      <footer className="border-t border-border pt-6">
        <Link href="/" className="inline-block rounded-sm bg-accent px-5 py-2 text-sm font-medium text-on-accent">Start a run →</Link>
      </footer>
    </div>
  );
}
