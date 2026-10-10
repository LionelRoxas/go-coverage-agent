// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";
import { actionLinkClass, buttonClass, cardClass, codeBlockClass, inlineLinkClass, PageHeader, readingHeadingClass } from "@/components/ui";
import { type SectionId, SECTIONS } from "./sections";

export const metadata: Metadata = {
  title: "Walkthrough",
  description: "Every step of one Go Coverage Agent run, in the order the code runs it, with the files and events behind it.",
};

// Every fact on this page was checked against backend/app, tools/gohelper and the measured runs in ./output.

function C({ children }: { children: ReactNode }) {
  return <code className="rounded-sm bg-surface px-1 py-px font-mono text-[0.8125rem] ring-1 ring-border">{children}</code>;
}

function Pre({ children, caption }: { children: string; caption?: string }) {
  return (
    <figure className="min-w-0 space-y-1.5">
      <pre className={codeBlockClass("md")}>{children}</pre>
      {caption && <figcaption className="text-xs text-muted">{caption}</figcaption>}
    </figure>
  );
}

function H3({ children }: { children: ReactNode }) {
  return <h3 className="pt-2 font-semibold">{children}</h3>;
}

/** Where to look in the code, and the events the browser receives for this part of the run. */
function Where({ code, events }: { code: string[]; events?: string[] }) {
  const row = (label: string, items: string[]) => (
    <div className="flex flex-wrap gap-x-2 gap-y-1">
      <dt className="w-14 shrink-0 text-muted">{label}</dt>
      <dd className="flex min-w-0 flex-wrap gap-x-3 gap-y-1 font-mono text-xs leading-5">{items.map((i) => <span key={i}>{i}</span>)}</dd>
    </div>
  );
  return (
    <dl className="space-y-1 border-t border-dashed border-border pt-3 text-xs">
      {row("Code", code)}
      {events && row("Events", events)}
    </dl>
  );
}

const ROUND = SECTIONS.filter((s) => s.part === "round");

function Section({ id, children }: { id: SectionId; children: ReactNode }) {
  const s = SECTIONS.find((x) => x.id === id)!;
  const step = ROUND.findIndex((x) => x.id === id);
  return (
    <section id={id} aria-labelledby={`${id}-heading`} className="scroll-mt-20 space-y-4 border-t border-border pt-10">
      <div className="space-y-1">
        {step >= 0 && <p className="text-sm font-medium text-accent">Each round, part {step + 1} of {ROUND.length}</p>}
        <h2 id={`${id}-heading`} className={readingHeadingClass}>{s.title}</h2>
      </div>
      {children}
    </section>
  );
}

function LoopIcon() {
  return (
    <svg aria-hidden viewBox="0 0 24 24" className="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 12a9 9 0 0 1 15.5-6.2L21 8" /><path d="M21 3v5h-5" /><path d="M21 12a9 9 0 0 1-15.5 6.2L3 16" /><path d="M3 21v-5h5" />
    </svg>
  );
}

const tocLink = "block rounded-sm py-1 text-sm leading-snug text-muted underline-offset-4 hover:text-text hover:underline";

function TocItem({ id, title }: { id: string; title: string }) {
  return (
    <li className="relative pl-4">
      <span aria-hidden className="absolute -left-[5px] top-[0.7rem] h-2 w-2 rounded-full border-2 border-muted/70 bg-bg" />
      <a href={`#${id}`} className={tocLink}>{title}</a>
    </li>
  );
}

/** The table of contents drawn as the run itself: a rail through the steps that turns green for the repeated round. */
function Toc() {
  const before = SECTIONS.filter((s) => s.part === "run" && s.id !== "stop");
  const stop = SECTIONS.find((s) => s.id === "stop")!;
  return (
    <nav aria-label="On this page" className={`${cardClass()} sm:grid sm:grid-cols-2 sm:gap-6 lg:block lg:border-0 lg:bg-transparent lg:p-0`}>
      <div className="space-y-2">
        <p className="text-sm font-semibold">The run, in order</p>
        <ol className="ml-1 border-l-2 border-border">
          {before.map((s) => <TocItem key={s.id} id={s.id} title={s.title} />)}
          <li className="-ml-0.5 my-1 border-l-2 border-accent bg-accent/5 py-1.5 pr-2">
            <div role="group" aria-labelledby="toc-round">
              <p id="toc-round" className="flex items-center gap-1.5 pl-4 text-xs font-medium text-accent"><LoopIcon />Each round</p>
              <ol className="ml-4">
                {ROUND.map((s) => (
                  <li key={s.id}><a href={`#${s.id}`} className={tocLink}>{s.title}</a></li>
                ))}
              </ol>
            </div>
          </li>
          <TocItem id={stop.id} title={stop.title} />
        </ol>
      </div>
      <div className="mt-5 space-y-2 sm:mt-0 lg:mt-7">
        <p className="text-sm font-semibold">Reference</p>
        <ul className="ml-1 pl-[1.125rem]">
          {SECTIONS.filter((s) => s.part === "ref").map((s) => (
            <li key={s.id}><a href={`#${s.id}`} className={tocLink}>{s.title}</a></li>
          ))}
        </ul>
      </div>
    </nav>
  );
}

type Gate = { id: string; name: string; what: ReactNode; rejects?: string };

