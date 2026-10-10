<!-- AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas. -->
# go-coverage-agent

[![ci](https://github.com/LionelRoxas/go-coverage-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/LionelRoxas/go-coverage-agent/actions/workflows/ci.yml)

An autonomous agent that raises unit-test coverage for Go repositories. Give it a local Go module and a target percentage. It measures coverage, plans what to test, asks an LLM to write idiomatic Go tests, compiles and runs them, keeps only the tests that pass and add coverage, and repeats until it hits the target or gains flatten out.

<a href="docs/screenshots/gallery-summary.png"><img src="docs/screenshots/gallery-summary.png" width="100%" alt="Run page for montanaflynn/stats (run f910d155f3cd) showing 97.8% coverage against a 100% target, the Iteration limit reached card and the top of the AI summary"></a>

> **Scope, for reviewers.** This is a single-user tool that runs locally with Docker Compose. There are no accounts:
> whoever opens http://localhost:3000 sees every run. Run history is saved in `./output` and reloads when the app restarts.
> Supporting several users would need real authentication first; see [What I would do differently in production](#what-i-would-do-differently-in-production).

## Quick start

Requirements: Docker Desktop with Compose v2.24+. Node 22+ is needed only for `make test` / `make test-frontend`.

```bash
git clone https://github.com/LionelRoxas/go-coverage-agent.git && cd go-coverage-agent
# If you received a .env from me, put it in the repo root. Otherwise:
cp .env.example .env          # and paste your Groq key (https://console.groq.com/keys) into GROQ_API_KEY
make up                       # or: docker compose up --build
```

Open http://localhost:3000, click the **montanaflynn/stats** card under **Sample repos** (the assignment's evaluation repo), press **Next** to set a target (80% by default), **Skip (use defaults)** past the advanced options, then **Start**.

- **Model:** `openai/gpt-oss-120b` on Groq (fallback `openai/gpt-oss-20b` via `GROQ_MODEL`). `GET /api/health` and the UI show it.
- **Paid (Developer-plan) key:** a stats run to 80% takes about 5 minutes (287 s, 184,926 tokens, no rate-limit waits).
- **Free Groq key** (8K tokens/min, 200K tokens/day): uncomment the free-trial block in [`.env.example`](.env.example) (copied into your `.env`). Expect long "waiting for rate limit" pauses and possibly less than 80%: an earlier free-key run reached 69.0% in about 28 minutes. Plan on one run per key per day.
- Without a key the stack still starts and the UI shows a "No Groq API key configured" banner.
- **Ports:** set `BACKEND_PORT` / `FRONTEND_PORT` in `.env` (defaults 8000 / 3000). After changing `BACKEND_PORT`, rebuild with `make up`, because the frontend bakes the API URL in at build time.
- **Linux:** the backend runs as uid 1000; make `./repos` and `./output` writable by uid 1000 if your uid differs.
- **Apple Silicon:** all base images are multi-arch and an arm64 cross-build (`docker buildx --platform linux/arm64`) succeeds for both images; I have not run it on a Mac.

## Input: sample repos and your own code

Step 1 of the setup page has two tabs. **Sample repos** (the example data): six small, dependency-free Go libraries. Clicking one shallow-clones it into `./repos/<id>` (a pinned release tag; stats uses its default branch) and selects it.

| Sample | What it is | Licence |
|---|---|---|
| `montanaflynn/stats` | Statistics functions (the assignment's repo) | MIT |
| `Masterminds/semver` | Semantic version parsing and constraints | MIT |
| `huandu/xstrings` | String utilities | MIT |
| `dustin/go-humanize` | Human-friendly numbers, sizes and times | MIT |
| `google/btree` | In-memory B-tree (generics) | Apache-2.0 |
| `shopspring/decimal` | Arbitrary-precision decimals | MIT |

**Your folders** takes your own projects in two ways:

- **Upload:** press **Choose a folder…** (or drop the folder that contains `go.mod`). The files are saved under `./repos/uploads/<name>`. `.git`, `vendor`, `node_modules`, hidden files, binaries and files over 1 MB are skipped; at most 3,000 files and 25 MB (`UPLOAD_MAX_FILES`, `UPLOAD_MAX_BYTES`). An upload only replaces a folder an earlier upload created.
- **Host folder:** every Go module (up to two levels deep) in `HOST_REPOS_DIR` (default `./my-repos`) is listed as `host/<path>`. It is mounted **read-only** at `/host-repos`. Copy a project into `./my-repos` and press Refresh, or set `HOST_REPOS_DIR` to an absolute path (`C:\Users\you\code`, `/Users/you/code`; compose does not expand `~`) and run `make up`.

Your code is never modified. A run copies the module into the container's `/work/<job-id>` (deleted when the run ends), deletes the copy's existing `_test.go` files, works only on that copy, and writes the generated tests to `./output/<job-id>/tests/` for you to review. Every run is saved in `./output/<job-id>` (events, report, tests, summary) and Run history reloads it on restart; a run the app was shut down in the middle of shows as Interrupted. Delete the folder to remove a run.

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
│  volumes: ./repos ─▶ /repos (samples, uploads)   ./output ─▶ /output   │
│           ${HOST_REPOS_DIR:-./my-repos} ─▶ /host-repos (read-only)     │
└────────────────────────────────────────────────────────────────────────┘
```

The loop is plain, testable Python. The LLM writes and fixes tests and summarizes the finished run; nothing else uses it. The app explains the loop in plain language at `/how-it-works` and in technical detail at `/walkthrough`.

1. **Measure.** Copy the repo, delete existing `_test.go` files (default), measure baseline coverage with `go test -coverprofile`.
2. **Plan.** A deterministic planner ranks files by uncovered statements and picks up to 3 targets per round, each at most 5 functions / 100 uncovered statements of one file (no planning tokens).
3. **Write.** The Writer LLM gets the target functions with lines marked `// UNCOVERED` and returns new tests as schema-constrained JSON.
4. **Validate.** A Go AST helper appends the tests to `<source>_test.go`. The candidate must pass an import guard, `go vet` and `go test -count=2`, and the set of covered blocks must strictly grow.
5. **Repair.** Failing tests are pruned one by one; forgotten imports, unqualified identifiers and reused test names are fixed without an LLM call; anything else goes to the Fixer LLM with the item's attempt history (up to 2 tries). Rejected candidates are rolled back.
6. **Stop** on target reached, marginal gains (less than `min_gain` points for `patience` rounds), max rounds, no targets left, token budget, cancel, or Groq unreachable for 10 minutes (`llm_unavailable`). An outage never counts against a target: it shows as "Retried later (Groq unreachable)" and is planned again. Accepted tests are always saved.
7. **Summarize.** One more LLM call writes two summaries from the run's measured facts: one for stakeholders, one for engineering teams. A deterministic check drops any sentence whose numbers, files or test names are not in those facts. The run counts as busy until then (a new run can't start; Cancel stops only the summary). Saved as `SUMMARY.md` and `ai_summary` in `report.json`; it can be turned off in the advanced options.

## Results

All on a Developer-plan Groq key, each repo's own tests deleted first. Default options (20 rounds, min gain 1.0, 3 targets per round) unless noted.

**montanaflynn/stats**

| Run | Goal | Coverage | Rounds / time | Targets kept / rejected | Tokens | Stop reason |
|---|---|---|---|---|---|---|
| `89eb53b5907e` | 80% | 0.0% → 80.51% (1,247 statements) | 15 / 287 s | 41 / 4 | 184,926 | `target_reached` |
| `26598ee5c57b` (after the fixes below) | 80% | 0.0% → 80.75% | 12 / 248 s | 34 / 1 | 182,494 | `target_reached` |
| `f910d155f3cd` | 100% | 0.0% → 97.83% | 20 / 474 s | 60 / 0 | 337,689 | `max_iterations` |
| `0e1f8bf7442a` (up to 30 rounds, min gain 0.5) | 100% | 0.0% → 100.0% | 22 / 612 s | 64 / 1 | 403,322 | `target_reached` |

Independent check: the tests of `89eb53b5907e` were copied into a fresh clone with every `_test.go` removed; `go vet` was clean, all tests passed and plain Go measured **80.5%** (the same check on `ca1beb9a1fdb` gave 80.1%).

**Masterminds/semver** (goal 80%). It starts at 1.4%, not 0%, because its two `init()` functions run when the package loads.

| Run | Setup | Coverage | Rounds / time | Targets kept / rejected | Tokens |
|---|---|---|---|---|---|
| `acab3e3c7570` | before the prompt-budget and duplicate-name fixes | 1.4% → 64.2% (`marginal_gains`) | 8 / 130 s | 12 / 5 | 115.9K |
| `f9f3edcd9bfc` | after those fixes, one `low` effort for both roles | 1.4% → 80.1% | 4 / 75 s | 9 / 0 | 59.0K |
| `736baa413b5d` | after the Fixer-history fixes, Fixer `medium` | 1.4% → **84.6%** | 4 / 114 s | 8 / 0 | 82.6K |
| `d247037efdb2` | same, Fixer `low` | 1.4% → **84.4%** | 3 / 88 s | 7 / 0 | 69.2K |

The last two runs needed one LLM fix each (12.8 s at `medium`, 9.6 s at `low`), too close to rank the Fixer's effort. A Fixer call at `high` was still waiting after about 114 s, which is why both roles default to `medium`.

**Cap of 5 functions per target** (same settings, only the planner's cap changed from 8 to 5):

| | semver, cap 8 | semver, cap 5 | stats, cap 8 | stats, cap 5 |
|---|---|---|---|---|
| Run | `736baa413b5d` | `7a8c53c08bce` | `459dfe48a57f` | `e2de1ca387cb` |
| Coverage | 1.4% → 84.6% | 1.4% → 83.5% | 0% → 80.3% | 0% → 81.1% |
| Rounds / time | 4 / 114 s | 3 / 83 s | 10 / 276 s | 11 / 310 s |
| Passed on the first check | 2 of 8 (25%) | 4 of 7 (57%) | 23 of 28 (82%) | 27 of 31 (87%) |
| LLM fixes | 1 | 0 | 3 | 1 |
| Tokens | 82.6K | 54.5K | 172K | 175K |

With the cap of 5 more targets passed on the first check and fewer LLM fixes were needed; semver used 34% fewer tokens, stats about the same. These are single runs, so a few seconds or a percentage point is within normal variation.

**Parallel writers (2026-10-10)** (stats, cap of 5; within each comparison only `PARALLEL_WRITERS` changed).

Goal 80%, default options:

| | Sequential | Parallel |
|---|---|---|
| Run | `e2de1ca387cb` | `adb390243460` |
| Coverage | 0% → 81.07% (target reached) | 0% → 80.27% (target reached) |
| Rounds | 11 | 11 |
| Time | 310 s | 147 s (−53%) |
| Targets accepted / rejected | 31 / 0 | 33 / 0 |
| Passed on the first check | 27 | 25 |
| LLM fixes | 1 | 2 |
| Duplicate-name errors / renames | 0 / 0 | 0 / 0 |
| `no_gain` rejections | 0 | 0 |
| Rate-limit waits | 0 | 0 |
| Tokens | 175K | 187K |

Goal 100%, long run (30 rounds max, minimum gain 0.5 pp, 5 targets per round, 3 fix attempts):

| | Sequential | Parallel |
|---|---|---|
| Run | `979b912d00b4` | `73d630a6dd05` |
| Coverage | 0% → 99.84% | 0% → 99.68% |
| Rounds | 17 (stopped on small gains) | 17 (stopped on small gains) |
| Time | 681 s | 377 s (−45%) |
| Targets accepted / rejected | 78 / 0 | 75 / 1 |
| Passed on the first check | 61 | 55 |
| LLM fixes | 14 | 16 |
| Duplicate-name errors | 2 | 1 |
| `no_gain` rejections | 2 | 0 |
| Rate-limit waits | 0 | 0 |
| Tokens | 493K | 506K |

These are single runs: parallel writers cut the time roughly in half on both a short and a long run, with the same rounds and coverage within 0.8 pp, for 3–7% more tokens. `PARALLEL_WRITERS` is off by default and meant to be turned on for paid keys.

### Issues I found in testing and fixed

I had the system run end to end (Claude ran the live runs I approved), read the results, spotted these problems and decided the fixes. Claude Code implemented them under review.

| Symptom | Root cause | Fix | Evidence |
|---|---|---|---|
| Malformed-JSON errors from Groq (400 `json_validate_failed`) | The output cap left too little room after hidden reasoning tokens | Output allowance is the model maximum (65,536), clamped to the key's tokens/min limit | No JSON errors in later runs |
| A run took about 28 minutes and stopped at 69% | A free-trial key (8K tokens/min, 200K/day) | Developer-plan key; free-tier settings documented in `.env.example` | `a46c5a902f70`: 1,678 s, 68.97%, 46 rate-limit events; `89eb53b5907e`: 287 s, 80.51% |
| Model errors, `norm.go` stuck at 32.7% | Targets of 12 to 37 functions asked for answers too large to finish | Cap targets at 5 functions / 100 statements; split an over-size answer and retry | `ca1beb9a1fdb` → `26598ee5c57b`: 4 model errors → 0, `norm.go` 32.74% → 90.27% |
| Were failing tests counted toward coverage? | Not a bug: only candidates that pass twice and strictly add coverage are kept | Verified, no change | `ca1beb9a1fdb`'s tests re-run in a fresh clone: all pass, 80.1% |
| `make test` failed in PowerShell | The Makefile used `cat` and `VAR=x cmd` | Shell-independent Makefile | Passes in PowerShell, Git Bash and CI |
| No theme switch, no way back to the start page, a one-line running banner, no explanation of the loop | UI gaps | Theme toggle, Run history panel, "← All runs", How it works page | Screenshots below |
| semver stalled at 64.2% (prompt too large for the Fixer, duplicate test names) | A prompt cap from the free-trial era; existing test names crowded out | `MAX_PROMPT_TOKENS` 4,500 → 12,000; Fixer prompts shrink instead of failing; reused names renamed without an LLM call | `acab3e3c7570` 64.2% → `f9f3edcd9bfc` 80.1% |
| The Fixer kept repeating a wrong assertion (semver `constraints.go`, rejected after 6 attempts) | The Fixer saw only the latest check; effort was at its minimum | Five changes, listed under [AI usage](#decisions-i-made-during-the-build) | `736baa413b5d`: 84.6%, 0 rejected |
| A generated test asserted NaN/Inf-to-int results that differ between x86 and ARM, so it would fail on Apple Silicon | Go leaves out-of-range float-to-int conversion implementation-defined; the same test also locked in a behaviour the model had flagged as a suspected bug | Writer and Fixer prompt rules (no platform-dependent or suspected-bug assertions) plus a guard check that rejects `int(math.Inf(`, `int64(math.NaN())` and similar | Run `7e5223daa8e2`, `util_test.go`; re-run: re-run `73d630a6dd05` (same settings, goal 100%): 0% → 99.68%; NaN/Inf are now tested only for "does not panic", and the guard never had to fire |

## Screenshots

<table>
<tr><td valign="top" width="50%"><a href="docs/screenshots/gallery-setup.png"><img src="docs/screenshots/gallery-setup.png" width="100%" alt="New run page at step 1 of the wizard: the header, the four-step stepper, the Sample repos tab with montanaflynn/stats selected, and the Run history panel listing 31 runs"></a><br><b>New run, step 1:</b> the wizard beside Run history.</td><td valign="top" width="50%"><a href="docs/screenshots/gallery-runs-dark.png"><img src="docs/screenshots/gallery-runs-dark.png" width="100%" alt="The review step of the New run wizard and the Run history panel in the dark theme"></a><br><b>Review &amp; start</b>, dark theme.</td></tr>
<tr><td valign="top" width="50%"><a href="docs/screenshots/gallery-folders.png"><img src="docs/screenshots/gallery-folders.png" width="100%" alt="Step 1 of the New run wizard on the Your folders tab after uploading a copy of stats: the drop area, the upload result, the uploaded module selected and the HOST_REPOS_DIR note"></a><br><b>Your folders:</b> after uploading a local copy of stats.</td><td valign="top" width="50%"><a href="docs/screenshots/gallery-live.png"><img src="docs/screenshots/gallery-live.png" width="100%" alt="Run in progress at 17.2 percent with a Cancel button and the Activity list ending in a running item"></a><br><b>Run in progress</b>, with Cancel and the Activity list.</td></tr>
<tr><td valign="top" width="50%"><a href="docs/screenshots/gallery-chart.png"><img src="docs/screenshots/gallery-chart.png" width="100%" alt="Line chart of coverage after each of 11 iterations rising from 0 percent to the dashed 80 percent target line, with the Generated tests section below it"></a><br><b>Coverage by round</b> for the parallel-writers run of stats (<code>adb390243460</code>), above the generated tests.</td><td valign="top" width="50%"><a href="docs/screenshots/gallery-trace.png"><img src="docs/screenshots/gallery-trace.png" width="100%" alt="Expanded Activity item for histogram.go with three numbered attempts: rejected by the safety guard, one failing test after the LLM fix, then the failing test removed and the rest passing"></a><br><b>Attempt trace:</b> guard rejection, LLM fix, prune, accepted.</td></tr>
<tr><td valign="top" width="50%"><a href="docs/screenshots/gallery-testfile.png"><img src="docs/screenshots/gallery-testfile.png" width="100%" alt="Generated tests section with clip_test.go selected and highlighted Go code"></a><br><b>Generated tests</b>, syntax-highlighted.</td><td valign="top" width="50%"><a href="docs/screenshots/gallery-dark.png"><img src="docs/screenshots/gallery-dark.png" width="100%" alt="Iteration limit reached summary card and the AI summary below it, on the For stakeholders tab, in the dark theme"></a><br><b>Run page</b>, dark theme.</td></tr>
<tr><td valign="top" width="50%"><a href="docs/screenshots/gallery-summary-ai.png"><img src="docs/screenshots/gallery-summary-ai.png" width="100%" alt="The Summary section of run f910d155f3cd on the For stakeholders tab: a headline about coverage rising from 0.0% to 97.83%, then Outcome, Efficiency with an estimated cost, Risks and Recommendation, with Copy as Markdown and Write again buttons"></a><br><b>AI summary</b> for stakeholders, with the cost line.</td><td valign="top" width="50%"><a href="docs/screenshots/gallery-summary-tech.png"><img src="docs/screenshots/gallery-summary-tech.png" width="100%" alt="The same Summary section on the For engineering teams tab: what was tested, where the tests live, how to run them, and a table of the files with uncovered statements"></a><br><b>AI summary</b> for engineering teams.</td></tr>
<tr><td valign="top" width="50%"><a href="docs/screenshots/gallery-howitworks.png"><img src="docs/screenshots/gallery-howitworks.png" width="100%" alt="How it works page: the five steps of a run side by side, steps 2 to 5 marked as one round with an arrow back to step 2"></a><br><b>How it works</b>, in plain words.</td><td valign="top" width="50%"><a href="docs/screenshots/gallery-walkthrough.png"><img src="docs/screenshots/gallery-walkthrough.png" width="100%" alt="Walkthrough page with a table of contents that follows the run beside the Start a run section"></a><br><b>Walkthrough</b>, the technical version.</td></tr>
<tr><td valign="top" width="50%"><a href="docs/screenshots/gallery-setup-mobile.png"><img src="docs/screenshots/gallery-setup-mobile.png" width="100%" alt="The New run wizard at step 1 on a 390 pixel wide phone screen"></a><br><b>New run</b> on a phone.</td><td valign="top" width="50%"><a href="docs/screenshots/gallery-mobile.png"><img src="docs/screenshots/gallery-mobile.png" width="100%" alt="Run page on a 390 pixel wide phone screen"></a><br><b>Run page</b> on a phone.</td></tr>
<tr><td valign="top" width="50%"><a href="docs/screenshots/gallery-howitworks-mobile.png"><img src="docs/screenshots/gallery-howitworks-mobile.png" width="100%" alt="How it works page on a 390 pixel wide phone screen"></a><br><b>How it works</b> on a phone.</td><td></td></tr>
</table>

## Configuration

Job options (`POST /api/jobs`). The UI's advanced step exposes max iterations, min gain, files per iteration, fix attempts and the AI summary; the rest are API-only.

| Option | Default | Range |
|---|---|---|
| `target_coverage` | 80 | 1-100 |
| `max_iterations` | 20 | 1-30 |
| `min_gain` (percentage points per round) | 1.0 | 0-10 |
| `patience` | 2 | 1-5 |
| `targets_per_iteration` | 3 | 1-5 |
| `max_fix_attempts` | 2 | 0-4 |
| `delete_existing_tests` | true | bool |
| `max_llm_tokens` (per job) | 1,000,000 | 10K-2M |
| `exclude_patterns` (module-relative globs) | `["examples/**", "testdata/**"]` | list |
| `write_summary` (AI summary after the run) | true | bool |

Environment (`.env`; only the key is required). [`.env.example`](.env.example) documents every variable with its default.

| Variable | Default | Meaning |
|---|---|---|
| `GROQ_API_KEY` | (empty) | Needed to start a job |
| `GROQ_MODEL` | `openai/gpt-oss-120b` | `openai/gpt-oss-20b` is cheaper and weaker |
| `GROQ_WRITER_REASONING_EFFORT` / `GROQ_FIXER_REASONING_EFFORT` | `medium` / `medium` | `low` also works; `high` is accepted but too slow. An answer cut off for length is retried one level lower |
| `PARALLEL_WRITERS` | false | Send each round's writer requests at once; validation stays one at a time, in plan order. Faster on paid keys, no gain on free-trial keys (8K tokens/min). A round can spend tokens on answers that are never checked once the goal is reached mid-round |
| `BACKEND_PORT` / `FRONTEND_PORT` | 8000 / 3000 | Host ports (loopback only) |
| `HOST_REPOS_DIR` | `./my-repos` | Your Go projects, mounted read-only at `/host-repos` |
| `DAILY_TOKEN_BUDGET` | 2,000,000 | The app's own daily cap (not a Groq limit), counted in `output/.usage.json`, reset at midnight UTC |
| `GROQ_PRICE_INPUT_PER_M` / `GROQ_PRICE_OUTPUT_PER_M` | (unset) | USD per 1M tokens; when both are set the AI summary shows an estimated cost. `.env.example` sets 0.15 / 0.60 |
| Free-trial key: `DAILY_TOKEN_BUDGET` / `MAX_PROMPT_TOKENS` / `CALL_TOKEN_RESERVATION` | 2,000,000 / 12000 / 16000 | Set to 190000 / 4500 / 8000 |

Advanced settings (Groq timeout and output cap, outage window, per-stage Go timeouts, upload limits, history size) are listed with their defaults in `.env.example`. `MIN_DAILY_TOKENS_TO_START` (20,000) and `MAX_OUTPUT_CHARS` (20,000 characters of command output kept) are also read, mainly for tests.

## Running the tests

```bash
make test   # everything: Go helper, backend unit + integration (in Docker), frontend; or test-go, test-backend, test-integration, test-frontend
make lint   # ruff (backend, in Docker), eslint + tsc --noEmit (frontend); or lint-backend, lint-frontend
```

CI (`.github/workflows/ci.yml`) runs these targets, the lint targets and `make build-frontend`. Backend tests run in the image's `test` stage (`gca-backend-test`: dev dependencies and tests); the default `runtime` stage that compose runs has neither. `test-integration` runs the container with the same hardening as compose (below). Without `make` (Git Bash; Go runs in Docker):

```bash
export MSYS_NO_PATHCONV=1
docker run --rm -v "$PWD/tools/gohelper:/src" -w /src golang:1.27-bookworm sh -c "go vet ./... && go test ./..."
docker build -f backend/Dockerfile --build-arg GO_IMAGE=golang:1.27-bookworm --target test -t gca-backend-test .
docker run --rm gca-backend-test pytest
docker run --rm --cap-drop ALL --security-opt no-new-privileges:true --pids-limit 512 --memory 4g --read-only \
  --tmpfs /tmp:exec --tmpfs /work:exec,uid=1000,gid=1000 --tmpfs /home/app/.cache:exec,uid=1000,gid=1000 \
  --env-file .env.example -v "$PWD/backend/tests/fixtures:/host-repos:ro" gca-backend-test pytest -m integration
docker run --rm gca-backend-test ruff check --no-cache .
cd frontend && npm ci && npm test && npm run lint && npx tsc --noEmit
```

**Security scanning (GitHub Actions):** CodeQL (`codeql.yml`, security-extended queries for Python, TypeScript, Go and the workflows), Trivy (`trivy.yml`, dependencies, secrets and Dockerfile misconfigurations in the repo plus the built backend image; report-only), and Dependabot (`.github/dependabot.yml`, weekly grouped updates). Findings appear under the repository's Security tab.

## Why Groq instead of a local model

The brief allows a hosted LLM as well as LocalAI/Ollama. `openai/gpt-oss-120b` is an open-weight model, the same family Ollama ships as `gpt-oss:20b`, served fast on Groq: a stats run to 80% takes about 5 minutes. CPU-only inference on a Mac without a GPU would be far slower (I did not measure it). The trade-off is that you need a key (or the `.env` I send) and the code under test is sent to Groq (see [Limitations](#limitations)). Pointing it at a local OpenAI-compatible endpoint would mean replacing the Groq client; that is listed as future work.

## Design decisions and trade-offs

- **Deterministic loop; the LLM only writes and fixes tests and writes the end-of-run summary** (structured JSON, no tool calls, no shell). Why: reliability, token cost, testability, safety.
- **Append-only test generation** through a small Go AST helper: accepted tests can't be lost, and failing tests are pruned one by one.
- **Strict acceptance:** vet clean, tests pass twice, covered blocks strictly grow. Coverage never regresses.
- **Token economy:** mechanical errors (forgotten imports, reused names) are repaired without an LLM call, and the planner packs up to 5 functions / 100 uncovered statements of one file into each call.
- **The model predicts expected values; the Go runtime decides.** I considered a "record mode" where the LLM only chooses inputs and the system runs the function to capture the outputs as expected values. It would remove wrong-prediction failures and fixer calls, but every test would then agree with the code by construction and could never catch a bug. I kept the prediction as a weak, independent oracle: when it disagrees with the code, the Fixer adopts the observed value unless it contradicts the function's documentation, in which case the case is dropped and reported as a suspected bug. Suspected bugs are leads, not verdicts: a refuted one (stats `Mode`, run f910d155f3cd) once reached the report, so claims the runtime disproves are now dropped.
- **Defense in depth, not a sandbox:** non-root user that cannot write the app code or its Python environment (both root-owned; the root filesystem is read-only), all capabilities dropped, no-new-privileges, pids and memory limits, env allowlist (the key is not passed to test processes), a best-effort import guard, timeouts with process-group kill, loopback-only ports, no Docker socket mount.

## What I would do differently in production

- **Per-run sandbox:** run each test in a throwaway container with `network: none` and no secrets, instead of the backend container plus a best-effort guard and an unprivileged user.
- **Auth and storage:** real authentication, then per-user runs in Postgres/Redis with ownership checks, instead of one user's history on disk.
- **Secrets** in a secret manager, not a `.env` file.
- **A job queue with workers** instead of one in-process job at a time.
- **Observability:** structured logs, metrics and traces instead of the event log alone.
- **Supply chain:** pinned image digests and dependency hashes, plus an SBOM.
- **Per-user rate limits and token budgets** instead of one app-wide daily budget.
- **LLM endpoint:** a configurable OpenAI-compatible base URL, so a local model or a private deployment can replace Groq.
- **Cheaper corrections:** patch simple mismatches (numbers, strings, booleans, error vs nil) from Go's own "got X, want Y" output without an LLM call, and keep the LLM fixer for suspicious cases (doc contradictions, NaN, panics).

## Limitations

- Generated tests run inside the backend container as the same user (uid 1000) as the API server. They cannot modify your code (`HOST_REPOS_DIR` is read-only) or the app itself: the app code and its Python environment are owned by root and the root filesystem is read-only, compose drops all capabilities, sets no-new-privileges and limits the container to 512 processes and 4 GB of memory. They could still read the backend's environment (including `GROQ_API_KEY`, via `/proc`), write to the app's data folders (`/repos`, `/output`, `/work`, the Go cache), start processes within those limits, and reach the network (outbound access is open). A separate runner per test run, with no network and without the key, is production work (above). The import guard is easy to bypass (string concatenation, reflection).
- **Privacy:** the functions under test and related declarations (your source code) are sent to Groq in each prompt. The New run flow does not show this notice; the How it works and Walkthrough pages describe it.
- Expected values for floating-point code are partly characterization tests: the Fixer may adopt an observed value, so real bugs can be encoded rather than flagged. Review generated assertions before trusting them.
- Single-user by design: no accounts, and history lives in `./output`.
- Run time and final coverage vary between runs and with the key's rate limits. Tokens billed for failed calls count toward the run.
- Most cited runs live in the gitignored `./output`; only `e2de1ca387cb` and `fc080d7fc500` are committed (as backend test fixtures).

## AI usage

I used Claude Code as a pair programmer and implementation team. I set the direction and made the product and architecture decisions; Claude turned them into a spec and plan and wrote the code.

### What I decided before any detailed plan existed

- **Architecture.** A Next.js frontend and a FastAPI backend with Docker Compose; FastAPI with a later cloud deployment in mind.
- **LLM provider and model.** Groq, with `openai/gpt-oss-120b`.
- **The core idea.** An agent that plans, writes and runs unit tests and uses the results to decide what to do next. My first version gave the model terminal access; together we refined that into fixed, whitelisted Go commands and schema-checked JSON.
- **The process.** Spec first, then a task-by-task plan, each reviewed until the gaps were closed, then execution with an independent review of every task.

### Decisions I made during the build

- **Uncapped model output.** When Groq returned malformed JSON, I identified the output cap as the likely cause and had it removed.
- **The right API key.** I found my first key was a free trial, checked Groq's documentation and switched to a Developer-plan key: from a 28-minute partial result (69%) to 80.5% in under five minutes.
- **Token efficiency.** I chose to cut tokens per round rather than add a "continue a previous run" feature; the changes that followed (a no-LLM repair step, larger targets per call) cut tokens per covered point by about 13%.
- **Smaller targets.** I saw `norm.go` stuck at 32.7% with model errors and had targets capped at 8 functions with over-size answers split. Later data across the earlier runs showed targets of 1 to 3 functions passed the first check about two times in three and 6 to 8 functions about one in three, so I lowered the cap to 5 (see the cap-of-5 table).
- **Proof that failing tests are not counted.** I asked for evidence, not an assurance: a fresh-clone re-run passed with 80.1%.
- **Fixing `make` for PowerShell**, and the **UI gaps** (theme toggle, Run history, "← All runs", How it works page).
- **LLM quality over token savings.** I traced semver's `constraints.go` item, asked why the Fixer kept failing, and decided five changes: (1) give the Fixer the item's full attempt history; (2) keep the tests that reached new lines and correct their expected values to the observed behaviour; (3) a reasoning effort per role, replacing the single `GROQ_REASONING_EFFORT` (then `low`), with both roles at `medium` because `high` was too slow; (4) a Writer rule to trace parsing logic before asserting; (5) measure it on semver: 64.2% before the earlier fixes, 84.6% after, nothing rejected.
- **Prediction over record mode.** I weighed letting the runtime record expected values instead of the model predicting them, and kept prediction so the tests keep a chance of catching bugs.
- **Disk-based run history** over a Redis/multi-user design, given the single-user scope.
- **Hosted model, README-only privacy notice.** Groq rather than a local model (see [Why Groq](#why-groq-instead-of-a-local-model)), and the "code is sent to Groq" notice kept in this README rather than the UI.
- **Publishing and disclosure.** The per-file disclosure wording and the pull-request workflow.

### What Claude did

- Proposed options and trade-offs at each decision point, and drafted the spec and plan from my direction; each was reviewed by a separate AI reviewer and revised before I approved it.
- Wrote the code through subagents, one task at a time; a separate AI reviewer checked every task, with fix rounds until it passed.
- Ran the test suites and the live runs I approved, with the Groq keys I supplied.

### What that means for the code

The code is AI-generated. I did not hand-write it, and I did not read every generated line. I reviewed it by deciding the stack, approving the spec and plan, reviewing every task's review findings and fix rounds, making the product calls above, and verifying the behaviour through the test suites and live runs. I own the design, those decisions and the verified results.

Every source and config file starts with a one-line comment saying how it was produced (`#`, `//` or `<!-- -->`): "AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas." The LLM prompt files carry it as an HTML comment that is stripped before the prompt is sent. Exempt: files that can't hold a comment (`package.json`, `package-lock.json`, `uv.lock`, `.go-version`), the empty `.gitkeep` markers, the screenshots, the test fixtures in `backend/tests/fixtures/` (test data, some copied from real runs), and the spec and plan in [`docs/superpowers/`](docs/superpowers/), which Claude drafted as described above.
