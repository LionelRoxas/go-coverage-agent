# Go Coverage Agent — Design Spec

- **Date:** 2026-10-08
- **Status:** Draft v2 (revised after independent review) — awaiting your approval
- **Working name:** `go-coverage-agent` (rename to match the GitHub repo once it exists)
- **Source requirements:** `take-home-assignment-spectro-cloud.pdf`

---

## 1. Intent

### 1.1 What we are building

An autonomous system that takes a **local Go repository** and a **target coverage percentage**, then loops on its own: measure coverage → plan what to test → have an LLM write idiomatic Go unit tests → compile, run and validate them → keep only tests that pass and add coverage. It stops when the target is met or further gains become marginal. A browser UI shows the run live and presents the results.

### 1.2 Who it is for

| Audience | What they need |
|---|---|
| Spectro Cloud hiring team (primary) | Clone the repo, follow the README, `docker compose up`, run against `montanaflynn/stats`, and see coverage reach the target in the browser |
| The candidate (you) | A codebase you can explain and defend in a follow-up interview: clear boundaries, tests, documented trade-offs, disclosed AI usage |

### 1.3 Success criteria

1. Starting from `montanaflynn/stats` with **every `_test.go` deleted**, a run with target 80% finishes at or above 80% coverage. All generated tests compile, pass twice, and pass `go vet`.
2. Fully autonomous after the user clicks **Start**: no prompts, no manual steps.
3. `docker compose up --build` starts everything on macOS ARM (no GPU) plus a `GROQ_API_KEY` in `.env`.
4. Results are viewable in the browser: live progress, coverage over iterations, per-file before/after, and the generated test code.
5. The project's own code has unit tests (Python backend, Go helper, frontend logic), runnable with one command each.
6. The README explains purpose, setup, required model name, example input, architecture, trade-offs, and AI usage.
7. **The end-to-end run on `stats` works by day 3** of implementation. Everything after that is polish and can be cut.

### 1.4 Decisions already made

| Decision | Choice | Rationale |
|---|---|---|
| LLM provider | **Groq only** | Fast inference keeps the write → run → fix loop short. Trade-off: reviewers need a Groq API key (free tier works within limits, §6.7). Documented prominently |
| Backend | **Python 3.12 + FastAPI** | Allowed language; good fit for orchestration and subprocess control |
| Frontend | **Next.js (TypeScript)** | Allowed language; polished UI is explicitly graded |
| Packaging | **docker compose** | Required by the assessment |
| Deployment | **Local only for v1** | Reviewers run it locally. Hosting is future work (§11) |

### 1.5 Assumptions (correct if wrong)

- Roughly 7 calendar days, part-time.
- Reviewers will create a free Groq key if the README tells them to.
- Optimized for `stats` (single flat package, stdlib only), but nothing is hard-coded to it.

---

## 2. Requirements traceability

| Assessment requirement | Where it is satisfied |
|---|---|
| Analyze codebase, find coverage gaps | §5.3 coverage analyzer, §5.4 `gohelper funcs` |
| Generate meaningful, idiomatic Go tests with an LLM | §6.3 Writer, §6.6 idiom rules |
| Validate: compile, pass, increase coverage | §5.6 validator, §7.3 acceptance rules |
| Iterate until threshold or marginal gains | §7.1 loop, §7.5 stop policy |
| Inputs: local repo path + desired coverage % | §8 `POST /api/jobs`, §9 run form, §10 mounts |
| Plan → write → execute → iterate, fully autonomous | §7 — no human step between Start and Done |
| Use `montanaflynn/stats`, delete existing `_test.go` | §5.2 `delete_existing_tests` (default on), §8 sample repo button |
| Containerized; docker run/compose | §10 |
| Share the model name | README, `/api/health`, UI footer: `openai/gpt-oss-120b` |
| Unit tests for own code | §12 |
| README with example input | §13 |
| Results in browser, polished UX | §9 |
| Disclose AI usage | §13.2 |

The weakest row is "coverage met based on input", because it depends on Groq's token limits. §6.7 is the risk plan for that.

---

## 3. Architecture overview

```
┌──────────────────────────── docker compose ────────────────────────────┐
│                                                                        │
│  ┌──────────────┐   HTTP + SSE    ┌──────────────────────────────────┐ │
│  │  frontend    │ ──────────────▶ │  backend (FastAPI)               │ │
│  │  Next.js     │ 127.0.0.1:8000  │                                  │ │
│  │  :3000       │                 │  API ─▶ JobManager ─▶ Orchestrator │
│  └──────────────┘                 │            │        │       │    │ │
│                                   │      Planner    Writer/Fixer  Validator
│                                   │   (deterministic)  (LLM)     (go tools)
│                                   │                     │          │  │ │
│                                   │               LLM client   gohelper│
│                                   │                     │       go test│
│                                   │                  Groq API   go vet │
│                                   │                             gofmt  │
│                                   │   Workspace: /work/<job>/repo (copy)│
│                                   └──────────────────────────────────┘ │
│  volumes: ${HOST_REPOS_DIR:-./repos} ─▶ /repos   ./output ─▶ /output    │
└────────────────────────────────────────────────────────────────────────┘
```

### 3.1 Key choice: deterministic orchestration, LLM only where judgment is needed

The loop (measure, plan, validate, prune, accept/reject, stop) is plain, testable Python. The LLM does two narrow jobs:

- **Writer:** write *new* test functions for chosen targets, plus the test ideas behind them.
- **Fixer:** repair new test functions that fail to compile, fail assertions, or add no coverage.

Each LLM call returns **schema-constrained JSON** via Groq Structured Outputs (`strict: true`), not free-form tool calls. Why:

- **Reliability:** constrained decoding gives schema-valid JSON. Truncation and API errors are still handled (§5.7).
- **Token economy:** Groq's limits are tight (§6.7), and multi-turn tool loops re-send context on every turn.
- **Testability:** each agent is a function `(inputs) -> typed output`, trivially faked in unit tests.
- **Safety:** the LLM never gets a shell. Only fixed, whitelisted commands run (§10.3).

This replaces the earlier idea of giving the LLM a terminal through tool calling. The system still plans, writes and executes; execution is done *for* the LLM by a deterministic validator, and the outcome is fed back to it.

### 3.2 Key choice: append-only test generation

The LLM never rewrites a test file. It returns **new test functions plus the imports they need**. A Go helper (`gohelper merge`, using `go/ast`) merges them into `<source>_test.go`. Consequences:

- Previously accepted tests can't be lost or silently changed.
- Output tokens are spent only on new code.
- Failing individual tests can be removed deterministically (`gohelper prune`) instead of discarding the whole candidate.

### 3.3 Key choice: no Docker-in-Docker sandbox

The backend container already isolates execution from the host. Untrusted generated test code runs as a non-root user, on a throwaway copy of the repo, with an env allowlist, timeouts, process-group kill and an import guard (§10.3). Mounting the Docker socket would give the backend root-equivalent host access on reviewers' Macs, which is worse than what it buys. This is documented as a trade-off, and a per-run sandbox is listed as production follow-up (§11).

---

## 4. Tech stack

| Layer | Choice | Notes |
|---|---|---|
| Backend | Python 3.12, FastAPI, Uvicorn, Pydantic v2 | `uv` for dependencies |
| LLM SDK | `groq` (official Python SDK), `AsyncGroq` | Uses `.with_raw_response` to read rate-limit headers |
| Streaming | `sse-starlette` | |
| Go toolchain | Official `golang` image, pinned to the current stable 1.x tag (verified at implementation) | Copied into the backend image |
| Go helper | `gohelper` CLI (`go/parser`, `go/ast`, `go/format`) | Subcommands `funcs`, `merge`, `prune`, `decls` (§5.4) |
| Frontend | Next.js (App Router), TypeScript, Tailwind CSS, Shiki (Go highlighting), Recharts (one chart) | |
| Tests | pytest + pytest-asyncio; `go test`; Vitest | §12 |