const GATES: Gate[] = [
  { id: "imports", name: "Clean import paths", what: <>Spaces, quotes and backslashes around each import path are stripped from every answer. No AI; when it changes something it is reported as a <C>mechanical_repair</C> with repair number 0. It never rejects.</> },
  { id: "guard", name: "Safety guard", what: <>Imports must be valid paths from the standard library or this module. <C>os/exec</C>, <C>net</C> and <C>net/…</C>, <C>crypto/tls</C>, <C>log/syslog</C>, <C>golang.org/x/net/…</C>, <C>syscall</C>, <C>unsafe</C>, <C>plugin</C>, <C>runtime/cgo</C>, <C>runtime/debug</C> and <C>C</C> are refused. The code may not contain a package or import clause, <C>func init</C> or <C>TestMain</C>, <C>StartProcess</C>, <C>/proc/</C>, a string containing <C>environ</C>, <C>{'filepath.Join("/", …)'}</C>, a file operation on an absolute path, build tags, <C>{"//go:"}</C> directives or <C>#cgo</C>; it must hold at least one <C>TestXxx</C> and stay under 40,000 bytes. It also refuses converting <C>math.NaN()</C> or <C>math.Inf()</C> to an integer type, which gives different results on x86 and ARM. Comments and strings are blanked before the keyword checks.</>, rejects: "guard_rejected" },
  { id: "merge", name: "Merge", what: <><C>gohelper merge</C> appends the new declarations to <C>&lt;source&gt;_test.go</C> (creating it if needed). It never edits existing declarations, refuses a duplicate name, de-duplicates imports, drops unused ones and runs gofmt.</>, rejects: "compile_error" },
  { id: "compile", name: "Compile", what: <><C>go test -count=1 -run=^$</C> builds the test binaries without running anything.</>, rejects: "compile_error" },
  { id: "vet", name: "Vet", what: <><C>go vet</C> must be clean.</>, rejects: "vet_error" },
  { id: "asserts", name: "Assertions", what: <><C>gohelper asserts</C>: every new <C>TestXxx</C> must call <C>t.Error*</C>/<C>t.Fatal*</C> (also in its <C>t.Run</C> subtests) or pass <C>t</C> to a helper. Tests that check nothing are pruned when others remain (<C>tests_pruned</C> with reason <C>no_assertions</C>, shown as “Removed the test without assertions”); otherwise the Fixer is told to assert.</>, rejects: "no_assertions" },
  { id: "test", name: "Run twice", what: <><C>go test -count=2 -covermode=set -coverprofile -timeout=60s</C>. Running twice catches flaky tests. Failing test names are read from the <C>--- FAIL</C> lines.</>, rejects: "test_failure" },
  { id: "coverage", name: "Coverage gain", what: <>The set of covered blocks after must be a strict superset of the set before: something gained, nothing lost.</>, rejects: "no_gain" },
];

function GateChain() {
  return (
    <ol data-testid="gate-chain" className="relative space-y-0">
      {GATES.map((g, i) => (
        <li key={g.id} data-gate={g.id} className="relative grid grid-cols-[1.75rem_minmax(0,1fr)] gap-x-3 pb-5">
          <span aria-hidden className="absolute bottom-0 left-[0.8125rem] top-7 w-0.5 bg-border" />
          <span aria-hidden className="relative z-10 flex h-7 w-7 items-center justify-center rounded-full border-2 border-border bg-bg font-mono text-xs font-semibold tabular-nums">{i + 1}</span>
          <div className="min-w-0 space-y-1 pt-0.5">
            <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-0.5">
              <p className="font-semibold">{g.name}</p>
              {g.rejects && <p className="font-mono text-xs text-danger"><span className="sr-only">Rejected as </span>✕ {g.rejects}</p>}
            </div>
            <p className="text-sm leading-relaxed text-muted">{g.what}</p>
          </div>
        </li>
      ))}
      <li aria-hidden className="grid grid-cols-[1.75rem_minmax(0,1fr)] gap-x-3">
        <span className="flex h-7 w-7 items-center justify-center rounded-full bg-accent text-on-accent">
          <svg viewBox="0 0 16 16" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"><path d="m3.5 8.5 3 3 6-7" /></svg>
        </span>
        <p className="pt-1 font-mono text-sm font-semibold text-accent">accepted</p>
      </li>
    </ol>
  );
}

/** A two-column table that stacks on narrow screens: `term` is code (a reason, a result kind). */
function Rules({ rows, head }: { rows: { term: ReactNode; text: ReactNode }[]; head: [string, string] }) {
  return (
    <table className="w-full text-left text-sm">
      <thead className="sr-only"><tr><th scope="col">{head[0]}</th><th scope="col">{head[1]}</th></tr></thead>
      <tbody className="divide-y divide-border border-y border-border">
        {rows.map((r, i) => (
          <tr key={i} className="block py-2.5 sm:table-row">
            <th scope="row" className="block pb-1 align-top font-normal sm:table-cell sm:w-48 sm:py-2.5 sm:pr-4">{r.term}</th>
            <td className="block align-top leading-relaxed text-muted sm:table-cell sm:py-2.5">{r.text}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

const m = "font-mono text-[0.8125rem]";

const KEEP = [
  { term: <span className={`${m} text-accent`}>accepted</span>, text: <>The tests stay and coverage goes up: <C>candidate_accepted</C> with the test names, the new percentage and the gain. The target is checked right away.</> },
  { term: <span className={m}>test_failure, some new tests</span>, text: <>When only new tests failed, and not all of them, <C>gohelper prune</C> removes just those (and any import they alone used); the rest go through compile, vet, run and coverage again. Free: <C>tests_pruned</C>.</> },
  { term: <span className={m}>compile_error, fixable</span>, text: <>Mechanical repair, no AI, up to 3 per target: add a forgotten standard-library import; drop the package’s own qualifier (<C>stats.Mean</C> becomes <C>Mean</C>); rename a duplicate <C>Test…</C>, <C>Benchmark…</C> or <C>Fuzz…</C> to <C>_2</C>, <C>_3</C>. Example functions are left to the Fixer: <C>ExampleX_2</C> is a malformed name for go vet, and an Example without <C>{"// Output:"}</C> never runs. The snapshot is restored and the repaired code re-validated: <C>mechanical_repair</C>.</> },
  { term: <span className={m}>anything else</span>, text: <>The Fixer: the snapshot is restored and Groq (<C>medium</C> effort) gets the rejected code, the validator output, the imports and test plan it declared, and the history of every earlier check of this target. Up to 2 attempts (<C>max_fix_attempts</C>, 0 to 4), each re-validated through every gate: <C>fix_attempt</C>.</> },
  { term: <span className={`${m} text-danger`}>still failing</span>, text: <>The snapshot is restored exactly (test file, <C>go.mod</C>, <C>go.sum</C>) and each function in the target counts one failure. After 2 failures the planner skips it: <C>candidate_rejected</C> with the reason.</> },
];

const STOP_RULES = [
  { term: <span className={m}>target_reached</span>, text: <>Coverage is at or above the target. Checked before each round and after every target, accepted or not, not only at the end of a round.</> },
  { term: <span className={m}>marginal_gains</span>, text: <>The last 2 rounds (<C>patience</C>) each gained less than 1 percentage point (<C>min_gain</C>).</> },
  { term: <span className={m}>max_iterations</span>, text: <>20 rounds by default (<C>max_iterations</C>, 1 to 30). A round in which every target met a Groq outage does not count.</> },
  { term: <span className={m}>no_remaining_targets</span>, text: <>Every function with uncovered statements has failed twice or is too large for one request. Groq outages do not count as failures.</> },
  { term: <span className={m}>budget_exhausted</span>, text: <>The job’s own budget (<C>max_llm_tokens</C>, 1,000,000 by default) is spent; or the app’s daily cap <C>DAILY_TOKEN_BUDGET</C> (2,000,000 by default, reset at 00:00 UTC) has less than the 16,000 a call reserves; or Groq asks to wait more than 90 s, which usually means its own daily cap.</> },
  { term: <span className={m}>cancelled</span>, text: <>You pressed Cancel. Running commands, Groq requests and rate-limit pauses stop within seconds.</> },
  { term: <span className={m}>llm_unavailable</span>, text: <>Groq stayed unreachable (timeouts, 5xx errors, connection errors) for 10 minutes in a row (<C>LLM_UNAVAILABLE_AFTER_S</C>). Such failures never count against a function: the item is deferred (<C>candidate_deferred</C>, shown as “Retried later (Groq unreachable)”), the run waits (15 s, doubling up to 2 minutes) and plans it again later. The automatic AI summary is then skipped. Tests kept so far are saved.</> },
];

const MEASURED = [
  { repo: "montanaflynn/stats, goal 80%", job: "e2de1ca387cb", cov: "0.0% → 81.07%", rounds: 11, time: "310 s", tokens: "175,023", kept: "31 / 0" },
  { repo: "montanaflynn/stats, goal 100%, up to 30 rounds, min gain 0.5", job: "0e1f8bf7442a", cov: "0.0% → 100.0%", rounds: 22, time: "612 s", tokens: "403,322", kept: "64 / 1" },
  { repo: "google/btree, goal 100%, min gain 0.5", job: "80a576a4d3ad", cov: "0.0% → 87.09%", rounds: 11, time: "350 s", tokens: "306,562", kept: "6 / 5" },
  { repo: "montanaflynn/stats, goal 80%", job: "89eb53b5907e", cov: "0.0% → 80.51%", rounds: 15, time: "287 s", tokens: "184,926", kept: "41 / 4" },
];

const GLOSSARY: { term: string; def: ReactNode }[] = [
  { term: "Test", def: "A small program that runs a piece of the code and checks the answer is right. In Go, a function named TestXxx in a _test.go file." },
  { term: "Coverage", def: "Covered statements divided by all statements in the measured packages, as Go’s coverage profile reports them." },
  { term: "Block", def: "A run of statements that always execute together. The coverage profile has one line per block." },
  { term: "Round", def: "One pass of plan, write, validate and keep, repair or undo. Called an iteration in the code, the events and the API." },
  { term: "Target", def: "One planned unit of work: up to 5 functions from one source file and at most 100 uncovered statements, unless one function alone is bigger." },
  { term: "Candidate", def: "The tests the model wrote for one target, as they go through the gates." },
  { term: "Writer, Fixer and Summarizer", def: "The three AI roles. The Writer writes new tests; the Fixer repairs a rejected candidate; after the run, the Summarizer writes the AI summary. Nothing else uses AI." },
  { term: "AI model", def: <>An AI that writes text and code, run by the company Groq: <C>openai/gpt-oss-120b</C>.</> },
  { term: "Reasoning effort", def: "How long the model thinks before answering: low, medium or high. Both roles use medium." },
  { term: "Token", def: "The unit AI use is measured and limited in; roughly 3.5 characters of text." },
  { term: "Snapshot", def: "A copy of the test file, go.mod and go.sum taken before a candidate, so a rejection restores them exactly." },
  { term: "Guard", def: "The static check that refuses dangerous imports and code before anything compiles. A filter, not a sandbox." },
  { term: "Pruning", def: "Removing only the new tests that failed, then checking the rest again." },
  { term: "Mechanical repair", def: "A fix the code makes without AI: a missing import, a self-qualified name, a duplicate test name." },
  { term: "Event stream", def: "Server-Sent Events: the numbered log of a run that the job page replays and follows." },
];

export default function WalkthroughPage() {
  return (
    <div className="lg:grid lg:grid-cols-[14rem_minmax(0,1fr)] lg:gap-x-14">
      <PageHeader className="lg:col-start-2" title="What happens when you press Start"
                  lede={<>
                    Every step of one run, in the order the code runs it: what it does, the file that does it, and the events the browser sees.
                    For the two-minute version, see <Link href="/how-it-works" className={inlineLinkClass}>How it works</Link>.
                  </>} />

      <aside className="mt-8 lg:col-start-1 lg:row-span-2 lg:row-start-1 lg:mt-0">
        <div className="lg:sticky lg:top-20 lg:max-h-[calc(100vh-6rem)] lg:overflow-y-auto lg:pb-6">
          <Toc />
        </div>
      </aside>

      <div className="mt-4 max-w-[44rem] space-y-12 leading-relaxed lg:col-start-2">
        <Section id="start">
          <p>You pick a Go module from the repos folder, set a coverage target (80% by default, anywhere from 1 to 100) and press Start. The browser sends one request, then only listens. It never drives the run.</p>
          <Pre caption="frontend/src/lib/api.ts. The options shown are the defaults.">{`POST /api/jobs
{ "repo_path": "stats", "target_coverage": 80,
  "options": { "max_iterations": 20, "min_gain": 1.0, "patience": 2,
               "targets_per_iteration": 3, "max_fix_attempts": 2,
               "delete_existing_tests": true, "max_llm_tokens": 1000000,
               "exclude_patterns": ["examples/**", "testdata/**"],
               "write_summary": true } }`}</Pre>
          <H3>Checks before anything starts</H3>
          <p>Each refusal comes back as <C>{`{"error": {"code", "message"}}`}</C>:</p>
          <ul className="list-disc space-y-1 pl-5 marker:text-muted">
            <li>A write from another website: <C>403 forbidden_origin</C>.</li>
            <li>A malformed body: <C>400 invalid_request</C>.</li>
            <li>A path outside the repos folder, or one without <C>go.mod</C>: <C>400 invalid_repo</C>. A path on your own machine (like <C>C:\…</C>) gets an explanation.</li>
            <li>No Groq key: <C>400 llm_not_configured</C>.</li>
            <li>Fewer than 20,000 tokens left in today’s budget: <C>429 daily_budget_low</C>.</li>
            <li>Another job still running (one at a time): <C>409 job_running</C>.</li>
          </ul>
          <H3>A job id comes back at once</H3>
          <p>The API answers <C>{`201 {"job_id": "…"}`}</C> right away and the run continues as a background task. Everything from here on is recorded as numbered events, starting with <C>job_started</C> as event 0.</p>
          <H3>The browser follows an event stream</H3>
          <p>The job page opens <C>GET /api/jobs/&#123;id&#125;/events</C> (Server-Sent Events). The server replays every event from 0, then sends new ones as they happen, with a keep-alive every 15 s. The page ignores sequence numbers it has already seen, so a refresh or a second tab shows the full history without duplicates. Cancel is <C>POST /api/jobs/&#123;id&#125;/cancel</C>.</p>
          <Where code={["backend/app/main.py", "backend/app/api.py", "backend/app/jobs.py", "frontend/src/lib/useJobEvents.ts"]} events={["job_started"]} />
        </Section>

        <Section id="prepare">
          <H3>Copy the repository</H3>
          <p><C>repos/&lt;name&gt;</C> is copied to <C>/work/&lt;job id&gt;/repo</C>. <C>.git</C> and symbolic links are skipped, so a link cannot pull in files from elsewhere. Your repository is never written to.</p>
          <H3>Delete the existing tests</H3>
          <p>By default (<C>delete_existing_tests</C>) every <C>*_test.go</C> file in the copy is removed, so the result measures only the tests this tool writes. The removed files are listed in <C>workspace_ready</C>.</p>
          <H3>Read the module and find the packages</H3>
          <p><C>go.mod</C> gives the module path and the Go version. The version becomes rules in every prompt: standard library only and no <C>t.Parallel()</C> always; before Go 1.18 no generics; before 1.21 no <C>slices</C>, <C>maps</C>, <C>cmp</C> or <C>min</C>/<C>max</C>/<C>clear</C>; before 1.22, copy loop variables before using them in a closure.</p>
          <p><C>go list -json ./...</C> finds the packages. <C>main</C> packages, packages without Go files and paths matching <C>exclude_patterns</C> (<C>examples/**</C>, <C>testdata/**</C>) are left out. If nothing is left, the job fails with <C>no_packages</C>.</p>
          <H3>Seed each package</H3>
          <p>Every package without a test file gets <C>zz_coverage_seed_test.go</C> containing only <C>package &lt;name&gt;</C>. With it, Go reports every statement of that package (at 0) instead of leaving the package out of the total. The seed file is never exported.</p>
          <H3>Inventory the code with Go’s own parser</H3>
          <p><C>gohelper</C>, a small Go program built on <C>go/ast</C>, lists every function with its file, receiver, name and line range, and every type, var and const. Later it also lists the names already declared in a package’s tests, and does the merge and prune.</p>
          <Pre caption="Shapes of the output; values illustrative.">{`gohelper funcs .    → [{"file": "mean.go", "receiver": "", "name": "Mean", "start_line": 6, "end_line": 15, …}, …]
gohelper symbols .  → [{"name": "EmptyInputErr", "kind": "var", "file": "errors.go", …}, …]`}</Pre>
          <Where code={["backend/app/engine/setup.py", "backend/app/workspace.py", "backend/app/gotools.py", "tools/gohelper"]} events={["workspace_ready"]} />
        </Section>

        <Section id="measure">
          <ol className="list-decimal space-y-2 pl-5 marker:text-muted">
            <li><strong className="font-semibold">Does it build?</strong> <C>go test -count=1 -run=^$ &lt;packages&gt;</C> builds the test binaries without running anything. On failure the job stops with <C>repo_does_not_build</C> and the compiler output. Product code is never edited.</li>
            <li><strong className="font-semibold">Measure.</strong> <C>go test -count=2 -covermode=set -coverprofile=cover.out -timeout=60s &lt;packages&gt;</C>. If tests were kept and fail, the job stops with <C>existing_tests_fail</C>; a timeout gives <C>baseline_timeout</C>.</li>
            <li><strong className="font-semibold">Vet.</strong> <C>go vet</C> must already pass on the untouched copy. Otherwise every candidate would be rejected for a problem it did not cause, so the job stops with <C>repo_vet_fails</C> before spending any tokens.</li>
          </ol>
          <p><C>baseline_measured</C> carries the report: total and covered statements, the percentage, and per-file and per-function coverage with the uncovered line ranges. How the profile becomes a percentage is in <a href="#coverage" className={inlineLinkClass}>How the number is computed</a>.</p>
          <p>Every command runs with a fixed argument list (no shell), a scrubbed environment and a 120 s timeout; on a timeout or Cancel its whole process group is killed.</p>
          <Where code={["backend/app/engine/setup.py", "backend/app/validator.py", "backend/app/gotools.py", "backend/app/coverage.py"]} events={["baseline_measured", "job_failed"]} />
        </Section>

        <Section id="plan">
          <p>Choosing what to test is a sort, not a judgement call: no AI, no tokens, easy to test.</p>
          <ol className="list-decimal space-y-1.5 pl-5 marker:text-muted">
            <li>Take every function with uncovered statements, except those that have failed twice and those found too large for one request.</li>
            <li>Sort them by uncovered statements, largest first.</li>
            <li>Per source file, pack functions into one target, biggest first, until it holds at most 5 functions or 100 uncovered statements. A function that would overflow waits for a later round; a single function over 100 still gets a target of its own.</li>
            <li>Rank the targets by uncovered statements and take up to 3 targets per round (<C>targets_per_iteration</C>, 1 to 5).</li>
          </ol>
          <p>Packing by file spends each request’s fixed cost where it buys the most: in the first stats run, targets over 40 statements cost about 1.9K tokens per percentage point, against about 3.7K for targets of 20 or fewer. If no target is left, the run stops with <C>no_remaining_targets</C>.</p>
          <Pre caption="Run 26598ee5c57b, round 1, abridged (recorded before the 5-function cap; norm.go then held 8 functions). LoadRawData alone has 107 uncovered statements, so it is a target by itself.">{`{"seq": 4, "type": "plan_created", "data": {"index": 1, "items": [
  {"file": "load.go", "functions": ["LoadRawData"], "uncovered_statements": 107},
  …two more targets
]}}`}</Pre>
          <Where code={["backend/app/agents/planner.py", "backend/app/engine/orchestrator.py"]} events={["iteration_started", "plan_created"]} />
        </Section>

        <Section id="write">
          <H3>Snapshot first</H3>
          <p>Before anything changes, the target’s test file (<C>&lt;source&gt;_test.go</C>), <C>go.mod</C> and <C>go.sum</C> are saved so they can be restored exactly.</p>
          <H3>Build the prompt</H3>
          <p>A deterministic builder assembles the context in this order:</p>
          <Pre>{`## Module          module path, package, test file, Go version and its rules
## Names already declared in this package's tests     (never trimmed)
## Functions to test   source with doc comments; untested lines end in // UNCOVERED
## Tests already in mean_test.go    signatures only; the newest are kept if space runs out
## Related declarations in this package    types, vars, consts the targets use (dropped first)
## Task            Write new tests for \`Mean\`, … Focus on the lines marked // UNCOVERED.`}</Pre>
          <p>The whole prompt (system prompt, context and task) must fit <C>MAX_PROMPT_TOKENS</C>, 12,000 by default, counted as characters ÷ 3.5. If the functions alone do not fit, the target is retried with its first function only; a single function that does not fit is skipped for good (<C>too_large</C>). Free-trial keys (8K tokens per minute) should set 4,500.</p>
          <H3>Call the Writer</H3>
          <p>One request to Groq: <C>openai/gpt-oss-120b</C>, reasoning effort <C>medium</C> (<C>high</C> is accepted but was measured as too slow), temperature 0.2, and a strict JSON schema, so the answer always has this shape:</p>
          <Pre>{`{ "test_plan":      [{"scenario": "empty input returns EmptyInputErr", "target": "Mean"}],
  "imports":        ["testing", "math"],
  "code":           "func TestMean(t *testing.T) { … }",
  "suspected_bugs": [] }`}</Pre>
          <p>The output allowance, <C>max_completion_tokens</C>, is the model’s maximum of 65,536, lowered to the key’s tokens-per-minute limit minus the prompt and a 256-token margin (at least 1,024) when that is smaller, so a long answer is not cut off mid-JSON.</p>
          <H3>When the answer goes wrong</H3>
          <ul className="list-disc space-y-1.5 pl-5 marker:text-muted">
            <li><strong className="font-semibold">Cut off</strong> (finish reason <C>length</C>): retried one effort lower, <C>medium</C> to <C>low</C>. Cut off at <C>low</C>, the first half of the target’s functions is retried right away; the rest stay in the pool for a later round. A single function is skipped for good (<C>too_large</C>).</li>
            <li><strong className="font-semibold">Malformed JSON</strong> (<C>400 json_validate_failed</C>): sampled once more; a second failure is treated like a cut-off answer: the first half is retried and the rest go back to the pool.</li>
            <li><strong className="font-semibold">No answer within 240 s</strong> (<C>GROQ_TIMEOUT_S</C>): retried once at <C>low</C> effort, which answers fastest. A second timeout fails the target as <C>llm_timeout</C>. Same for the Fixer.</li>
            <li><strong className="font-semibold">Request too large for the key</strong>: retried once with the allowance clamped to the limit Groq names.</li>
            <li><strong className="font-semibold">Network or server errors</strong>: up to 3 retries with backoff. A rejected key (401) fails the job.</li>
          </ul>
          <p><C>llm_request</C> is emitted right before each request; the job page turns it into a live “Waiting for Groq · 1m 42s” line. <C>llm_call</C> follows with the tokens used and the effort that answered, then <C>candidate_generated</C> with the code and test plan.</p>
          <H3>Parallel writers (optional)</H3>
          <p>With <C>PARALLEL_WRITERS=true</C> (off by default) all of a round’s Writer requests go out at once, each built from the coverage at the start of the round, and the job page shows “Waiting for Groq · 3 requests · writer · medium · 8s”. Validation does not change: the answers are checked one at a time, in plan order, through every gate below, and the Fixer still runs inside each item. Before each check the context is rebuilt from the current workspace, so a test name another item just added is renamed mechanically and lines it already covered end as <C>no_gain</C>; the Writer is also asked to prefix new helpers with the file’s name (<C>normCases</C>), since one package is one namespace. Every request reserves its share of the job and daily budgets before it is sent (a cap is overshot by at most one reservation while answers stay within <C>CALL_TOKEN_RESERVATION</C>), a 429 pauses all of them, and Cancel stops them together. When the goal is reached mid-round, the remaining answers are paid for but not checked. It is faster on paid keys; a free-trial key (8K tokens per minute) gains nothing and should keep it off.</p>
          <Where code={["backend/app/agents/context.py", "backend/app/agents/llm_agents.py", "backend/app/llm/client.py", "backend/app/agents/prompts/writer.md"]} events={["llm_request", "llm_call", "candidate_generated"]} />
        </Section>

        <Section id="validate">
          <p>Each candidate goes through the gates in order and stops at the first one it fails. The kind it fails with decides what happens next.</p>
          <GateChain />
          <p>Every check emits <C>validation_result</C> with the kind, the first 4,000 characters of tool output and the failing test names.</p>
          <Where code={["backend/app/agents/repair.py", "backend/app/guard.py", "backend/app/validator.py", "tools/gohelper/merge.go"]} events={["mechanical_repair", "validation_result"]} />
        </Section>

        <Section id="keep">
          <Rules head={["Result", "What happens"]} rows={KEEP} />
          <H3>What the Fixer sees from earlier attempts</H3>
          <p>Each check of the target becomes one compact record: its source (writer, prune, auto-fix or LLM fix), the kind, the failed tests and the first assertion lines with the values the code actually produced. The history is capped at 1,500 tokens and always keeps the first and the latest failure with observed values. If pruning left no new coverage because the tests that reached new lines were the ones that failed, the Fixer is told to keep them and correct their expected values.</p>
          <Pre caption="Shape of the history; values illustrative.">{`## Earlier attempts for these functions
1. writer -> test_failure
   TestNcr/overflow: norm_test.go:41: got 0, want +Inf
2. prune of [TestNcr] -> no_gain`}</Pre>
          <H3>When the Fixer prompt does not fit</H3>
          <p>It shrinks step by step instead of failing:</p>
          <ol className="list-decimal space-y-1 pl-5 marker:text-muted">
            <li>Related declarations are dropped.</li>
            <li>The history is cut to the first and latest failures with observed values.</li>
            <li>The validator output is cut to its first lines (800 characters).</li>
            <li>The code is cut to the whole declarations the errors point at (2,500 characters).</li>
            <li>Smaller again: 1,000 characters of code, 300 of output, no test plan.</li>
            <li>The code is left out and a fresh replacement asked for.</li>
          </ol>
          <p>If even that does not fit, the target is rejected as <C>prompt_too_large</C> and no model call is made.</p>
          <p>If anything unexpected happens mid-candidate, or you press Cancel, the snapshot is restored before the error goes further. Between candidates the workspace always compiles and passes.</p>
          <Where code={["backend/app/engine/orchestrator.py", "backend/app/agents/repair.py", "backend/app/agents/history.py", "backend/app/agents/llm_agents.py"]} events={["tests_pruned", "mechanical_repair", "fix_attempt", "candidate_accepted", "candidate_rejected"]} />
        </Section>

        <Section id="stop">
          <p>After every round, <C>iteration_completed</C> records the start and end percentage and how many targets were accepted and rejected; then the stop rules are checked. If none applies, the next round plans from the new coverage report.</p>
          <Rules head={["Stop reason", "When"]} rows={STOP_RULES} />
          <p>Whatever the reason, accepted tests are kept. The run itself ends with <C>job_completed</C>, <C>job_cancelled</C>, or <C>job_failed</C> when setup could not finish. Unless the AI summary is turned off, a summarizer <C>llm_request</C> and then <C>summary_generated</C> or <C>summary_failed</C> follow (see the AI summary under Results).</p>
          <Where code={["backend/app/engine/orchestrator.py", "backend/app/engine/policy.py", "backend/app/jobs.py"]} events={["iteration_completed", "job_completed", "job_cancelled", "job_failed", "summary_generated", "summary_failed"]} />
        </Section>

        <Section id="results">
          <H3>Files on your machine</H3>
          <Pre>{`./output/<job id>/
  tests/         every accepted test file, at its path in the repo (the seed file is left out)
  report.json    stop reason and message, baseline → final %, every round, per-file before/after,
                 tests added, possible bugs, tokens, duration,
                 the AI summary (ai_summary)
  SUMMARY.md     the AI summary as Markdown (when one was written)
  events.jsonl   every event, one JSON object per line, including the final one`}</Pre>
          <H3>The AI summary</H3>
          <p>After the result is shown, one more model call (the Summarizer) gets the run’s measured facts as JSON: coverage, rounds, time, tokens, an estimated cost when prices are set, rejected targets, the least-covered files and suspected bugs. It returns two summaries, one for stakeholders and one for engineering teams. A deterministic grounding check then drops any sentence whose numbers, files or test names are not in those facts; suspected bugs are copied from the facts, not written by the model. The job stays busy until the summary is written, so a new run can’t start until then, and Cancel stops only the summary. It is skipped when Groq was unreachable at the end (<C>llm_unavailable</C>); Write again on the run page asks for a new one. Turn it off with <C>write_summary: false</C> or the checkbox in the advanced options.</p>
          <H3>The job page</H3>
          <p>It renders entirely from the events: the coverage meter with the target marker, coverage per round as a chart, the Activity list with every numbered attempt and its errors, the generated test files with syntax highlighting, coverage by file, and possible bugs the model reported.</p>
          <H3>One candidate in the event stream</H3>
          <Pre caption="Run 26598ee5c57b, round 1, abridged. Current builds also send llm_request and the reasoning effort.">{`{"seq": 5, "type": "llm_call",            "data": {"index": 1, "file": "load.go", "role": "writer",
                                                  "prompt_tokens": 3301, "completion_tokens": 1220, "total_tokens": 4521}}
{"seq": 6, "type": "candidate_generated", "data": {"index": 1, "file": "load.go", "test_file": "load_test.go", "code": "…", "test_plan": […]}}
{"seq": 7, "type": "validation_result",   "data": {"index": 1, "file": "load.go", "kind": "accepted", "output": "", "failed_tests": []}}
{"seq": 8, "type": "candidate_accepted",  "data": {"index": 1, "file": "load.go", "test_file": "load_test.go",
                                                  "tests": ["TestLoadRawData"], "percent": 3.69, "gain": 3.69}}`}</Pre>
          <H3>Measured results</H3>
          <p>Developer-plan Groq key, default options except where the first column says otherwise, each project’s own tests deleted first, so every run starts at 0.0%. The goal is in the first column. The btree run stopped with <C>marginal_gains</C>: the last 2 rounds each added less than its 0.5-point minimum gain. The last row is the run whose tests were re-checked below.</p>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[34rem] text-left text-sm">
              <thead className="text-xs text-muted">
                <tr className="border-b border-border">
                  <th scope="col" className="py-2 pr-4 font-medium">Project and run</th>
                  <th scope="col" className="py-2 pr-4 font-medium">Coverage</th>
                  <th scope="col" className="py-2 pr-4 text-right font-medium">Rounds</th>
                  <th scope="col" className="py-2 pr-4 text-right font-medium">Time</th>
                  <th scope="col" className="py-2 pr-4 text-right font-medium">Tokens</th>
                  <th scope="col" className="py-2 text-right font-medium">Targets kept / rejected</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {MEASURED.map((r) => (
                  <tr key={r.job}>
                    <th scope="row" className="py-2 pr-4 font-normal"><span className="font-mono text-[0.8125rem]">{r.repo}</span><br /><span className="font-mono text-xs text-muted">{r.job}</span></th>
                    <td className="py-2 pr-4 font-mono font-semibold tabular-nums">{r.cov}</td>
                    <td className="py-2 pr-4 text-right tabular-nums">{r.rounds}</td>
                    <td className="py-2 pr-4 text-right tabular-nums">{r.time}</td>
                    <td className="py-2 pr-4 text-right tabular-nums">{r.tokens}</td>
                    <td className="py-2 text-right tabular-nums">{r.kept}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p>The tests from run 89eb53b5907e were copied into a fresh clone of stats with its tests deleted; <C>go vet</C> was clean, every test passed, and plain Go measured 80.5%. An earlier run on a free-trial key (8K tokens per minute) reached 69.0% in about 28 minutes, mostly waiting on rate limits.</p>
          <p>Why the semver sample starts at 1.4% and not 0%: a package’s <C>init()</C> functions run when the package loads, so their statements (version.go:83 and constraints.go:206) count as covered before any test exists. That is true and measured, not an error. For this reason the results above use runs that started at exactly 0%.</p>
          <Where code={["backend/app/engine/run.py", "backend/app/jobs.py", "backend/app/summary/grounding.py", "frontend/src/app/jobs/[id]/page.tsx", "README.md"]} events={["job_completed", "summary_generated"]} />
        </Section>

        <Section id="coverage">
          <H3>The coverage profile</H3>
          <p><C>go test -covermode=set -coverprofile</C> writes one line per block: the file, the start and end as line.column, the number of statements, and whether the block ran (1) or not (0).</p>
          <Pre caption="mean.go: the Mean function, columns illustrative. 4 statements, 3 ran: 75%. The empty-input return never ran.">{`mode: set
github.com/montanaflynn/stats/mean.go:6.47,8.22 1 1
github.com/montanaflynn/stats/mean.go:8.22,10.3 1 0
github.com/montanaflynn/stats/mean.go:12.2,15.2 2 1`}</Pre>
          <p>The module prefix is stripped from each path. A block listed more than once counts as run if any line says so. Coverage is covered statements ÷ all statements across the measured packages, as a percentage rounded to 2 decimals. Each block is assigned to the function whose line range (from <C>gohelper funcs</C>) contains its start, which gives the per-function numbers the planner sorts by.</p>
          <p>A package with no test file at all can be left out of the profile, depending on the Go version, and the total would then look better than it is. That is why every such package gets <C>zz_coverage_seed_test.go</C> during setup: its statements then count, at 0.</p>
          <H3>What “no new coverage” means</H3>
          <p>The set of covered block ids before a candidate is compared with the set after:</p>
          <ul className="list-disc space-y-1.5 pl-5 marker:text-muted">
            <li>After is a strict superset of before: <span className={`${m} text-accent`}>accepted</span>.</li>
            <li>The sets are equal: <C>no_gain</C>, “the new tests executed no previously uncovered statements”. The tests may be perfectly correct, but they only repeat what is already checked.</li>
            <li>A block that was covered is not any more: <C>no_gain</C>, “the new tests made previously covered statements uncovered”.</li>
          </ul>
          <p>It also happens after pruning, when the only tests that reached new code were the ones that failed. In the Mean example, a test calling <C>Mean</C> with an empty slice runs the block at line 8, so it would be accepted.</p>
          <H3>How the 80.5% check was run</H3>
          <Pre>{`git clone --depth 1 https://github.com/montanaflynn/stats verify && cd verify
find . -name '*_test.go' -delete
cp -r ../output/<job id>/tests/. .
go vet . && go test -count=1 -coverprofile=c.out . && go tool cover -func=c.out | tail -1`}</Pre>
          <Where code={["backend/app/coverage.py", "backend/app/validator.py", "backend/app/workspace.py"]} />
        </Section>

        <Section id="safety">
          <ul className="list-disc space-y-2 pl-5 marker:text-muted">
            <li><strong className="font-semibold">A copy, and only test files.</strong> The run works on <C>/work/&lt;job id&gt;/repo</C>. The workspace writes and restores only <C>*_test.go</C>, <C>go.mod</C> and <C>go.sum</C>, and refuses any other path.</li>
            <li><strong className="font-semibold">The model never gets a shell.</strong> It returns schema-checked JSON; the code decides what runs, always with fixed argument lists.</li>
            <li><strong className="font-semibold">Environment allowlist.</strong> Go commands get only <C>PATH</C>, <C>HOME</C>, <C>TMPDIR</C>, <C>GOPROXY</C>, <C>GOPRIVATE</C>, <C>GONOSUMDB</C> and the proxy variables, plus <C>GOFLAGS=-mod=readonly</C>, <C>GOTOOLCHAIN=local</C>, <C>CGO_ENABLED=0</C> and <C>GOTELEMETRY=off</C>. The Groq key is not passed to test processes.</li>
            <li><strong className="font-semibold">Timeouts.</strong> 120 s per command and 60 s per <C>go test</C>; the whole process group is killed on a timeout or Cancel.</li>
            <li><strong className="font-semibold">The guard is best effort, not a sandbox.</strong> Generated tests run inside the backend container as a non-root user and could still read files there, including the backend’s environment through <C>/proc</C>, by getting around the filter (string building, reflection). The container is the only real isolation; a per-job sandbox (gVisor or Firecracker) is future work.</li>
            <li><strong className="font-semibold">Local only.</strong> Both ports are bound to <C>127.0.0.1</C>, writes from other websites are refused, and the Docker socket is not mounted.</li>
            <li><strong className="font-semibold">Your code goes to Groq.</strong> The functions being tested and the related declarations are sent in each prompt.</li>
          </ul>
          <H3>Rate limits and budgets</H3>
          <p>The client reads Groq’s <C>x-ratelimit</C> headers and, when fewer than 16,000 tokens remain in the current minute, waits for the reset. A 429 is retried after its <C>Retry-After</C>, up to 5 times and at most 90 s; each pause is a <C>rate_limited</C> event. <C>DAILY_TOKEN_BUDGET</C> is the app’s own cap (2,000,000 by default, counted in <C>./output/.usage.json</C>, reset at 00:00 UTC), not a Groq limit; a run needs at least 20,000 tokens left to start.</p>
          <Where code={["backend/app/workspace.py", "backend/app/gotools.py", "backend/app/guard.py", "backend/app/llm/limits.py", "docker-compose.yml"]} events={["rate_limited"]} />
        </Section>

        <Section id="glossary">
          <dl className="grid gap-x-8 gap-y-4 sm:grid-cols-2">
            {GLOSSARY.map((g) => (
              <div key={g.term} className="space-y-0.5">
                <dt className="font-medium">{g.term}</dt>
                <dd className="text-sm leading-relaxed text-muted">{g.def}</dd>
              </div>
            ))}
          </dl>
        </Section>

        <footer className="flex flex-wrap items-center gap-x-6 gap-y-3 border-t border-border pt-6">
          <Link href="/" className={buttonClass({ variant: "primary" })}>Start a run</Link>
          <Link href="/how-it-works" className={`text-sm ${actionLinkClass}`}>Back to How it works</Link>
        </footer>
      </div>
    </div>
  );
}
