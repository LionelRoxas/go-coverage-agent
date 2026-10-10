# go-coverage-agent

[![ci](https://github.com/LionelRoxas/go-coverage-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/LionelRoxas/go-coverage-agent/actions/workflows/ci.yml)

An autonomous agent that raises unit-test coverage for Go repositories. Give it a local Go module and a target
percentage. It measures coverage, plans what to test, asks an LLM to write idiomatic Go tests, compiles and runs
them, keeps only the tests that pass and add coverage, and repeats until it hits the target or gains flatten out.

<a href="docs/screenshots/gallery-summary.png"><img src="docs/screenshots/gallery-summary.png" width="100%" alt="Results page for montanaflynn/stats showing 81.1% coverage against an 80% target and a Target reached summary card"></a>

## Quick start

Requirements: Docker Desktop with Compose v2.24+, and a Groq API key from https://console.groq.com/keys.
Node 22+ is only needed to run the frontend tests outside Docker.

```bash
git clone https://github.com/LionelRoxas/go-coverage-agent.git && cd go-coverage-agent
cp .env.example .env          # then paste your key into GROQ_API_KEY
docker compose up --build
```

Open http://localhost:3000 (or `http://localhost:${FRONTEND_PORT}` if you changed it), click the
**montanaflynn/stats** card under **Sample repos**, then follow the four steps: **Next** to set a target (80% by default),
**Next** or **Skip (use defaults)** past the optional advanced options, then **Start** on the review step.
The New run page shows one step at a time: choose a repository, set a target, optional advanced options, review & start.

**Model:** `openai/gpt-oss-120b` on Groq (fallback: `openai/gpt-oss-20b`, set `GROQ_MODEL` in `.env`). The model name is also
reported by `GET /api/health` and shown in the UI.

If `.env` is missing or has no key, the stack still starts and the UI shows a "No Groq API key configured" banner.

**Ports.** Set `BACKEND_PORT` / `FRONTEND_PORT` in `.env` (defaults 8000 / 3000) if those are taken. Changing them requires
`docker compose up --build`, because the frontend bakes the API URL at build time.

**Linux note.** The backend runs as uid 1000. On Linux hosts with a different uid, make `./repos` and `./output` writable by uid 1000.

### What to expect

- On a Groq **Developer plan** (observed limit: 250K tokens/min) a run on `stats` to 80% took about **5 minutes**
  (287 s, 184,926 tokens) with no rate-limit waits.
- On a **free-trial key** (8K tokens/min, 200K tokens/day), set `DAILY_TOKEN_BUDGET=190000`, `MAX_PROMPT_TOKENS=4500` and `CALL_TOKEN_RESERVATION=8000` in `.env`. The client reads the key's tokens-per-minute limit from Groq's response headers and automatically lowers `max_completion_tokens` to fit (a rejected request is retried once with the clamped value); Developer keys keep 65536. To force a smaller value, set `GROQ_MAX_COMPLETION_TOKENS` (e.g. `4000`). Expect long waits
  (the UI shows "waiting for rate limit"; that's normal) and possibly stopping short of 80%. An earlier run on such a key reached
  69.0% in about 28 minutes, mostly waiting on rate limits, before the then-default 10-iteration cap. Plan on one full run per key per day.
- Accepted tests are always saved, even if a run stops early.

## Using your own repository

Step 1 of the setup page, **Choose a repository**, has two tabs.

**Sample repos** lists six small, dependency-free Go libraries. Click one and it is downloaded into `./repos/<id>` (shallow clone of a pinned release tag, no submodules; stats: default branch, the assessment's evaluation repo), then selected. Nothing else is fetched.

| Sample | What it is | Licence |
|---|---|---|
| `montanaflynn/stats` | Statistics functions | MIT |
| `Masterminds/semver` | Semantic version parsing and constraints | MIT |
| `huandu/xstrings` | String utilities | MIT |
| `dustin/go-humanize` | Human-friendly numbers, sizes and times | MIT |
| `google/btree` | In-memory B-tree (generics) | Apache-2.0 |
| `shopspring/decimal` | Arbitrary-precision decimals | MIT |

**Your folders** is where your own projects go. Press **Choose a folder…** (or drag the folder onto the box) and pick the folder that contains `go.mod`. The browser uploads the project's files and the backend saves them under `./repos/uploads/<name>`; the project then appears in the list, selected. Your original folder is never changed; upload it again to refresh the copy. What is sent and kept:

- `.git`, `vendor`, `node_modules` and hidden files or folders are skipped, as are files over 1 MB and binary files.
- At most 3,000 files and 25 MB in total after skipping (`UPLOAD_MAX_FILES`, `UPLOAD_MAX_BYTES`); a larger folder is stopped before anything is sent.
- An upload only ever replaces a folder that an earlier upload created; any other folder with the same name is left untouched and you are asked for a different name.
- If the mounted folder already has an `uploads` folder of its own, the app leaves it alone and refuses to upload until it is renamed.

The tab also lists every other Go module (a folder with a `go.mod`, up to two levels deep) in the mounted folder, apart from the samples. For large projects, or to keep a folder in sync while you edit it, mount it instead:

1. Copy or clone it into the mounted folder (`./repos` by default; the tab shows the real host path), then press Refresh; or
2. Set `HOST_REPOS_DIR` in `.env` to any parent folder and run `make up` again. Compose needs an absolute path (it does not expand `~`) or one relative to this repository:

   | OS | Example |
   |---|---|
   | Windows | `HOST_REPOS_DIR=C:\Users\you\code` |
   | macOS | `HOST_REPOS_DIR=/Users/you/code` |
   | Linux | `HOST_REPOS_DIR=/home/you/code` |

Your repository is never modified: the agent works on a copy, and the generated tests are written to `./output/<job-id>/tests/`.

Every run is saved in `./output/<job-id>` (events, report, tests, summary), and Run history reloads it from there when the app restarts, so earlier runs stay viewable. A run the app was shut down in the middle of shows as Interrupted, with the results up to that point; a run whose container was killed outright mid-run has no saved events yet and is not listed. Delete `./output/<job-id>` to remove a run.

## How it works

```
┌──────────────────────────── docker compose ────────────────────────────┐
│  ┌──────────────┐   HTTP + SSE    ┌──────────────────────────────────┐ │
│  │  frontend    │ ──────────────▶ │  backend (FastAPI)               │ │
│  │  Next.js     │ 127.0.0.1:8000  │  API ─▶ JobManager ─▶ Orchestrator │
│  │  :3000       │                 │      Planner    Writer/Fixer  Validator
│  └──────────────┘                 │   (deterministic)  (LLM)     (go tools)
│                                   │               LLM client   gohelper│
│                                   │                  Groq API   go test/vet/gofmt
│                                   │   Workspace: /work/<job>/repo (copy)│
│                                   └──────────────────────────────────┘ │
│  volumes: ${HOST_REPOS_DIR:-./repos} ─▶ /repos   ./output ─▶ /output    │
└────────────────────────────────────────────────────────────────────────┘
```

The loop is plain, testable Python. The LLM only writes and fixes tests, and summarizes the finished run. The app explains the same loop in plain language at `/how-it-works`, and step by step for technical readers at `/walkthrough` (each How it works step links to its Walkthrough section).

1. **Measure.** Copy the repo, delete existing `_test.go` files (default), and measure baseline coverage per package with `go test -coverprofile`.
2. **Plan.** A deterministic planner ranks files by uncovered statements and picks up to 3 targets per iteration (no planning tokens).
3. **Write.** The Writer LLM gets a compact context (the functions to test, with lines marked `// UNCOVERED`) and returns new test functions as schema-constrained JSON.
4. **Merge and validate.** A Go AST helper appends the tests to `<source>_test.go`. The candidate must pass the import guard, `go vet`, and `go test -count=2`, and the set of covered blocks must be a strict superset of the previous one.
5. **Repair.** Failing assertions are pruned test by test; stray quotes or backslashes around import paths, forgotten imports, unqualified identifiers and reused test names are fixed mechanically; anything else goes to the Fixer LLM (up to 2 attempts). Rejected candidates are rolled back.
6. **Stop** on target reached, marginal gains (less than `min_gain` points for `patience` iterations), max iterations, no remaining targets, token budget, or cancel. Artifacts are always written.
7. **Summarize.** After the result is shown, one more LLM call writes two summaries from the run's measured facts (coverage, rounds, time, tokens, an estimated cost when `GROQ_PRICE_*_PER_M` are set, rejected targets, the least-covered files, suspected bugs): one **for stakeholders** (outcome, efficiency, risks, recommendation) and one **for engineering teams** (what was tested, where the tests are, gaps, how to run them, next steps). A deterministic check then drops any sentence whose numbers (digits, number words, dollar amounts, percentages, durations, multipliers such as "3x"), files or test names are not in those facts, each number matched against facts of the same kind; suspected bugs are copied from the facts, not written by the model. The run counts as busy until its summary is written (a new run waits, and Cancel stops only the summary). The run page shows both in tabs with Copy as Markdown and Write again, and they are saved as `output/<job_id>/SUMMARY.md` (and `ai_summary` in `report.json`). Turn it off with the "Write an AI summary at the end" checkbox in the advanced options.

**The UI.** The setup page has a **Runs** panel: a live card for a running job (with Cancel) and past runs with before to after coverage. The job page has an "← All runs" link. The header has a System / Light / Dark toggle (remembered per browser) and a **How it works** page. The Spectro Cloud logo in the navbar is there because this is a take-home for Spectro Cloud; it is not a Spectro Cloud product.

## Results on montanaflynn/stats

Developer-plan key, 2026-10-08, defaults (20 iterations max, 3 targets per iteration), target 80%.

| Target | Final coverage | Tests added | Duration | Tokens | Stop reason |
|---|---|---|---|---|---|
| 80% | 0.0% → 80.51% (1247 statements) | 34 test files; 41 candidates accepted, 4 rejected | 287 s (15 iterations) | 184,926 | `target_reached` |
| 80% (newest run, after the fixes below) | 0.0% → 80.75% | 30 test files; 34 candidates accepted, 1 rejected | 248 s (12 iterations) | 182,494 | `target_reached` |

The 80.51% run (`89eb53b5907e`): 45 LLM calls (41 writer, 4 fixer), 7 mechanical repairs, 0 rate-limit waits.

The newest run (`26598ee5c57b`): 42 LLM calls (35 writer, 7 fixer), 5 mechanical repairs, 0 model errors, 0 rate-limit waits.

Independent check: the generated tests were copied into a fresh clone with all `_test.go` removed; `go vet` was clean, `go test` passed, and
coverage was **80.5%**. The same check on run `ca1beb9a1fdb` (80.11%) also passed, with 80.1%.

An earlier run on a free-trial key (8K tokens/min, 200K/day) reached 69.0% in about 28 minutes before hitting the then-default 10-iteration cap,
mostly waiting on rate limits.

## Results on Masterminds/semver

Developer-plan key, 2026-10-09, target 80%, defaults. Writer at `medium` reasoning in both new runs; the Fixer's effort was the variable.

| Run | Setup | Coverage | Iterations / time | Items accepted / rejected | Tokens |
|---|---|---|---|---|---|
| `acab3e3c7570` | before the prompt-budget and duplicate-name fixes | 1.4% → 64.2%, stopped on small gains | 8 / 129 s | — | 115.9K |
| `f9f3edcd9bfc` | after those fixes, `low` effort | 1.4% → 80.1%, target reached | 4 / 75 s | — | 59.0K |
| `736baa413b5d` | after the Fixer-history fixes, Fixer `medium` | 1.4% → **84.6%**, target reached | 4 / 114 s | 8 / 0 | 82.6K |
| `d247037efdb2` | same, Fixer `low` | 1.4% → **84.4%**, target reached | 3 / 88 s | 7 / 0 | 69.2K |

The 1.4% baseline is not an error: semver's two `init()` functions (`version.go:83`, `constraints.go:206`) run when the package loads, so their statements count as covered before any test exists. The "How it works" and Walkthrough pages therefore report runs that started at exactly 0%.

Each of the last two runs needed only one LLM fix, and both fixes were accepted (12.8 s at `medium`, 9.6 s at `low`), so the two runs are too close to rank the Fixer's effort. A Fixer call at `high` was still waiting after about 114 s, which is why both roles default to `medium`.

### Cap of 5 functions per target (2026-10-09)

The same settings (Writer and Fixer at `medium`, target 80%), changing only the planner's cap from 8 to 5 functions per target:

| | semver, cap 8 | semver, cap 5 | stats, cap 8 | stats, cap 5 |
|---|---|---|---|---|
| Run | `736baa413b5d` | `7a8c53c08bce` | `459dfe48a57f` | `e2de1ca387cb` |
| Coverage | 1.4% → 84.6% | 1.4% → 83.5% | 0% → 80.3% | 0% → 81.1% |
| Rounds / time | 4 / 114 s | 3 / 83 s | 10 / 276 s | 11 / 310 s |
| Targets accepted / rejected | 8 / 0 | 7 / 0 | 28 / 0 | 31 / 0 |
| Passed on the first check | 2 of 8 (25%) | 4 of 7 (57%) | 23 of 28 (82%) | 27 of 31 (87%) |
| LLM fixes | 1 | 0 | 3 | 1 |
| Tokens | 82.6K | 54.5K | 172K | 175K |

With the cap of 5, more targets passed on the first check and fewer LLM fixes were needed. semver used 34% fewer tokens; stats used about the same and took one extra round. These are single runs, so differences of a few seconds or a percentage point are within normal variation.

## Issues I found in testing and fixed

I ran the system end to end, spotted these problems, and decided the fixes. Claude Code implemented them under review.

| Symptom | Root cause | Fix | Evidence |
|---|---|---|---|
| Malformed-JSON errors from Groq (400 `json_validate_failed`) | The output cap (7K minus the prompt) left too little room after hidden reasoning tokens | Removed the artificial cap; `max_completion_tokens` is the model maximum (65536), clamped to the key's per-minute token limit, with one retry on a size rejection | No JSON errors in later runs (see the next rows) |
| A run took about 28 minutes and stopped at 69% | The key was a free-trial key (8K tokens/min, 200K tokens/day), so the agent was pacing to the limits | Switched to a Developer-plan key; documented free-tier settings (`DAILY_TOKEN_BUDGET=190000`) in `.env.example` | Run `a46c5a902f70`: 1678 s, 68.97%, 46 rate-limit events. Run `89eb53b5907e`: 287 s, 80.51% |
| "max completion tokens" / JSON errors, and `norm.go` stuck at 32.7% | Plan items with 12 to 37 functions asked the model for answers too large to finish | The planner caps a plan item at 5 functions / 100 statements (lowered from 8; see Design decisions); an over-size answer splits the item in half and retries | Run `ca1beb9a1fdb` to `26598ee5c57b`: 4 model errors to 0, `norm.go` 32.74% to 90.27%, 80.75% overall |
| I worried that failing tests were counted toward coverage | Not a bug. A candidate is accepted only if `go test -count=2` passes and coverage is a strict superset; rejected candidates are rolled back | Verified, no change | Final tests of run `ca1beb9a1fdb` re-run in a fresh clone: all pass, 80.1% |
| `make test` failed in PowerShell | The Makefile used `cat` and `VAR=x cmd`, which `cmd.exe` lacks | Shell-independent Makefile (`$(file <.go-version)`, exported `MSYS_NO_PATHCONV`) with a fallback for macOS make 3.81 | `make test` passes in PowerShell, Git Bash and CI |
| No way to switch light/dark, no way back to the start page, the running job was only a one-line banner, the navbar looked unfinished, and the app did not explain the loop | UI gaps | System / Light / Dark toggle in the header (remembered per browser), "← All runs" on the job page, a Run history panel on the setup page (live running card with Cancel, past runs with before to after coverage), a redesigned navbar and a How it works page | Screenshots below |
| semver run stalled at 64.2%: fix attempts failed with 'targets need ~3591 tokens; budget is 2191' and duplicate test names | prompt cap from the free-trial era left the fixer too little room; existing test names were crowded out of the prompt | `MAX_PROMPT_TOKENS` default 4,500 → 12,000 (free-trial keys set 4,500); existing test names now come before optional context; Fixer prompts shrink (first error lines, then only the whole declarations the errors point at, then no code) instead of failing; a reused `Test…` name is renamed to `_2`, `_3`, … without an LLM call; an oversized prompt shows as "Prompt too large (no model call)", not "Model error" | Run `acab3e3c7570`: 1.4% → 64.2% in 8 iterations, stopped on small gains. Re-run `f9f3edcd9bfc`: 1.4% → 80.1% in 4 iterations, 75 s, 59K tokens, target reached, 0 model or prompt-size errors; 3 duplicate names renamed without an LLM call |
| LLM fixes kept repeating a wrong assertion (semver constraints.go rejected after 6 attempts). I traced that item through the event log and questioned why the LLM kept failing | the fixer only saw the latest check result; after failing tests were removed it saw 'no new coverage' and never the observed values; reasoning effort was at its minimum | I decided to prioritise LLM quality. The Fixer now gets the candidate's full attempt history (each check's source, kind, failed tests and the failing assertions with their observed values), kept within the prompt budget; after pruning leaves no new coverage it is told to keep the failing tests and correct their values; the Fixer prompt says to trust the observed value; the Writer prompt says to trace the code path before asserting; reasoning effort per role (both default to `medium`: a `high` Fixer call was measured as too slow, still waiting after ~114 s against 9 s for a `medium` Writer call in job `86b6d88b558c`) | Same semver target afterwards: 1.4% → 84.6% in 4 iterations and 114 s, 8 items accepted, 0 rejected, 82.6K tokens (job `736baa413b5d`). See [Results on Masterminds/semver](#results-on-mastermindssemver) |

## Screenshots

<table>
<tr>
<td valign="top" width="50%">
<a href="docs/screenshots/gallery-setup.png"><img src="docs/screenshots/gallery-setup.png" width="100%" alt="New run page at step 1 of the wizard: the header, the four-step stepper, the Sample repos tab with montanaflynn/stats selected, and the Run history panel"></a>
<br><b>New run, step 1</b><br>The header, a chart of a measured run (0% to 100% in 22 rounds), and the wizard on step 1 of 4: the stepper above the six sample repos (<code>montanaflynn/stats</code> selected), beside the Run history panel with three past runs.
</td>
<td valign="top" width="50%">
<a href="docs/screenshots/gallery-runs-dark.png"><img src="docs/screenshots/gallery-runs-dark.png" width="100%" alt="The review step of the New run wizard and the Run history panel in the dark theme"></a>
<br><b>Review &amp; start, dark theme</b><br>Step 4 of 4: the chosen repository, the 80% target and default advanced options with the AI summary on, each with an Edit link, then Start with the token budget beside it. Run history shows stats 0.0% to 81.1%, semver 1.4% to 83.5% and stats 0.0% to 100.0%.
</td>
</tr>
<tr>
<td valign="top" width="50%">
<a href="docs/screenshots/gallery-folders.png"><img src="docs/screenshots/gallery-folders.png" width="100%" alt="Step 1 of the New run wizard on the Your folders tab after uploading a copy of stats: the drop area, the upload result, the uploaded module selected and the HOST_REPOS_DIR note"></a>
<br><b>Your folders</b><br>Step 1 on the Your folders tab, after uploading a local copy of <code>montanaflynn/stats</code>: "Uploaded stats (118 Go files). Skipped: 29 files in .git, 8 hidden files.", with <code>uploads/stats</code> selected under Go modules in <code>./repos</code> and the one-line <code>HOST_REPOS_DIR</code> note below it. The upload selects the folder; Next moves on.
</td>
<td valign="top" width="50%">
<a href="docs/screenshots/gallery-live.png"><img src="docs/screenshots/gallery-live.png" width="100%" alt="Run in progress at 19.9 percent with a Cancel button and the Activity list ending in a running item"></a>
<br><b>Run in progress</b><br>Iteration 2 of a stats run at 19.9% against the 80% target, with a Cancel button, the status "Compiling and running tests for ttest.go…" and <code>ttest.go</code> Running in the Activity list.
</td>
</tr>
<tr>
<td valign="top" width="50%">
<a href="docs/screenshots/gallery-chart.png"><img src="docs/screenshots/gallery-chart.png" width="100%" alt="Line chart of coverage after each of 11 iterations rising past the dashed 80 percent target line"></a>
<br><b>Coverage by iteration</b><br>Coverage after each of the 11 iterations, rising from the 0% baseline to 81.1% and ending just above the dashed 80% target line.
</td>
<td valign="top" width="50%">
<a href="docs/screenshots/gallery-trace.png"><img src="docs/screenshots/gallery-trace.png" width="100%" alt="Expanded Activity item for ttest.go with two numbered attempts: one failing test, then the failing test removed and the rest passing"></a>
<br><b>Attempt trace, expanded</b><br><code>ttest.go</code> in iteration 2: ① written by the LLM, 1 of 5 tests failed (with the failing assertion); ② the failing test removed, 4 kept, passed. Result: accepted at attempt 2, +2.7 pp.
</td>
</tr>
<tr>
<td valign="top" width="50%">
<a href="docs/screenshots/gallery-testfile.png"><img src="docs/screenshots/gallery-testfile.png" width="100%" alt="Generated tests section with correlation_test.go selected and highlighted Go code"></a>
<br><b>Generated tests</b><br>Each of the 29 accepted test files can be read with syntax-highlighted Go, here <code>correlation_test.go</code>.
</td>
<td valign="top" width="50%">
<a href="docs/screenshots/gallery-dark.png"><img src="docs/screenshots/gallery-dark.png" width="100%" alt="Target reached summary card and the AI summary below it, on the For stakeholders tab, in the dark theme"></a>
<br><b>Run page, dark theme</b><br>The Target reached card (0.0% to 81.1%, 109 tests in 29 files, 5m 10s, 175.0k tokens) and, below it, the AI summary on its For stakeholders tab with the run / summary / total cost line, in the dark theme.
</td>
</tr>
<tr>
<td valign="top" width="50%">
<a href="docs/screenshots/gallery-summary-ai.png"><img src="docs/screenshots/gallery-summary-ai.png" width="100%" alt="The Summary section of a finished stats run on the For stakeholders tab: a headline about coverage rising from 0% to 81.1%, then Outcome, Efficiency with an estimated cost, Risks and Recommendation, with Copy as Markdown and Write again buttons"></a>
<br><b>AI summary</b><br>Under the summary card, two tabs: For stakeholders (shown: outcome, efficiency with the cost line "Run cost $0.0674 · summary $0.0013 · total $0.0688", risks, recommendation) and For engineering teams (what was tested, where the tests are, how to run them, gaps, suspected bugs, next steps), with Copy as Markdown (the same text as <code>SUMMARY.md</code>) and Write again. No Groq call was made for this screenshot: the text was written by hand from run <code>e2de1ca387cb</code>'s facts, and a backend test checks that it passes the same grounding check as a real summary.
</td>
<td valign="top" width="50%"></td>
</tr>
<tr>
<td valign="top" width="50%">
<a href="docs/screenshots/gallery-howitworks.png"><img src="docs/screenshots/gallery-howitworks.png" width="100%" alt="How it works page: the five steps of a run side by side, steps 2 to 5 marked as one round with an arrow back to step 2"></a>
<br><b>How it works</b><br>The five steps of a run in plain words, with steps 2 to 5 marked as one round that repeats until the goal or a stop rule; each step links to its Walkthrough section.
</td>
<td valign="top" width="50%">
<a href="docs/screenshots/gallery-walkthrough.png"><img src="docs/screenshots/gallery-walkthrough.png" width="100%" alt="Walkthrough page with a table of contents that follows the run beside the Start a run section"></a>
<br><b>Walkthrough</b><br>The technical version at <code>/walkthrough</code>: the contents follow the run in order (Plan, Write, Validate and Keep grouped under Each round), beside the Start a run section and its request.
</td>
</tr>
</table>

<table>
<tr>
<td valign="top" width="33%">
<a href="docs/screenshots/gallery-setup-mobile.png"><img src="docs/screenshots/gallery-setup-mobile.png" width="100%" alt="The New run wizard at step 1 on a 390 pixel wide phone screen"></a>
<br><b>New run on a phone</b><br>The wizard at 390 px wide, scrolled to the box: "Step 1 of 4 · Choose a repository" with a progress bar, the sample repos (<code>montanaflynn/stats</code> selected), and Next pinned to the bottom of the box.
</td>
<td valign="top" width="33%">
<a href="docs/screenshots/gallery-mobile.png"><img src="docs/screenshots/gallery-mobile.png" width="100%" alt="Run page on a 390 pixel wide phone screen"></a>
<br><b>Run page on a phone</b><br>The 81.1% meter, the summary card in two columns, and the top of the AI summary. The header total (179.5k tokens) includes the summary call.
</td>
<td valign="top" width="33%">
<a href="docs/screenshots/gallery-howitworks-mobile.png"><img src="docs/screenshots/gallery-howitworks-mobile.png" width="100%" alt="How it works page on a 390 pixel wide phone screen"></a>
<br><b>How it works on a phone</b><br>The opening lines and what coverage means.
</td>
</tr>
</table>

## Configuration

Options (`POST /api/jobs`). The UI's "Advanced" section exposes max iterations, min gain, files per iteration (`targets_per_iteration`), fix attempts and the AI summary (`write_summary`); the rest (`patience`, `delete_existing_tests`, `max_llm_tokens`, `exclude_patterns`) are API-only:

| Option | Default | Range |
|---|---|---|
| `target_coverage` | 80 | 1-100 |
| `max_iterations` | 20 | 1-30 |
| `min_gain` (percentage points per iteration) | 1.0 | 0-10 |
| `patience` | 2 | 1-5 |
| `targets_per_iteration` | 3 | 1-5 |
| `max_fix_attempts` | 2 | 0-4 |
| `delete_existing_tests` | true | bool |
| `max_llm_tokens` (per job) | 1,000,000 | 10K-2M |
| `exclude_patterns` (module-relative globs) | `["examples/**", "testdata/**"]` | list |
| `write_summary` (AI summary after the run) | true | bool |

Environment variables (`.env`, same layout as `.env.example`). Only the key is required; everything else has a built-in default.

| Variable | Default | Meaning |
|---|---|---|
| **Required** | | |
| `GROQ_API_KEY` | (empty) | Needed to start a job |
| **Optional** | | |
| `GROQ_MODEL` | `openai/gpt-oss-120b` | `openai/gpt-oss-20b` is cheaper and weaker |
| `GROQ_WRITER_REASONING_EFFORT` | `medium` | Writer's reasoning effort (`medium` or `low`; `high` is accepted but too slow) |
| `GROQ_FIXER_REASONING_EFFORT` | `medium` | Fixer's reasoning effort (`medium` or `low`; `high` is accepted but too slow). If an answer is cut off for length, it is retried automatically one level lower |
| `BACKEND_PORT` / `FRONTEND_PORT` | 8000 / 3000 | Host ports (loopback only); run `make up` again after changing |
| `HOST_REPOS_DIR` | `./repos` | Host folder whose Go modules appear under "Your folders" |
| `DAILY_TOKEN_BUDGET` | 2,000,000 | The app's own daily token cap (not a Groq limit), counted in `output/.usage.json`, reset at midnight UTC. Raise it freely on a paid key |
| `GROQ_PRICE_INPUT_PER_M` / `GROQ_PRICE_OUTPUT_PER_M` | (unset) | Groq prices in USD per 1M input / output tokens. When both are set, the AI summary shows an estimated cost; unset shows none. `.env.example` sets `0.15` / `0.60` as an example (openai/gpt-oss-120b on Groq at the time of writing; check console.groq.com pricing); remove both lines to hide the cost |
| **Free-trial Groq key** (8K tokens/min, 200K/day): set all three | | |
| `DAILY_TOKEN_BUDGET` | | Free trial: `190000` |
| `MAX_PROMPT_TOKENS` | 12000 | Prompt-size cap per call. Free trial: `4500` |
| `CALL_TOKEN_RESERVATION` | 16000 | Tokens reserved per call for rate pacing. Free trial: `8000` |
| **Advanced** | | |
| `UPLOAD_MAX_FILES` / `UPLOAD_MAX_BYTES` | 3000 / 26214400 (25 MB) | Folder upload limits, counted after skipping `.git`, `vendor`, `node_modules`, hidden and binary files. Larger uploads are refused with 413 |
| `UPLOAD_MAX_FILE_BYTES` | 1048576 (1 MB) | Single files larger than this are skipped in an upload |
| `GROQ_MAX_COMPLETION_TOKENS` | 65536 | Output-token cap per call (the model maximum). Empty does not mean unlimited: Groq then applies a smaller default |
| `GROQ_TIMEOUT_S` | 240 | Seconds one Groq request may take. A timed-out request is retried once at `low` reasoning effort; a second timeout fails the item as "Groq timed out" |
| `HISTORY_MAX_RUNS` | 500 | How many of the most recent runs in `./output` Run history reloads on startup; older folders stay on disk but are not listed |

## Running the tests

```bash
make test               # everything: Go helper, backend unit + integration (in Docker), frontend
make test-go
make test-backend
make test-integration
make test-frontend
```

CI (`.github/workflows/ci.yml`) runs exactly these make targets, so the Makefile is the single source of truth for the test commands.

Without `make` (Windows / Git Bash). Go is not required on the host; it runs in Docker:

```bash
export MSYS_NO_PATHCONV=1
# Go helper
docker run --rm -v "$PWD/tools/gohelper:/src" -w /src golang:1.27-bookworm go test ./...
# Backend image, then unit and integration tests inside it
docker build -f backend/Dockerfile --build-arg GO_IMAGE=golang:1.27-bookworm -t gca-backend .
docker run --rm gca-backend uv run --no-sync pytest
docker run --rm gca-backend uv run --no-sync pytest -m integration
# Frontend
cd frontend && npm ci && npm test
```

## Design decisions and trade-offs

- **Deterministic loop, LLM only for writing and fixing tests** (structured JSON output, no tool calls). Why: reliability, token cost, testability, safety. The LLM never gets a shell.
- **Append-only test generation** through a small Go AST helper. Accepted tests can't be lost, and failing tests are pruned one by one.
- **Strict acceptance:** a candidate is kept only if vet is clean, tests pass twice, and covered blocks strictly grow. Coverage never regresses.
- **The container is the only real isolation, and it is not a per-job sandbox.** The import/content guard is a best-effort filter, not a security boundary, and does not make generated code safe. Defense in depth: non-root, env allowlist (the API key is not passed to test processes, although code running as the same container user could still read it via `/proc`), best-effort import filter, timeouts with process-group kill, loopback-only ports. No Docker socket mount, because that would give the backend root-equivalent access to the host.
- **Token economy over generality:** a measured run showed that most Fixer calls were for mechanical errors (forgotten imports), so those are repaired without an LLM call, and the planner packs as many statements as fit into one prompt. See spec §6.7.
- **Groq only:** fast iterations; the cost is that reviewers need a key and rate limits shape run time on free keys. Output tokens are left uncapped by default (suited to a paid key).

## Limitations

- Expected values for floating-point code are partly characterization tests: when a generated assertion fails, the fixer may adopt the observed value if it's plausible. Real bugs may therefore be encoded rather than flagged; review generated assertions before trusting them.
- Generated tests run inside the backend container and could read files there (including the backend's environment via `/proc`) and start processes. The guard's rejection of `StartProcess` and `/proc/` is a cheap best-effort filter and is easy to bypass (string concatenation, reflection); it is not a sandbox. The real control for untrusted generated code is a per-job sandbox with a separate uid and no network (gVisor/Firecracker), listed as production future work.
- The repository's source code is sent to Groq.
- It's designed as a single-user local tool, so run history is persisted to disk (./output/<id>: events, report, tests, summary) and reloaded on startup. That's enough for one developer and needs no extra infrastructure. Multi-user history would need real authentication — not just an anonymous cookie, which only separates browsers and doesn't secure anything. With login in place I'd move run metadata and events to Redis or Postgres keyed by user, with ownership checks on every run endpoint and per-user uploads.
- Results depend on Groq rate limits and on the model; run time and final coverage vary between runs.

## AI usage

I used Claude Code as a pair programmer and implementation team. I set the direction and made the product and architecture decisions; Claude turned them into a detailed spec and plan and wrote the code. The assessment asks where AI was and wasn't used, so here is the split.

### What I decided before any detailed plan existed

- **Architecture.** Separate agents with a client/server split: a Next.js frontend and a FastAPI backend, run with Docker Compose. I chose FastAPI for the server side with production deployment in mind (run locally first, deploy to the cloud later).
- **LLM provider and model.** Groq, with `openai/gpt-oss-120b`.
- **The core idea.** An agent that plans, writes and executes unit tests and uses the execution results to decide what to do next. My first version gave the model terminal access; together we refined that into fixed, whitelisted Go commands and schema-checked JSON, so the model never gets a shell.
- **The process.** Spec first, then a task-by-task implementation plan, each reviewed repeatedly until the gaps were closed, then execution with an independent review of every task.

### Decisions I made during the build

- **Uncapped model output.** When Groq returned malformed JSON, I identified the output cap as the likely cause and had it removed.
- **The right API key.** I found that my first key was a free trial (8K tokens/min, 200K tokens/day), checked Groq's documentation, and switched to a Developer-plan key. That took the full run from a 28-minute partial result (69%) to 80.5% in under five minutes.
- **Token efficiency.** I chose to cut tokens per iteration, rather than adding a "continue a previous run" feature or relying on higher rate limits, so the tool stays usable on rate-limited keys. The data-driven changes that followed (a no-LLM repair step, larger targets per call) cut tokens per covered point by about 13%.
- **Cutting plan item size.** I saw `norm.go` stuck at 32.7% with model errors, traced it to plan items asking for answers too large to finish, and decided to cap items at 8 functions / 100 statements and split over-size answers. Later data from 366 targets (19 runs) showed that targets of 1 to 3 functions passed the first check 65% of the time, 4 to 5 functions 41%, and 6 to 8 functions 25%, so I lowered the cap to 5 functions; the before/after runs are in [Cap of 5 functions per target](#cap-of-5-functions-per-target-2026-10-09).
- **Proof that failing tests are not counted.** I asked for evidence, not an assurance. The final tests were re-run in a fresh clone and passed with 80.1%.
- **Fixing `make` for PowerShell.** `make test` failed on my machine, so I had the Makefile made shell-independent.
- **The UI gaps.** I found no theme switch, no way back to the start page, a one-line running banner, an unfinished navbar and no in-app explanation, and decided on the toggle, Run history panel, "← All runs", navbar and How it works page.
- **LLM quality over token savings.** I traced semver's `constraints.go` item, rejected after 6 attempts, asked why the LLM kept failing, and decided five changes: (1) give the Fixer the item's full attempt history, including the failures of tests that were pruned; (2) a Fixer rule to keep the tests that reached new lines and correct their expected values to the observed behaviour; (3) reasoning effort per role, with the old low-effort setting removed entirely; both roles now default to `medium`, because `high` was measured as too slow (a Fixer call was still waiting after ~114 s, against 9 s for a `medium` Writer call); (4) a Writer rule to trace parsing and regex logic step by step before asserting; (5) measuring the result on semver: 1.4% → 84.6% with nothing rejected, against 64.2% before the earlier fixes (see Results on Masterminds/semver).
- **Disk-based run history.** I chose to reload run history from `./output` on startup over a Redis/multi-user design, after weighing it against the assessment's scope: this is a single-user local tool, and real multi-user history needs authentication first.
- **Publishing and disclosure.** The wording of the per-file disclosure line and the pull-request workflow.

### What Claude did

- Proposed options and trade-offs at each decision point, and drafted the design spec and implementation plan from my direction. Each was reviewed by a separate AI reviewer and revised before I approved it.
- Wrote the code through subagents, one task at a time. A separate AI reviewer checked every task against the spec, with fix rounds until it passed.
- Ran the test suites and the live runs I approved, using the Groq keys I supplied. The numbers in [Results](#results-on-montanaflynnstats) come from those runs.

### What that means for the code

The code is AI-generated. I didn't hand-write it or review it line by line; I own the design, the decisions above, and the verified results. Every source file starts with a one-line comment saying how it was produced, and the full trail (spec, plan, measured runs) is in [`docs/superpowers/`](docs/superpowers/).