**Model:** `openai/gpt-oss-120b`, a Groq production model with 131K context, strict Structured Outputs, and a `reasoning_effort` parameter. It's configurable with `GROQ_MODEL`. The documented fallback is `openai/gpt-oss-20b`, which costs fewer tokens and runs faster but writes lower-quality tests.

---

## 5. Backend components

Each unit has one purpose and a narrow interface, and it can be tested on its own.

### 5.1 `config`

Pydantic `BaseSettings` from env:

- `GROQ_API_KEY` (required to start jobs), `GROQ_MODEL`, `GROQ_WRITER_REASONING_EFFORT` (default `medium`) and `GROQ_FIXER_REASONING_EFFORT` (default `medium`): the `reasoning_effort` sent for each role (`low`, `medium` or `high`; `medium` and `low` are the practical choices). Both roles default to `medium`: `high` was measured as too slow (job `86b6d88b558c`: a `high` Fixer call was still waiting after about 114 s, against 9 s for the `medium` Writer call), and remains accepted. The former single `GROQ_REASONING_EFFORT` was removed; if it is still in a `.env`, it is ignored.
- `GROQ_TIMEOUT_S` (default 240): how long one Groq request may take. A timed-out request is retried once at reasoning effort `low`; if that also times out, the item fails as `llm_timeout` ("Groq did not answer within 240 s, twice") (§5.7).
- `GROQ_MAX_COMPLETION_TOKENS` (default 65536, sent as `max_completion_tokens`; set it empty to send no cap), `CALL_TOKEN_RESERVATION` (default 16,000: tokens reserved per call for daily-ledger checks and TPM pacing, never sent to Groq; for accurate pacing it should be at least `MAX_PROMPT_TOKENS` plus the expected answer, so free-trial keys set 8,000), `DAILY_TOKEN_BUDGET` (default 2,000,000 for a paid plan; free-tier keys should set `DAILY_TOKEN_BUDGET=190000`)
- `MAX_PROMPT_TOKENS` (default 12,000: the estimated prompt cap per call; free-trial keys with 8K tokens/min should set 4,500 so prompt plus completion fit in one minute's allowance)
- `GROQ_PRICE_INPUT_PER_M` and `GROQ_PRICE_OUTPUT_PER_M` (USD per 1M input / output tokens, unset by default): when both are set, the end-of-run summary includes an estimated cost (§6.8); unset means no cost is shown anywhere.
- `REPOS_DIR=/repos`, `OUTPUT_DIR=/output`, `WORK_DIR=/work`
- loop defaults (§7.4), command timeouts, `CORS_ORIGINS=["http://localhost:3000"]` (JSON list; set by docker-compose from `FRONTEND_PORT`, and the compose value overrides `.env`)

The app starts without a key. `/api/health` reports `llm_configured: false`, and the UI shows a setup banner instead of a dead page.

### 5.2 `workspace`

- `create(job_id, repo_path)`: resolves `repo_path` relative to `REPOS_DIR`, rejects anything that resolves outside it (path-traversal guard), and requires `go.mod`. It copies to `WORK_DIR/<job_id>/repo`, excluding `.git`. **The source repo is never written to.**
- `delete_existing_tests()`: removes every `*_test.go` in the copy and returns the list.
- `snapshot(paths)` / `restore(snapshot)`: records content **or absence** for each path. Restore rewrites or deletes. Snapshots always include `go.mod` and `go.sum`.
- Writes are atomic (temp file + rename), restricted to `*_test.go` paths inside the workspace. Any other path raises.

### 5.3 `coverage` (pure Python)

- `parse_profile(text) -> list[Block]`: parses the `go test -coverprofile` format (`mode:` header; `file:sl.sc,el.ec numStmts count`). Blocks are keyed by `(file, range)`, and duplicates are OR-merged defensively. Without `-coverpkg` they shouldn't occur, because external `_test` files count toward their package.
- **Denominator guarantee:** a package with zero tests must still contribute all its statements as uncovered, and Go versions differ in how they report "no test files" packages. To be version-independent, the workspace writes a **seed file** `zz_coverage_seed_test.go` containing only the package clause into every included package directory that has no `_test.go`. The package then always builds a test binary and the profile lists every block, at count 0. Seed files are never exported as artifacts.
- `summarize(blocks, functions) -> CoverageReport`:
  - total % = covered statements / all statements (matches the `go tool cover -func` total)
  - per file and per function: statements, covered, %, uncovered line ranges
  - `covered_block_ids: set` (used by acceptance, §7.3)
- Functions are keyed by **`FuncKey = (file, receiver, name)`** everywhere. For example, `stats` has both `Mean` and `Float64Data.Mean`.

### 5.4 `gohelper` (Go CLI built into the image)

| Subcommand | Input → output | Purpose |
|---|---|---|
| `funcs <dir>` | → JSON `[{file, package, receiver, name, start_line, end_line, exported}]` for non-test files | Coverage-to-function attribution; extracting function source for prompts |
| `decls <dir>` | → JSON list of top-level identifiers declared in `_test.go` files | Tells the Writer which names already exist (avoids `redeclared`) |
| `merge <test_file> <snippet_file>` | Merges new funcs/types/vars and imports into the test file (creates it with the package clause if absent); `go/format` output; rejects a snippet declaring an identifier that already exists | Append-only writes |
| `prune <test_file> <names...>` | Removes the named top-level test functions and drops now-unused imports | Deterministic removal of failing tests |

It's written in Go because Python can't reliably parse Go, and `go/ast` can. It has its own unit tests.

### 5.5 `gotools`: the only code that runs commands

`run(argv, cwd, timeout)` uses `asyncio.create_subprocess_exec` with argument lists (never a shell) and `start_new_session=True`. On timeout or cancel it **kills the whole process group** (`os.killpg`), which also stops the test binary that `go` spawned. Output is truncated to a cap.

- **Environment allowlist** (not inherited): `PATH`, `HOME`, `GOCACHE`, `GOMODCACHE`, `GOFLAGS=-mod=readonly`, `GOTOOLCHAIN=local`, `CGO_ENABLED=0`, `GOPROXY` (default), `TMPDIR`. **`GROQ_API_KEY` is never passed to test processes** (code running as the same container user could still read it via `/proc`; see §10.3).
- `GOTOOLCHAIN=local`: a repo whose `go` directive is newer than the image's Go fails fast with a clear `job_failed` message.

| Wrapper | Command |
|---|---|
| `list_packages()` | `go list -json ./...` → includes import path, dir, name. Excludes `main` packages and packages whose **module-relative path** matches an `exclude_patterns` glob (default `examples/**`, `testdata/**`) |
| `test(pkgs)` | `go test -count=2 -covermode=set -coverprofile=<tmp> -timeout=60s <pkgs>` (the one test command, used for baseline and validation) |
| `compile(pkgs)` | `go test -count=1 -run=^$ <pkgs>` |
| `vet(pkgs)` | `go vet <pkgs>` |
| `gohelper(...)` | §5.4 |
| `go_directive()` | reads `go` version from `go.mod` (parsed in Python) |

### 5.6 `validator`

`validate(workspace, test_file, prev_report) -> ValidationResult`, failing fast in this order:

1. **Static guard** (§10.3) on the snippet: imports allowlist, no `//go:build`/`// +build` lines, size cap.
2. **Merge** via `gohelper merge`. A parse error or duplicate identifier → `compile_error` (with the helper's message).
3. **Compile check:** `go test -count=1 -run=^$ <pkgs>` builds the test binaries and runs no tests. A non-zero exit → `compile_error` (this also catches the vet subset `go test` runs automatically).
4. `go vet <pkgs>`. A non-zero exit → `vet_error`. Because compilation already passed, the classification is unambiguous.
5. `go test` (§5.5). On failure, parse `--- FAIL: TestName` lines → `test_failure{failed_tests, output}`. A panic or timeout → `test_failure` with all new tests marked failed.
6. Parse the profile → new report. If `covered_block_ids` is not a **superset** of `prev_report`'s, or no new block is covered → `no_gain`.
7. Otherwise `accepted{report, new_tests}`.

Formatting needs no separate step: `gohelper merge` writes `go/format` output, and syntax errors surface at the merge as `compile_error`.

### 5.7 `llm`: Groq client wrapper

- `complete(role, system, user, schema) -> (parsed, Usage)` with `response_format = json_schema, strict: true`, `reasoning_effort` from the role's setting (§5.1), and an explicit `max_completion_tokens` (`GROQ_MAX_COMPLETION_TOKENS`, default 65536, the model maximum; omitting the field does not mean unlimited, because Groq then applies a smaller undocumented default that truncated long answers). A truncated answer (after the lower-effort retries) or a persistent `json_validate_failed` raises `LLMOutputTooLarge`, which the orchestrator handles by retrying with the first half of the item's functions (§6.7). The prompt estimate is chars/3.5, conservative. If the prompt alone exceeds `MAX_PROMPT_TOKENS` (default 12,000; 4,500 for free-trial keys), the context builder must have trimmed it already (§6.1); the client asserts this. The completion allowance is fitted to the key's tokens-per-minute limit (`x-ratelimit-limit-tokens`): `min(configured, limit - prompt - 256)`, floor 1024, and a request-size rejection (413 / "Request too large") is retried once with the clamped value before failing with guidance to lower `GROQ_MAX_COMPLETION_TOKENS` (and, on a free-trial key, to set `MAX_PROMPT_TOKENS=4500`: with an 8K TPM limit, a prompt above about 6,700 tokens leaves less than the 1,024-token completion floor).
- **Schema normalizer** `to_strict_schema(model) -> dict`: converts Pydantic JSON Schema to Groq strict rules. All properties go into `required`, `additionalProperties: false` on every object, Optional → `["T","null"]`, and unsupported keywords (`default`, `title`, `maxItems`, `minLength`) are stripped. Limits are enforced **after** parsing. It's unit tested.
- **Failure handling:**
  - `finish_reason == "length"` (truncated, often from reasoning tokens) → automatic step-down: retry one effort level lower (`high` → `medium` → `low`). A truncation at the bottom of that step-down fails the item, since an identical retry would just re-spend the tokens. The effort a call actually used is reported as `llm_call.reasoning_effort`.
  - **Cancellation:** the client receives the job's cancel event, so a cancel interrupts a rate-limit pause or an in-flight request immediately.
  - 400 schema errors → fail the item, log, continue the loop.
  - 5xx/network → exponential backoff, max 3.
  - **Timeout:** each request may take `GROQ_TIMEOUT_S` (default 240 s). After a timeout the request is retried **once at reasoning effort `low`**, whatever the role's configured effort, since the lowest effort answers fastest; the retry emits its own `llm_request` (effort `low`), so the UI's wait restarts, and it is not a fix attempt (it happens inside one `complete` call). A second timeout raises `LLMTimeout`; the orchestrator records it as `validation_result.kind = llm_timeout` with the output "Groq did not answer within 240 s, twice", and the UI labels it "Groq timed out". The worst case per call is therefore about 2 × `GROQ_TIMEOUT_S`. Two side effects: `APITimeoutError` also covers connection (connect-phase) timeouts, which were formerly retried as network errors and now follow this rule; and the SDK's float timeout is a per-phase httpx limit (the read limit is the time between bytes), which for these non-streaming calls behaves as roughly the total time.
  - **Visible waits:** `complete` takes an `on_request(effort)` hook, called right before each request to Groq (also after a retry or an effort step-down); the orchestrator uses it to emit `llm_request` (§5.8).
- **Rate limiting:**
  - Before each call, if `x-ratelimit-remaining-tokens` (from the previous response) is less than the call's token reservation, sleep until `x-ratelimit-reset-tokens`, emitting a `rate_limited{seconds, reason:"tpm"}` event.
  - On 429: if `retry-after ≤ 90s`, sleep and retry (max 5) with an event. If it's longer, treat it as the **daily cap**: stop the job with `budget_exhausted` and a clear message. Never hang silently.
- **Usage tracking:** per-job token totals in events. A small **daily usage ledger** at `/output/.usage.json`, keyed by UTC date, stops a job before it starts if the remaining daily budget is under 20K, and the UI shows "~N tokens left today".
- `LLMClient` Protocol, so tests inject `FakeLLM`.

### 5.8 `jobs` and `events`

- `Job`: id, inputs, status (`running|completed|failed|cancelled`), ordered `events`, latest `CoverageReport`, `Summary`.
- `Event`: `{seq, ts, type, data}`. Types: `job_started`, `workspace_ready`, `baseline_measured`, `iteration_started`, `plan_created`, `llm_request` (`{index, file, role, reasoning_effort, attempt?}`, emitted right before each Groq request; `attempt` is the fix attempt for the Fixer; the UI shows "Waiting for Groq · fixer · medium reasoning · 1m 42s" on the waiting step, the item's status and the activity line until the matching `llm_call`, a `validation_result`, a `rate_limited` pause or the end of the job; older logs lack it and render as before), `llm_call` (`{index, file, role, prompt_tokens, completion_tokens, total_tokens, reasoning_effort}`; `reasoning_effort` is the effort the answer was produced at, after any step-down; older logs lack it), `rate_limited`, `candidate_generated`, `validation_result`, `tests_pruned`, `mechanical_repair` (`{index, file, repair, description}`; `repair` is 0 for an import-path cleanup, which is not a numbered repair, §6.4), `fix_attempt`, `candidate_accepted`, `candidate_rejected`, `iteration_completed`, `job_completed`, `job_failed`, `job_cancelled`, and after the run the summary events (§6.8): `llm_request` with `{role: "summarizer", reasoning_effort}` (no `index`/`file`), `summary_generated` (`{business, technical, dropped_sentences, tokens: {prompt_tokens, completion_tokens, total_tokens}, cost_usd?: {run, summary, input, output, total}}`; `tokens` is the summary call's; `cost_usd` is present only when both prices are set: `run` is the run's own cost (what the text talks about), `summary` this call's, and `input` / `output` / `total` the two together) and `summary_failed` (`{reason, message}`, reason `budget_exhausted`, `timeout`, `llm_error`, `llm_auth`, `llm_not_configured`, `cancelled` or `internal_error`). `validation_result.kind` can be `llm_error`, with the LLM error text in `output`, `llm_timeout` when Groq did not answer within `GROQ_TIMEOUT_S` (§5.7; the UI says "Groq timed out"), or `prompt_too_large` when a Fixer prompt could not fit `MAX_PROMPT_TOKENS` even after degrading (§6.1; no model call was made; the UI says "Prompt too large (no model call)"). Either kind can also be a `candidate_rejected.reason`; older event logs with `llm_error` still render.
- `JobManager`: in-memory, **one busy job at a time** (409 otherwise): a job is busy while it runs and, after `job_completed` / `job_cancelled`, until its AI summary is written or has failed (§6.8; the snapshot then has `writing_summary: true`, and the 409 message says the job is still writing its summary). Each job is an `asyncio.Task`. Cancel sets a flag checked before every LLM call and command, and kills the active process group; during the summary it cancels only the summary call.
- On finish, write `OUTPUT_DIR/<job_id>/`: the accepted `_test.go` files (repo-relative paths), `report.json`, `events.jsonl`, and `SUMMARY.md` when an AI summary was written (§6.8; `report.json` then gains `ai_summary`, or `ai_summary_error` when it failed, and `summary_tokens`, every summary call's tokens, kept apart from the run's own `tokens`). The UI shows this host path (`./output/<job_id>`) so users can copy the tests into their repo.
- **SSE:** `GET /api/jobs/{id}/events` always replays from seq 0, then tails. The client reducer ignores already-seen `seq`. That makes reconnects and refreshes safe without `Last-Event-ID`.

---

## 6. Planning and agents

### 6.1 Context builder (deterministic)

For one target file, it builds a prompt context in priority order. Items are trimmed from the bottom until the estimate fits **`MAX_PROMPT_TOKENS`** (default 12,000 prompt tokens; free-trial keys with 8K tokens/min set 4,500):

1. Module path, package name, **Go language version from `go.mod`**, and derived constraints (for `go 1.17`: no generics, no `slices`/`maps`/`cmp` packages, no `min`/`max` builtins, loop variables are shared, so no closures capturing `range` vars).
2. Target functions' source (from `gohelper funcs` ranges), with uncovered lines marked `// UNCOVERED`.
3. Names already declared in the package's test files (`gohelper decls`). **Never trimmed.**
4. Signatures (not bodies) of existing tests in the target test file, so the Writer avoids duplicating them. They come before item 5 so they are not crowded out; if only some fit, the most recent (last in the file) are kept.
5. Types, constants and sentinel errors referenced by the targets (same package, by identifier scan).

**Rule:** if items 1–3 alone exceed the budget, the target is split (fewer functions per call). A single function too large to fit is marked `skipped_too_large`.

**Fixer prompts degrade instead of failing.** The Fixer's task (rejected code plus validator output) is larger than the Writer's, so when it does not fit, it is shrunk in this order: items 4–5 are trimmed as usual, then the attempt history (§6.4) is cut to its first and most recent failures with observed values, then the validator output is cut to its first lines, then the rejected code is cut to whole top-level declarations, never mid-function: those the validator pointed at (failed tests, the declarations enclosing the `file:line` positions of compile/vet errors, names in the output), or, when it pointed at none, the leading declarations that fit; and finally the code is omitted (the Fixer then writes a fresh replacement from the first error lines). Only if items 1–3 plus that minimal task still do not fit does the attempt end, recorded as `prompt_too_large` (no model call made).

### 6.2 Planner (deterministic)

The planner is a pure function, no LLM. This is a deliberate trade-off to save the scarce token budget (§6.7). Every turn it does the following:

1. It ranks functions by uncovered statements, descending, skipping keys in `failed_targets` (two failed attempts) or `skipped_too_large`.
2. It groups the top functions by **source file**, so one Writer call covers one source file. It packs functions from that file up to a statement cap (default 100 uncovered statements per call; first function always included) and a function cap (default 5 functions per call), so a file of many tiny functions cannot become one oversized request; the rest are planned in later iterations.
3. It ranks the files by packed total and returns the top `targets_per_iteration` (default 3) `PlanItem{file, functions: [FuncKey], uncovered_statements}`.

"What to test" judgment (edge cases, error paths, scenarios) comes from the Writer's `test_plan` field. The UI shows it as the agent's plan for each target. The interface (`Planner` protocol) allows an LLM planner to be added later without touching the loop.

### 6.3 Writer (LLM)

- **Input:** one `PlanItem` + context (§6.1).
- **Output schema `TestSnippet`:**
  ```
  test_plan:      [{scenario: str, target: str}]   # what it decided to test and why
  imports:        [str]                             # import paths needed by the new code
  code:           str                               # ONLY new top-level decls (Test funcs, helpers); no package clause, no imports
  suspected_bugs: [{function: str, description: str}]
  ```
- **Path and package are not chosen by the LLM.** Code derives them: `<source_basename>_test.go` in the same directory, internal package (§6.6).

### 6.4 Fixer (LLM)

- **Input:** the snippet that failed, the failure kind, trimmed tool output, for `no_gain` the still-uncovered lines of the target functions, and the **attempt history** of this candidate.
- **Attempt history.** The orchestrator keeps, per candidate, an ordered record of every check: its source (`writer`, `auto_fix: <description>`, `prune of [tests]`, `llm_fix <n>`), the check kind, the failed test names, and the key failure lines: for test failures each failing test's first assertion (or panic) lines with the observed values, prefixed with the subtest name, with up to 2 continuation lines of a multi-line message (e.g. `got:`/`want:`), deduplicated across the `-count=2` repetition, at most 3 per test and interleaved across tests so every failing test's first line comes first; for compile/vet errors the first error lines; for `no_gain` the fact. Each record renders to at most 400 characters and the whole history to at most 1,500 tokens; over that, the oldest records are dropped first, except the first and the most recent failures with observed values. The Fixer prompt shows the earlier records (the latest check is the validator output itself) as `## Earlier attempts for these functions` before the rejected snippet. In the shrink order (§6.1) the history is cut to those two pinned failures right after related declarations and before the validator output, the code, or the whole code is dropped; the most recent failure with observed values is never dropped. When the current result is `no_gain` and came from pruning tests that an earlier record shows failing, the task says: "Removing the failing tests left no new coverage: the tests that reached the uncovered lines were the ones that failed. Keep them and correct their expected values (observed values are in the history)." Reason: on `output/7ef641efb870` (semver `constraints.go`) the writer asserted wrong flags, pruning turned the failure into `no_gain`, and the Fixer, which saw only `no_gain`, repeated the wrong assertion twice before the item was rejected after 6 checks.
- **Output:** the same `TestSnippet` schema (a full replacement for the *new* snippet only; accepted code is never sent back for editing).
- **Import-path cleanup (before any check).** Each answer from the Writer or the Fixer first has whitespace, quotes and backslashes stripped from both ends of every import path (job `86b6d88b558c`: `testing\` from JSON escaping was rejected by the guard and sent to the Fixer). Only the ends are touched, so a path's identity never changes and the guard still rejects a genuinely invalid path. A change is reported once per candidate as `mechanical_repair` with `repair: 0` and a description such as `cleaned import path 'testing\' → 'testing'`; it uses no fix attempt and does not count toward the 3 deterministic repairs.
- **When it is used** (max `max_fix_attempts`, default 2, per candidate):
  - `compile_error` → first a **deterministic repair** (no LLM, no fix attempt used, at most 3 per candidate, re-validated through every gate): add a missing stdlib import for `undefined: <pkg>`, strip the package's own name used as a qualifier (code tokens only, never comments or literals), or, for `gohelper: duplicate declaration: <Name>` where `<Name>` is a top-level `Test…`/`Benchmark…`/`Fuzz…` function that `go test` runs (the prefix followed by the end of the name, an uppercase letter, a digit or `_`, so not `Testable`), declared in the snippet and not referenced elsewhere in it, rename that declaration to the first free `<Name>_2`, `<Name>_3`, … (free: not declared in the package's tests nor in the snippet). Duplicate helpers (e.g. `approxEqual`), methods and `Example…` functions still go to the Fixer (`ExampleX_2` is a malformed example name for `go vet`, and an Example without `// Output:` adds no coverage). If nothing is repairable, or the cap is hit → Fixer.
  - `vet_error` → Fixer.
  - `test_failure` → first **prune** the failing tests deterministically (`gohelper prune`) and re-validate the rest. The Fixer is called with the failure output only if pruning leaves nothing that adds coverage.
  - `no_gain` → Fixer once, with the uncovered lines.
  - `guard_rejected` → Fixer once, with the rule that was violated.
- **Failing assertions:** the source code is the source of truth. The observed value in the failure output is what the code does, so the Fixer trusts it over its own expectation and corrects the expected value, unless it contradicts the function's documentation; then it drops the case and adds a `suspected_bugs` entry. The README states plainly that floating-point expectations in generated tests are partly characterization tests.

### 6.5 Why separate roles

- **Planner:** decides what to target (cheap, deterministic, testable).
- **Writer:** creates tests.
- **Fixer:** repairs against concrete tool output.

Each has its own context and contract, so prompts stay small, failures are attributable, and each piece can be unit tested with fakes. They're plain functions, not an agent framework, which keeps dependencies low and the design easy to explain.

A fourth role, the **Summarizer** (§6.8), runs once after the loop and never touches code.

### 6.8 End-of-run summary (Summarizer, LLM)

After a run ends with a report (`job_completed`, or `job_cancelled` after the baseline; never after a setup failure), and when the job option `write_summary` is on (default), an LLM writes a two-part summary from measured facts only.

- **Facts (deterministic, `app/summary/facts.py`):** `RunFacts` is built from the `Summary` and the run's events up to its terminal event: repo, module (from `workspace_ready` packages), model, goal, baseline → final %, gain in points, stop reason and message, rounds, duration (s and min), tokens (prompt/completion/total), tokens per percentage point, LLM calls by role and reasoning effort, targets accepted/rejected with reason counts, first-check passes (Writer answers accepted on their first check), Fixer calls, mechanical repairs, pruned tests, timeouts, rate-limit waits (count and seconds), tests added (count and names), test files (count and names), the export folder `output/<id>/tests`, per-file before → after, the 5 lowest-covered files with uncovered statements (from the baseline's statement counts), the suspected bugs the Writer reported, and `cost_usd` (input/output/total, the run only) when both `GROQ_PRICE_*_PER_M` are set.
- **Call:** `Agents.summarize(facts)` with role `summarizer` at `GROQ_WRITER_REASONING_EFFORT`, strict JSON schema `RunSummary` (`business: {headline, outcome, efficiency, risks[], recommendation}`, `technical: {headline, what_was_tested, where_tests_live, gaps[{file, detail}], suspected_bugs[], rejected_or_failed, how_to_run, next_steps[]}`) and prompt `agents/prompts/summarizer.md` (business: a senior business analyst for stakeholders, no jargon; technical: a senior tech lead handing over to other teams, with real files and `go test ./...`). Hard rule: only numbers, files and test names from the facts. When the facts JSON does not fit `MAX_PROMPT_TOKENS`, unchanged files and all but 30 test names are left out (their counts stay). Same client as every call: timeout and retry rules, pacing, the daily ledger. The summary's tokens count toward the job's `max_llm_tokens` (checked before the call) and the daily budget.
- **Grounding check (deterministic, `app/summary/grounding.py`):** every number in the output must match a fact of the same kind after rounding to the precision shown: dollar amounts (`$0.07`) only the cost facts, so none pass without prices; percentages (`81%`, `81 percent`, `81 points`, `81 pp`) only percentage facts; durations (`5.2 minutes`, `310s`, `two hours`, `an hour`) only the run's durations; `175K` / `1.2M` only token facts; other numbers (digits with thousands separators, number words such as `eleven` or `twenty-nine`, ordinals such as `11th`) the remaining facts (or a number in a fact's text). Multipliers (`3x`, `x3`, `3-fold`, `twice`, `doubled`, `half`) have no facts and always fail. Plain words (`each one`, `double-check`) and commands without numbers (`go test ./...`) are not numbers. Every `.go` path named must be a known file or a test file under `tests_dir`, and every `Test…` name must be in `tests_added`. A paragraph loses the failing sentences; a list item or gap that fails is dropped whole. `dropped_sentences` counts them. `technical.suspected_bugs` is replaced by the facts' own `Function: description` list.
- **Order:** `job_completed` / `job_cancelled` first, so the result shows at once; then `llm_request` (summarizer) and `summary_generated` or `summary_failed`. The SSE stream stays open until the summary is written or has failed, and the job stays busy (no new job, no other summary) until then. Cancel during the summary sets the summary's own cancel event: the call stops at once and `summary_failed` has reason `cancelled`. A failure never changes the job's status. Tokens Groq billed for a failed summary call still count toward the job.
- **Files:** `report.json` gains `ai_summary` (the event payload plus `model` and `generated_at`) or `ai_summary_error`; `SUMMARY.md` holds both sections, the note "AI-written from this run's measured data.", the generation date and the model. A later failure keeps an earlier summary.
- **Again:** `POST /api/jobs/{id}/summary` writes it again for a finished job held in memory (§8); the events follow on the same stream, which reopens until the summary is done.

### 6.6 Idiomatic Go rules (Writer/Fixer system prompt)

- Standard library `testing` only; no third-party imports; never touch `go.mod`.
- **Always the internal package** (`package stats`), so it can test unexported code, share helpers, and avoid split clauses.
- Table-driven tests with `t.Run(tc.name, ...)`. **No `t.Parallel()`** (it only saves time we don't need, and with Go < 1.22 it introduces loop-variable bugs).
- `errors.Is` for sentinel errors. Floats are compared with a tolerance helper. If `approxEqual` isn't in the declared-names list, define it once.
- Names: `TestMean`, `TestFloat64Data_Mean`, `TestPercentile_EmptyInput`.
- No `time.Sleep`, network, environment variables, or file writes outside `t.TempDir()`. No printing.
- Respect the Go language version constraints from context item 1.

### 6.7 Token budget and rate limits (main risk)

**Documented limits for `gpt-oss-120b`** (Groq rate-limits page, verified 2026-10-08): **8K tokens/min, 200K tokens/day, 30 requests/min, 1K requests/day.** Free-tier numbers weren't published separately. The account's limits page is authoritative.

- **Oversized answers:** if the Writer's answer is truncated or Groq cannot finish the JSON (`LLMOutputTooLarge`), the orchestrator retries with the first half of the item's functions, and a single function that still fails is skipped as `too_large`.
- **Per call:** output capped at `GROQ_MAX_COMPLETION_TOKENS` (default 65,536); the prompt stays ≤ `MAX_PROMPT_TOKENS` (default 12K; free-trial keys with 8K tokens/min set 4,500, which leaves at least 3,244 completion tokens after the TPM clamp of §5.7). A 16K reservation (`CALL_TOKEN_RESERVATION`, the 12K prompt cap plus an expected answer) is used for TPM pacing and the daily-ledger check; a reservation below the real call size makes pacing optimistic (more 429 waits, which are retried). Free-trial keys set 8,000, one minute's allowance. Defaults assume a paid plan: 1M tokens per job and 2M per day; free-tier keys should set `DAILY_TOKEN_BUDGET=190000` (the README repeats this). `reasoning_effort` is `medium` for both the Writer and the Fixer by default (§5.1; `high` was too slow); a truncated answer steps down automatically (§5.7). On the free tier the effective cadence is about 1 call per minute.
- **For `stats`** (about 60 small source files, no tests after deletion): 80% probably needs 20–35 Writer calls plus fixes. That's roughly 30–45 minutes and 120–190K tokens, close to the daily cap. Most `stats` functions are short, so per-call tokens will likely be lower than the cap. **Day 1 of the plan measures real per-call usage and updates these numbers.**
- **Built-in mitigations:**
  - Compact context.
  - Deterministic planner (no planning tokens).
  - Append-only output.
  - Prune instead of Fixer for failing assertions.
  - Marginal-gain stop.
  - Per-job budget (`max_llm_tokens`).
  - Daily ledger with up-front refusal.
  - Fast fail on daily-cap 429s.
  - Partial results are always saved and shown.
- **README guidance:**
  - One full run per key per day on the free tier.
  - `GROQ_MODEL=openai/gpt-oss-20b` for cheaper runs.
  - A Groq Developer plan removes the waiting.
  - Expected duration, so reviewers aren't surprised.
- **Measured end-to-end on 2026-10-08:** job `a46c5a902f70` on `stats` via the HTTP API (defaults: 10 iterations, 3 targets per iteration). Coverage went from 0.0% to 68.97% of 1247 statements in 1677.7 s over 10 iterations and stopped with `max_iterations`; the 80% target was not reached. Independent verification (fresh clone, existing tests deleted, generated tests copied in, `go vet` clean, `go test -count=1`) measured 69.0%. Tokens: 182,173 (122,218 prompt + 59,955 completion) over 43 LLM calls. 29 candidates accepted, 1 rejected (`llm_error`: 1), 14 fix attempts, 8 prune events. Gains were 3–12 pp per iteration early on, about 3 pp by iteration 10, so the default of 10 iterations was too low for `stats` and was raised to 20. Observed Groq limits for this key: 8,000 tokens per minute (`x-ratelimit-limit-tokens`) and 200,000 tokens per day. The job logged 46 `rate_limited` events (tpm and 429) totalling about 1,457 s of the 1,678 s, so rate-limit waiting dominated the duration. Two follow-up runs with `max_iterations=20` were stopped immediately with `budget_exhausted` because the daily token cap was already used.
- **Measured end-to-end run 2 (Developer key, 2026-10-08):** job `89eb53b5907e` on `stats` via the HTTP API (defaults: 20 iterations, 3 targets per iteration, planner max 100 statements, Groq Developer-plan key). Coverage went from 0.0% to 80.51% of 1247 statements in 287.1 s over 15 iterations and stopped with `target_reached`. Independent verification (fresh clone, existing tests deleted, generated tests copied in, `go vet` clean, `go test -count=1`) measured 80.5%. Tokens: 184,926 (121,055 prompt + 63,871 completion) over 45 LLM calls (41 writer, 4 fixer). 41 candidates accepted, 4 rejected (`llm_error`: 4), 7 mechanical repairs, 4 fix attempts (3 `compile_error`, 1 `test_failure`), 12 pruned tests in 12 prune events. No `rate_limited` events. Compared with run 1 (182,173 tokens for 68.97%, about 2,641 tokens per pp), run 2 used about 2,297 tokens per pp, and the duration fell from 1,677.7 s to 287.1 s because rate-limit waiting disappeared.
- **Token efficiency changes (2026-10-08).** Measured on run `a46c5a902f70` (events.jsonl): 182,173 tokens for 68.97 pp = 2,641 tokens per pp. Writer: 30 calls, avg 2,600 prompt + 1,454 completion; Fixer: 13 calls (33% of all tokens, 60,525), avg 3,400 + 1,255. Prompt size is flat across iterations (about 2.0-3.7K), so optional context sections are not the cost driver and were not trimmed. Findings and the changes they justify:
  - *Fixer calls were mostly mechanical.* 12 of 14 fix attempts were compile errors; 10 of the 13 fixer calls (about 46K tokens) answered a forgotten import (`undefined: errors|math|sort`) or the package qualifying its own identifiers (`undefined: stats`). New `app/agents/repair.py` repairs both deterministically (up to 3 times per candidate, no LLM call, no fix attempt consumed), and the repaired snippet goes through the normal guard, compile, vet, test and strict-superset gates. `writer.md` now also says to call the package's own functions unqualified.
  - *Fixer remains worth keeping at 2 attempts.* Fixed candidates produced 30.6 of the 68.97 pp; compile-error fixes: 10 succeeded on the first attempt, 2 on the second. No `vet_error`, `no_gain` or `guard_rejected` occurred, so there is no data to skip the fixer for any kind. `max_fix_attempts` stays 2.
  - *Prune is free and effective:* 8 prunes, 8 ended accepted.
  - *Bigger items are cheaper per point.* Tokens per pp by plan-item size: 3,702 (<=20 statements, 11 items), 2,738 (21-40, 11 items), 1,918 (>40, 7 items). The 60-statement cap left `load.go` (107 uncovered) needing three iterations and `norm.go` two. The cap is raised to 100 and the planner now ranks files by the statements it can pack into one prompt (not by their single biggest function), so each call buys as many statements as possible. The writer prompt asks for a few broad table-driven tests covering every `// UNCOVERED` branch (about 200 lines, was 150).
  - *Projection (not measured).* Removing the 10 mechanical fixer calls would have cut run 1 to about 135.6K tokens for the same 68.97 pp (1,966 tokens per pp). The last 11 pp costs 34-51K (iteration 9-10 writer-only rate of 3.1K per pp, up to the 4.6K per pp that iteration 10 cost including its fixer call), so a full run is projected at roughly 170-187K tokens, inside the 200K daily cap but with a thin margin. The larger item cap and planner ranking should lower this further but are not quantified until a new run.
- **Fallback if day-1 measurements show 80% isn't reachable within one day's budget:** lower the default target in the README example to the measured reachable value, and say so honestly. Don't hide it.

---

## 7. Orchestration loop

### 7.1 Algorithm

```
ws        = workspace.create(job, repo); if delete_existing_tests: ws.delete_existing_tests()
pkgs      = list_packages()                      # minus main + excluded
funcs     = gohelper funcs
report    = measure(pkgs)                        # baseline; stats → 0%
baseline  = report
failed    = Counter()                            # FuncKey → failed attempts
for iteration in 1..max_iterations:
    start_total = report.total
    if report.total >= target: stop("target_reached")
    plan = planner(report, failed)
    if not plan: stop("no_remaining_targets")
    for item in plan:                            # sequential; context built fresh per item
        check_cancel_and_budget()
        test_file = derive_test_path(item.file)
        snap      = ws.snapshot([test_file, "go.mod", "go.sum"])
        snippet   = clean_imports(writer(item, build_context(item, ws, report)))   # no LLM, no attempt used
        result    = validate(ws, test_file, snippet, report)
        history   = [record("writer", result)]   # every check of this candidate (§6.4)
        attempts  = repairs = 0
        while not result.accepted and attempts < max_fix_attempts:
            if result.kind == compile_error and repairs < 3 and (fixed := mechanical_repair(snippet, result)):
                snippet = fixed; repairs += 1       # deterministic, no LLM, attempts unchanged
                ws.restore(snap); result = validate(ws, test_file, snippet, report)
                history += [record("auto_fix: …", result)]; continue
            if result.kind == test_failure:
                result = prune_and_revalidate(result)   # deterministic, no LLM
                history += [record("prune of [tests]", result)]
                if result.accepted: break
            snippet = clean_imports(fixer(item, snippet, result, history)); attempts += 1
            ws.restore(snap)
            result  = validate(ws, test_file, snippet, report)
            history += [record(f"llm_fix {attempts}", result)]
        if result.accepted:
            report = result.report                # coverage only ever goes up
            emit candidate_accepted
        else:
            ws.restore(snap); failed[f] += 1 for f in item.functions
            emit candidate_rejected
        if report.total >= target: stop("target_reached")
    gains.append(report.total - start_total)
    if len(gains) >= patience and all(g < min_gain for g in gains[-patience:]):
        stop("marginal_gains")
stop("max_iterations")
```

`stop(...)` always writes artifacts and emits `job_completed` with the summary. Any exception → `job_failed` with partial artifacts written.

### 7.2 Baseline failure modes

- **Non-test code doesn't build:** `job_failed{reason:"repo_does_not_build", output}`. Product code is never modified.
- **Existing tests fail** (only when `delete_existing_tests=false`): `job_failed` with a hint to enable deletion.
- **No Go packages after exclusions:** `job_failed` with an explanation.
- **`go vet` already fails on the unmodified repo:** `job_failed{reason:"repo_vet_fails"}`. Every candidate would otherwise be rejected as `vet_error`, wasting the whole token budget.

### 7.3 Acceptance rules

A candidate is accepted only if **all** hold:

- the guard passes
- the merge succeeds
- `go vet` is clean
- all tests pass with `-count=2`
- the new covered-block set is a **strict superset** of the previous one

This guarantees coverage never regresses, the suite is never redundant, and the workspace always compiles and passes between candidates (rejected candidates are rolled back).

### 7.4 Options (UI + API)

| Option | Default | Range |
|---|---|---|
| `target_coverage` | 80 | 1–100 |
| `max_iterations` | 20 | 1–30 |
| `min_gain` (percentage points per iteration) | 1.0 | 0–10 |
| `patience` | 2 | 1–5 |
| `targets_per_iteration` | 3 | 1–5 |
| `max_fix_attempts` | 2 (unchanged after the 2026-10-08 token analysis, §6.7; mechanical repairs (imports, self-qualifier, duplicate test names) do not consume attempts) | 0–4 |
| `delete_existing_tests` | true | bool |
| `max_llm_tokens` (per job) | 1,000,000 | 10K–2M |
| `exclude_patterns` (module-relative path globs) | `["examples/**", "testdata/**"]` | list |
| `write_summary` (the AI summary after the run, §6.8) | true | bool |

### 7.5 Stop reasons

`target_reached`, `marginal_gains`, `max_iterations`, `no_remaining_targets`, `budget_exhausted`, `cancelled`, `error`. Each maps to one plain-language sentence in the UI.

---

## 8. HTTP API

All under `/api`, JSON, Pydantic-validated. Errors: `{"error": {"code", "message"}}`.

| Method & path | Purpose |
|---|---|
| `GET /api/health` | `{status, go_version, model, llm_configured, tokens_left_today, min_daily_tokens_to_start, storage_writable, host_repos_dir, upload_limits}` (`upload_limits` is `{max_files, max_bytes, max_file_bytes}` from `UPLOAD_MAX_*`, used by the UI's pre-check; `host_repos_dir` is display only, from `HOST_REPOS_DIR_DISPLAY`; `min_daily_tokens_to_start` is the minimum daily budget needed to start a job, below which `POST /api/jobs` returns 429) |
| `GET /api/repos` | Directories under `/repos` (depth ≤2) containing `go.mod`: `[{path, module, go_files, test_files}]` |
| `GET /api/repos/samples` | The curated sample allowlist: `[{id, name, description, license, ref, path, downloaded}]` |
| `POST /api/repos/samples/{id}` | Shallow-clones that sample (pinned release tags, no submodules; stats: default branch, the assessment's evaluation repo) into `/repos/<id>` if absent and returns the entry. Unknown id: 404 `unknown_sample`. Refuses a `go.mod` that has `require` lines |
| `POST /api/repos/sample` | Alias for `POST /api/repos/samples/stats` |
| `POST /api/repos/upload` | Multipart: one `files` part per file, whose filename is the path relative to the parent of the chosen folder (`myproj/pkg/a.go`), plus optional `name`. Saves the folder as `/repos/uploads/<name>` and returns `{path, module, go_files, test_files, skipped: {git, vendor, node_modules, hidden, too_large, binary}}`. 400 `invalid_path` / `mixed_folders` / `invalid_name` / `invalid_upload` / `no_files`, 400 `not_a_go_module` (no `go.mod` at the top), 409 `name_taken`, 409 `uploads_dir_taken` (a `repos/uploads` the app didn't create), 413 `upload_too_large`; limits and safety rules in §10.3 |
| `POST /api/jobs` | `{repo_path, target_coverage, options?}` → `201 {job_id}`. 400 for invalid input or missing key, 409 if a job is running, 429 if the daily budget is too low |
| `GET /api/jobs` | Jobs in the current process |
| `GET /api/jobs/{id}` | Snapshot: status, inputs, report, iterations, summary |
| `GET /api/jobs/{id}/events` | SSE; replays from seq 0, then tails |
| `POST /api/jobs/{id}/cancel` | Cooperative cancel + process-group kill |
| `POST /api/jobs/{id}/summary` | Write the AI summary (§6.8) again for a finished job held in memory → `202` with the job snapshot; the summary events follow on the job's event stream. 404 unknown job, 409 `job_running` (this or another job is running or writing a summary), 409 `no_report` (failed before the baseline), 400 `llm_not_configured`. Cross-origin POSTs are refused like every write |
| `GET /api/jobs/{id}/files/{path}` | Content of one generated test file. The path must be in the job's generated-file list (no traversal) |

**Repo path input:** containers can only see mounted paths. The user puts (or clones) repos into the host `./repos` folder, or sets `HOST_REPOS_DIR` to an **absolute** host path. Compose doesn't expand `~`, so the README shows `/Users/you/code`. The UI repo picker has two tabs: **Sample repos** (the six allowlisted libraries: stats, semver, xstrings, humanize, btree, decimal; click to download and select) and **Your folders** (a Choose a folder… button and drop area that upload a project to `/repos/uploads/<name>` via `POST /api/repos/upload`, the modules found under the mount, and one line on `HOST_REPOS_DIR` for large projects). There is no free-text path field.

**Data notice:** the UI and README state that the target repo's source code is sent to Groq.

---

## 9. Frontend (UX)

Design intent: a calm, precise developer tool, not a generic dashboard. The visual direction is set with the `frontend-design` skill during implementation.

### 9.1 Screens

1. **Run setup (`/`)**
   - Setup banner if `llm_configured=false`. Daily-budget hint (`tokens_left_today`).
   - Repo picker + **"Use sample repo (montanaflynn/stats)"**.
   - Target coverage (slider + number, default 80).
   - "Advanced" disclosure (§7.4).
   - Notices: "Existing `_test.go` files are removed from a working copy; your repo is never modified" and "Source code is sent to Groq".
   - Start. Disabled while a job runs, with a link to the running job.
2. **Live run (`/jobs/[id]`)**
   - Header: repo, model, status, elapsed time, tokens used, Cancel.
   - Coverage meter: current vs target marker, baseline.
   - Iteration timeline: each plan item → test plan (scenarios) → validation outcome → prunes and fixes → accepted (+x pp) or rejected (reason). Tool output sits in collapsible monospace blocks.
   - Current-activity line: "Writing tests for `percentile.go`…", "Waiting 41s for Groq rate limit (tokens/min)".
3. **Results (same page once finished)**
   - Summary: stop reason, baseline → final %, tests added, files, duration, tokens.
   - Coverage-over-iterations chart with a target reference line.
   - Per-file table: before → after, delta (static order: biggest delta first).
   - Test file viewer: file list + highlighted Go, with test plan scenarios.
   - Possible bugs found (if any).
   - Output location `./output/<job_id>` with a copy button.
   - Summary (§6.8), under the summary card: tabs "For stakeholders" and "For engineering teams", the label "AI-written from this run's measured data", the cost line "Run cost $X · summary $Y · total $Z (input …, output …)" when prices are set, Copy as Markdown (the same Markdown as `SUMMARY.md`), and Write summary / Write again. States: writing (a Groq wait timer and Stop), done, failed (message and retry), stopped, off ("Summary was turned off for this run"). A part the grounding check emptied says so. Run history keeps the run among the busy ones with "Writing summary…" and Stop summary.

### 9.2 Client data flow

One `EventSource` per job page, and a pure reducer `(state, event) -> state` that ignores already-seen `seq`. The same code serves live updates and replay. The reducer is what gets unit tested.

### 9.3 Quality bar

Purposeful typography and spacing, a restrained palette, no gratuitous gradients or emoji, real empty/loading/error states, keyboard accessible, readable in light and dark. Every number on screen comes from a real event.

---

## 10. Containerization and runtime

### 10.1 Compose

```yaml
services:
  backend:
    build: ./backend
    env_file: .env
    environment:
      CORS_ORIGINS: '["http://localhost:${FRONTEND_PORT:-3000}"]'
    ports: ["127.0.0.1:${BACKEND_PORT:-8000}:8000"]   # loopback only; host ports set in .env (defaults 8000/3000)
    volumes:
      - ${HOST_REPOS_DIR:-./repos}:/repos     # rw only so "Use sample repo" can clone
      - ./output:/output
      - gocache:/home/app/.cache
  frontend:
    build:
      context: ./frontend
      args: { NEXT_PUBLIC_API_URL: "http://localhost:${BACKEND_PORT:-8000}" }   # baked at build time
    ports: ["127.0.0.1:${FRONTEND_PORT:-3000}:3000"]
    depends_on: [backend]
volumes: { gocache: {} }
```

`repos/.gitkeep` and `output/.gitkeep` are committed. Changing the API URL requires a rebuild, and the README says so.

### 10.2 Backend image

- **Multi-stage:** a `golang:<pinned>` stage builds `gohelper`. The final `python:3.12-slim` stage gets `/usr/local/go` copied in, plus `git`.
- **Non-root `app` user:** `/home/app/.cache`, `/work` and `/output` are created and chowned in the image, so the named volume inherits ownership.
- **Entrypoint:** if the bind-mounted `/output` or `/repos` isn't writable by `app` (a Linux UID mismatch), it logs a clear instruction. On Docker Desktop for Mac, bind mounts are writable.
- Multi-arch base images, so it runs natively on Apple Silicon.

### 10.3 Execution safety (generated code is untrusted)

- Runs inside the container as non-root, never on the host. Only the workspace copy is executed or modified.
- **Environment allowlist:** the API key is not passed to test processes. Code running as the same container user could still read it via `/proc`, so the guard also rejects `StartProcess` and `/proc/` in generated code (cheap filters, bypassable via string concatenation or reflection; no further denylist rules will be added). The guard does not make generated code safe; the real control is a per-job sandbox with a separate uid and no network (§11, future work).
- **Import/content guard (best-effort filter, not a sandbox):** the snippet may import only standard library packages and the module's own packages. These are denied: `os/exec`, `net`, `net/*`, `syscall`, `unsafe`, `plugin`, `runtime/debug`.
- Timeouts at two levels (`-timeout=60s`, process 120s), with process-group kill and output caps.
- Only fixed commands run; the LLM can't choose commands.
- Ports bound to loopback only.
- **Folder uploads** (`POST /api/repos/upload`) write user-supplied files that are later compiled and tested, so: writes are subject to the origin check like every other write; every part's path is checked before anything is written (`\` normalised to `/`; absolute paths, `..`, `.`, empty segments, NUL and control characters, and `:` `<` `>` `"` `|` `?` `*` anywhere rejected, the last group so a segment can never carry a drive or an NTFS stream on a Windows host; at most 64 segments, 1,024 bytes per path and 255 per segment; all parts must share one top folder; a file the host can't create gives 400, never a 500) and each target must resolve inside the temp directory; only regular files are created (exclusive create, no symlinks); `.git`, `vendor`, `node_modules`, hidden paths, files over `UPLOAD_MAX_FILE_BYTES` (1 MB) and files with a NUL byte in their first 8 KB are skipped; at most `UPLOAD_MAX_FILES` (3,000) files and `UPLOAD_MAX_BYTES` (25 MB) are kept, and the raw body is cut off at twice the byte limit plus multipart overhead and at twice the file limit in parts (413 `upload_too_large`). Files go to `/repos/uploads/.tmp-<random>` and replace `/repos/uploads/<name>` with a rename under the clone lock; a destination is replaced only if it holds the `.gca-upload` marker of an earlier upload (otherwise 409 `name_taken`), and the temp directory is removed on any failure; `.tmp-*` folders older than an hour (left by a crash or kill) are removed on the next upload. `repos/uploads` is created with its own `.gca-uploads` marker, and an existing `uploads` folder without it (for example the user's own, under `HOST_REPOS_DIR`) is never written into (409 `uploads_dir_taken`). Jobs copy the repository under the same lock, so a re-upload never swaps a folder while a job is copying it. Error messages carry no server paths. `<name>` is the top folder (or `name`) reduced to lowercase letters, digits, `-`, `_`, `.`, at most 64 characters.
- **Documented residual risk:** a test could still read files inside the container via `os` (including the backend's environment via `/proc`) and start processes. The real fix is a per-job sandbox with a separate uid. Production hardening (a per-run sandbox with gVisor/Firecracker, no network) is in §11.

### 10.4 `.env.example`

`GROQ_API_KEY=`, `GROQ_MODEL=openai/gpt-oss-120b`, `GROQ_WRITER_REASONING_EFFORT=medium`, `GROQ_FIXER_REASONING_EFFORT=medium`, `HOST_REPOS_DIR=./repos`, a commented `MAX_PROMPT_TOKENS=4500` for free-trial keys, and under Advanced the commented `GROQ_MAX_COMPLETION_TOKENS=65536`, `GROQ_TIMEOUT_S=240` and the upload limits `UPLOAD_MAX_FILES=3000`, `UPLOAD_MAX_BYTES=26214400`, `UPLOAD_MAX_FILE_BYTES=1048576`. Under Optional (whose header says the values are the defaults unless noted), the example prices `GROQ_PRICE_INPUT_PER_M=0.15` and `GROQ_PRICE_OUTPUT_PER_M=0.60` (openai/gpt-oss-120b on Groq at the time of writing; not code defaults).

---

## 11. Non-goals (v1) and future work

- **Hosting** (Vercel frontend + Linode API behind Caddy), auth, multi-user, persistent DB, job queue, per-run sandbox containers.
- **An LLM-based planner:** the interface exists; deterministic for v1 to save tokens.
- **Bulk downloads:** zip download and patch file; v1 writes files to `./output/<job_id>`.
- **Other languages and providers;** concurrent jobs and parallel LLM calls (rate limits make them pointless).
- **Product-code changes:** modifying product code or fixing bugs it finds. It only reports suspected bugs.
- **Mutation testing:** measuring assertion strength, not just coverage.
- **CI pipeline:** stretch goal if time remains (GitHub Actions running the three suites).

---

## 12. Testing strategy (for our own code)

| Suite | Covers | Notes |
|---|---|---|
| Backend unit (pytest) | coverage parse/summarize/superset; planner ranking, grouping and skipping; stop policy; context builder budget + never-trim rules; strict-schema normalizer; import guard; workspace path guard + snapshot/restore incl. absent files; rate limiter + daily ledger (fake clock); validator classification (fake gotools); orchestrator end to end with `FakeLLM` + `FakeGoTools`; API routes via `httpx.AsyncClient`; SSE replay | No network, no Go needed |
| Backend integration (`-m integration`) | gotools + validator + gohelper against `tests/fixtures/gomod/` (tiny module with known coverage numbers, including a zero-test package for the denominator check) | Runs in the backend image |
| Go helper (`go test`) | `funcs`, `decls`, `merge` (new file, existing file, duplicate rejection, import dedupe), `prune` | |
| Frontend (Vitest) | event reducer (incl. duplicate `seq`), formatters, stop-reason copy | |
| Manual acceptance | Full run on `stats` at 80% | Results + screenshot in README |

`make test` runs all suites. Each is also documented individually.

---

## 13. Documentation

### 13.1 README sections

- Purpose and a demo screenshot.
- Requirements: Docker; a Groq API key; Node 22 only if running the frontend outside Docker.
- **Quick start:** copy `.env.example` → `.env`, add the key, `docker compose up --build`, open `http://localhost:3000`, click "Use sample repo", Start.
- **Expected run time and Groq limits.**
- Using your own repo (`./repos` or an absolute `HOST_REPOS_DIR`).
- **Model:** `openai/gpt-oss-120b` on Groq (fallback `openai/gpt-oss-20b`).
- How it works (diagram + loop); configuration options; running the tests.
- Design decisions and trade-offs; limitations (floating-point expectations, residual sandbox risk, source sent to Groq).
- Results on `stats`; AI usage disclosure.

### 13.2 AI usage disclosure

- A README section on where AI was used (design discussion, scaffolding, specific modules) and where it wasn't (decisions, review, verification).
- A short header comment in each source file, e.g. `// AI-assisted: initial draft generated with Claude; reviewed and modified by <name>`. It has to be accurate per file.
- The `docs/superpowers/` spec and plan are committed as evidence of the process.

---

## 14. Risks and mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| Groq TPM/TPD limits make the demo slow or cut it short | High | §6.7 measures, budgets, fails fast, saves partial results, gives honest README guidance |
| LLM computes wrong float expectations | High | Prune failing cases; Fixer plausibility rule; tolerance helper; documented limitation |
| Generated code violates Go 1.17 rules | Medium | Go version constraints injected into prompts; vet/compile catches the rest; Fixer |
| Duplicate identifiers across test files | Medium | `decls` list never trimmed; `merge` rejects duplicates up front |
| `examples/` main packages drag coverage down | Certain for `stats` | Exclude `main` packages + `examples/**` |
| Runaway or hung tests | Low | Timeouts + process-group kill |
| Flaky tests | Low | `-count=2` |
| Model deprecation | Low | `GROQ_MODEL` env, documented fallback |
| Running out of time | Medium | Day-3 end-to-end milestone; UI polish, CI, extras after; cut list in §11 |

---

## 15. Open questions

None blocking. Defaults that can be changed after review: target 80%, `openai/gpt-oss-120b`, `reasoning_effort` `medium` for the Writer and the Fixer, one job at a time, deterministic planner.
