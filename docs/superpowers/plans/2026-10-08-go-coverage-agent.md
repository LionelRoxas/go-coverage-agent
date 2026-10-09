# Go Coverage Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a containerized app that takes a local Go repo + target coverage %, then autonomously plans, writes (via Groq LLM), validates and iterates on Go unit tests until the target is reached or gains become marginal, with live results in a browser.

**Architecture:** A FastAPI backend runs a deterministic orchestration loop: measure coverage → plan targets → LLM writes test snippets → `gohelper` merges them → compile/vet/test/coverage validation → prune or LLM-fix → accept or roll back. Go-specific parsing and merging live in a small Go CLI (`gohelper`). A Next.js frontend reads job events over SSE and renders progress and results. Everything starts with `docker compose up`.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, pydantic-settings, `groq` SDK, sse-starlette, pytest + pytest-asyncio; Go (official image) for `gohelper`; Next.js (App Router) + TypeScript + Tailwind + Recharts + Shiki + Vitest; Docker Compose.

**Spec:** `docs/superpowers/specs/2026-10-08-go-coverage-agent-design.md`. Read it before starting any task. Section references like "spec §5.6" point there.

## Global Constraints

- **Languages:** Python (backend), Go (`tools/gohelper`), TypeScript (frontend). Nothing else.
- **Model:** default `GROQ_MODEL=openai/gpt-oss-120b`; fallback `openai/gpt-oss-20b`; `GROQ_REASONING_EFFORT=low` by default.
  > Note (Task 32): `GROQ_REASONING_EFFORT` was replaced by the per-role settings `GROQ_WRITER_REASONING_EFFORT` (default `medium`) and `GROQ_FIXER_REASONING_EFFORT` (default `high`); see the spec §5.1.
- **Token limits:** `MAX_TOKENS_PER_CALL=7000` (prompt + completion), `MAX_PROMPT_TOKENS=4500`, `DAILY_TOKEN_BUDGET=190000`, `MIN_DAILY_TOKENS_TO_START=20000`. Token estimate = `ceil(len(text) / 3.5)`.
- **Groq API:** every call uses Structured Outputs `{"type":"json_schema","json_schema":{"name":…,"strict":true,"schema":…}}`, with no tools and no streaming. The SDK client is created with `max_retries=0` (our code owns retries).
- **Generated Go tests:** always the internal package (same package name as the source), file `<source_basename>_test.go` next to the source, standard library only, no `t.Parallel()`, respect the `go` directive in `go.mod`.
- **Commands:** only `go list`, `go test`, `go vet`, `gohelper`, `git clone` (sample repo only) are ever executed, via `app/gotools.py`. Argument lists only, never a shell. Subprocess env is an allowlist and never contains `GROQ_API_KEY`.
- **Single test command:** `go test -count=2 -covermode=set -coverprofile=<file> -timeout=60s <pkgs>`. Compile check: `go test -count=1 -run=^$ <pkgs>`.
- **Seed file name:** `zz_coverage_seed_test.go`. It's never exported as an artifact.
- **Default exclude patterns:** `["examples/**", "testdata/**"]`, matched against module-relative package directories. Packages named `main` are always excluded.
- **Ports:** compose binds `127.0.0.1:8000` (backend) and `127.0.0.1:3000` (frontend) only.
- **Paths:** container paths are `/repos`, `/output`, `/work`, `/home/app/.cache/go-build`, `/home/app/.cache/go-mod`.
- **Line endings:** LF everywhere (`.gitattributes`), because the developer machine is Windows.
- **Git Bash + Docker on Windows:** run `export MSYS_NO_PATHCONV=1` once per shell before any `docker run … -v …:/x -w /x` command in this plan. Otherwise Git Bash rewrites `/src` into `C:/Program Files/Git/src` and mounts break.
- **AI disclosure:** every source file you create starts with a one-line comment: `# AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.` (use `//` in Go/TS). The author edits wording per file if they wrote it themselves.
- **Where tests run:** Backend unit tests run on the host (`cd backend && uv run pytest`) or in the image. Integration tests (`-m integration`) and anything using `os.killpg` run **only inside the backend image** (Linux). Go tests run with local Go or `docker run golang`.
- **Event payloads:** use exactly the contract below. Backend emits these; frontend consumes them.

### Event payload contract (backend ⇄ frontend)

| `type` | `data` |
|---|---|
| `job_started` | `{repo_path, target_coverage, options, model}` |
| `workspace_ready` | `{removed_tests: string[], packages: string[]}` |
| `baseline_measured` | `{report: CoverageReportPublic}` |
| `iteration_started` | `{index, percent}` |
| `plan_created` | `{index, items: [{file, functions: string[], uncovered_statements}]}` |
| `llm_call` | `{index, file, role, prompt_tokens, completion_tokens, total_tokens}` (`total_tokens` = job cumulative) |
| `rate_limited` | `{seconds, reason}` (`reason` ∈ `tpm`, `429`) |
| `candidate_generated` | `{index, file, test_file, test_plan: [{scenario, target}], code}` |
| `validation_result` | `{index, file, kind, output, failed_tests: string[]}` |
| `tests_pruned` | `{index, file, tests: string[]}` |
| `fix_attempt` | `{index, file, attempt, kind}` |
| `candidate_accepted` | `{index, file, test_file, tests: string[], percent, gain}` |
| `candidate_rejected` | `{index, file, reason}` |
| `iteration_completed` | `{index, start_percent, end_percent, accepted, rejected}` |
| `job_completed` / `job_cancelled` | `Summary` (see Task 1 models) |
| `job_failed` | `{reason, message, output}` |

`CoverageReportPublic` = `CoverageReport` without `covered_block_ids`.

## Review Focus

1. **A user types a host path** like `/Users/me/code/stats` that the container can't see. Expect a 400 that explains the `./repos` mount, not a "file not found". (Test in Task 5 + Task 16.)
2. **The Groq key is invalid or revoked (401).** The job should fail immediately with "Groq rejected the API key", not retry or hang. (Test in Task 9.)
3. **The target repo doesn't build, or needs a newer Go.** The job should fail with `repo_does_not_build` and show the compiler output; it shouldn't loop. (Test in Task 14.)
4. **The user refreshes the page or opens a second tab mid-run.** Expect full history with no duplicated timeline entries. (Tests in Task 15 + Task 18.)
5. **A generated test hangs** (infinite loop). It should be killed by the timeout, including the child test binary. The candidate is rejected and the loop continues. (Test in Task 6.)

## Schedule (day milestones)

| Day | Tasks | Milestone |
|---|---|---|
| 1 | 1–6 | Image builds; baseline coverage of a fixture measured inside the container |
| 2 | 7–12 | Validator + LLM client + agents; smoke call to Groq with real token numbers |
| 3 | 13–17 | **Full autonomous run on `stats` via API** (go/no-go checkpoint) |
| 4–5 | 18–20 | Frontend |
| 6 | 21 | README, AI disclosure, fresh-clone verification |
| 7 | 22 + buffer | CI (stretch), fixes |

## File Structure

```
.
├── .gitattributes / .gitignore / .dockerignore / .env.example / Makefile
├── docker-compose.yml
├── repos/.gitkeep                 # host folder mounted at /repos
├── output/.gitkeep                # host folder mounted at /output
├── tools/gohelper/                # Go CLI: funcs, decls, merge, prune
│   ├── go.mod
│   ├── main.go                    # subcommand dispatch
│   ├── funcs.go / funcs_test.go   # function inventory + test-file decls
│   └── merge.go / merge_test.go   # append-only merge + prune + tidy
├── backend/
│   ├── Dockerfile / pyproject.toml / uv.lock
│   ├── app/
│   │   ├── config.py              # Settings
│   │   ├── models.py              # shared Pydantic/dataclass types
│   │   ├── coverage.py            # profile parsing + summaries
│   │   ├── workspace.py           # repo copy, seed, snapshot/restore, path guards
│   │   ├── gotools.py             # the ONLY command runner
│   │   ├── guard.py               # static checks on LLM snippets
│   │   ├── validator.py           # merge → compile → vet → test → coverage
│   │   ├── llm/schema.py          # Pydantic → Groq strict schema
│   │   ├── llm/limits.py          # rate limiter + daily usage ledger
│   │   ├── llm/client.py          # LLMClient protocol + GroqLLM
│   │   ├── agents/context.py      # deterministic prompt context
│   │   ├── agents/planner.py      # deterministic target selection
│   │   ├── agents/llm_agents.py   # Writer + Fixer
│   │   ├── agents/prompts/writer.md / fixer.md
│   │   ├── engine/policy.py       # stop rules + messages
│   │   ├── engine/orchestrator.py # the loop
│   │   ├── engine/setup.py        # prepare workspace, baseline
│   │   ├── engine/run.py          # run_job + artifacts
│   │   ├── jobs.py                # Job, JobManager, event streaming
│   │   ├── repos.py               # list repos, clone sample
│   │   ├── api.py                 # HTTP routes
│   │   └── main.py                # create_app
│   ├── scripts/groq_smoke.py      # measures real token usage
│   └── tests/ (unit + integration, fixtures/gomod, fixtures/broken)
└── frontend/
    ├── Dockerfile / package.json / next.config.ts / vitest.config.ts
    └── src/
        ├── lib/types.ts / api.ts / runState.ts / format.ts (+ *.test.ts)
        ├── lib/useJobEvents.ts
        ├── components/ (RepoPicker, CoverageMeter, Timeline, CoverageChart, FileTable, TestFiles, SummaryCard)
        └── app/ (layout.tsx, page.tsx, jobs/[id]/page.tsx, globals.css)
```

---

### Task 1: Project scaffold, settings, shared models

**Files:**
- Create: `.gitattributes`, `.gitignore`, `.dockerignore`, `.env.example`, `Makefile`, `repos/.gitkeep`, `output/.gitkeep`
- Create: `backend/pyproject.toml`, `backend/app/__init__.py`, `backend/app/config.py`, `backend/app/models.py`
- Create: `backend/app/llm/__init__.py`, `backend/app/agents/__init__.py`, `backend/app/engine/__init__.py`
- Test: `backend/tests/__init__.py`, `backend/tests/test_models.py`, `backend/tests/test_config.py`

**Interfaces:**
- Produces: `Settings` (with `llm_configured` property); models `FuncKey`, `FuncInfo`, `Block`, `FuncCoverage`, `FileCoverage`, `CoverageReport`, `PlanItem`, `TestScenario`, `SuspectedBug`, `TestSnippet`, `JobOptions`, `JobRequest`, `StopReason`, `JobStatus`, `Event`, `TokenUsage`, `IterationRecord`, `FileDelta`, `Summary`. Every later task imports these from `app.models` / `app.config`.

- [ ] **Step 1: Create repo-level files**

`.gitattributes`:
```
* text=auto eol=lf
*.png binary
```

`.gitignore`:
```
__pycache__/
.venv/
.pytest_cache/
node_modules/
.next/
.env
repos/*
!repos/.gitkeep
output/*
!output/.gitkeep
```

`.dockerignore`:
```
**/node_modules
**/.next
**/.venv
**/__pycache__
.git
repos
output
.env
```

`.env.example`:
```
# Required: create a free key at https://console.groq.com/keys
GROQ_API_KEY=
# Model the app requires (fallback: openai/gpt-oss-20b — cheaper, weaker)
GROQ_MODEL=openai/gpt-oss-120b
GROQ_REASONING_EFFORT=low
# Absolute host path whose sub-folders contain Go repos (compose does not expand ~)
HOST_REPOS_DIR=./repos
```

> Note (Task 32): `GROQ_REASONING_EFFORT` was replaced by the per-role settings `GROQ_WRITER_REASONING_EFFORT` (default `medium`) and `GROQ_FIXER_REASONING_EFFORT` (default `high`); see the spec §5.1.

`Makefile` (the backend image is built directly, so these targets work before `docker-compose.yml` exists):
```make
GO_IMAGE := golang:$(shell cat .go-version)
.PHONY: up backend-image test test-go test-backend test-integration test-frontend
up:
	docker compose up --build
backend-image:
	docker build -f backend/Dockerfile --build-arg GO_IMAGE=$(GO_IMAGE) -t gca-backend .
test: test-go test-backend test-integration test-frontend
test-go:
	MSYS_NO_PATHCONV=1 docker run --rm -v "$(CURDIR)/tools/gohelper:/src" -w /src $(GO_IMAGE) go test ./...
test-backend: backend-image
	docker run --rm gca-backend uv run --no-sync pytest
test-integration: backend-image
	docker run --rm gca-backend uv run --no-sync pytest -m integration
test-frontend:
	cd frontend && npm test
```
On Windows without `make`, run the same commands directly in Git Bash.

Create empty `repos/.gitkeep` and `output/.gitkeep`.

- [ ] **Step 2: Pin the Go version**

Run: `docker run --rm golang:1-bookworm go version`
Expected: `go version go1.X.Y linux/...`. Write `1.X-bookworm` (e.g. `1.27-bookworm`) to a new file `.go-version` (single line, no newline issues). Every later reference to the Go image uses this value.

- [ ] **Step 3: Create `backend/pyproject.toml`**

```toml
[project]
name = "go-coverage-agent"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.115",
  "uvicorn[standard]>=0.30",
  "pydantic>=2.8",
  "pydantic-settings>=2.4",
  "groq>=0.30",
  "sse-starlette>=2.1,<3",  # tests/conftest.py touches AppStatus internals; re-check on a major bump
]

[dependency-groups]
dev = ["pytest>=8", "pytest-asyncio>=0.24", "httpx>=0.27"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
markers = ["integration: needs Go + gohelper; run inside the backend image"]
addopts = "-m 'not integration'"
```

Run: `cd backend && uv sync` (install uv first with `pip install uv` if missing). It creates `uv.lock`. Commit it.

- [ ] **Step 4: Write the failing tests**

`backend/tests/test_models.py`:
```python
from app.models import Block, CoverageReport, FuncKey, JobRequest, TokenUsage


def test_funckey_label_and_hashable():
    plain = FuncKey(file="mean.go", name="Mean")
    method = FuncKey(file="data.go", receiver="Float64Data", name="Mean")
    assert plain.label() == "Mean"
    assert method.label() == "Float64Data.Mean"
    assert len({plain, method, FuncKey(file="mean.go", name="Mean")}) == 2


def test_block_id_is_stable():
    b = Block(file="mean.go", start_line=3, start_col=2, end_line=5, end_col=10, statements=2)
    assert b.id == "mean.go:3.2,5.10"


def test_report_public_omits_block_ids():
    r = CoverageReport(total_statements=4, covered_statements=1, percent=25.0,
                       files=[], functions=[], covered_block_ids=["a"])
    assert r.covered_set() == frozenset({"a"})
    assert "covered_block_ids" not in r.public()


def test_job_request_defaults_and_bounds():
    req = JobRequest(repo_path="stats")
    assert req.target_coverage == 80
    assert req.options.max_iterations == 10
    assert req.options.exclude_patterns == ["examples/**", "testdata/**"]


def test_token_usage_add():
    total = TokenUsage(prompt_tokens=10, completion_tokens=5).add(TokenUsage(prompt_tokens=1, completion_tokens=1))
    assert total.total == 17
```

`backend/tests/test_config.py`:
```python
from app.config import Settings


def test_llm_configured_reflects_key(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    assert Settings().llm_configured is False
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    s = Settings()
    assert s.llm_configured is True
    assert s.groq_model == "openai/gpt-oss-120b"
    assert s.max_tokens_per_call == 7000
```

- [ ] **Step 5: Run the tests to verify they fail**

Run: `cd backend && uv run pytest -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'app'`.

- [ ] **Step 6: Implement `backend/app/config.py`**

```python
# AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    groq_reasoning_effort: Literal["low", "medium", "high"] = "low"
    max_tokens_per_call: int = 7000
    max_prompt_tokens: int = 4500
    daily_token_budget: int = 190_000
    min_daily_tokens_to_start: int = 20_000

    repos_dir: Path = Path("/repos")
    output_dir: Path = Path("/output")
    work_dir: Path = Path("/work")
    gocache: Path = Path("/home/app/.cache/go-build")
    gomodcache: Path = Path("/home/app/.cache/go-mod")

    command_timeout_s: float = 120.0
    test_timeout: str = "60s"
    max_output_chars: int = 20_000
    cors_origins: list[str] = ["http://localhost:3000"]
    sample_repo_url: str = "https://github.com/montanaflynn/stats"

    @property
    def llm_configured(self) -> bool:
        return bool(self.groq_api_key.strip())
```

> Note (Task 32): `GROQ_REASONING_EFFORT` was replaced by the per-role settings `GROQ_WRITER_REASONING_EFFORT` (default `medium`) and `GROQ_FIXER_REASONING_EFFORT` (default `high`); see the spec §5.1.

- [ ] **Step 7: Implement `backend/app/models.py`**

```python
# AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
"""Types shared across the backend. Pydantic for anything serialized; dataclass for hot internals."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FuncKey(BaseModel):
    """Unique identity of a function: (file, receiver, name). `Mean` != `Float64Data.Mean`."""

    model_config = ConfigDict(frozen=True)
    file: str
    receiver: str = ""
    name: str

    def label(self) -> str:
        return f"{self.receiver}.{self.name}" if self.receiver else self.name


class FuncInfo(BaseModel):
    key: FuncKey
    package: str
    start_line: int
    end_line: int
    exported: bool


@dataclass(frozen=True)
class Block:
    file: str  # module-relative, e.g. "mean.go" or "sub/x.go"
    start_line: int
    start_col: int
    end_line: int
    end_col: int
    statements: int

    @property
    def id(self) -> str:
        return f"{self.file}:{self.start_line}.{self.start_col},{self.end_line}.{self.end_col}"


class FuncCoverage(BaseModel):
    key: FuncKey
    statements: int
    covered: int
    uncovered_lines: list[tuple[int, int]] = Field(default_factory=list)

    @property
    def uncovered(self) -> int:
        return self.statements - self.covered


class FileCoverage(BaseModel):
    file: str
    statements: int
    covered: int
    percent: float


class CoverageReport(BaseModel):
    total_statements: int
    covered_statements: int
    percent: float
    files: list[FileCoverage]
    functions: list[FuncCoverage]
    covered_block_ids: list[str]

    def covered_set(self) -> frozenset[str]:
        return frozenset(self.covered_block_ids)

    def public(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude={"covered_block_ids"})


class PlanItem(BaseModel):
    file: str
    functions: list[FuncKey]
    uncovered_statements: int


# --- LLM I/O. Strict-schema friendly: every field required, no defaults. ---
class TestScenario(BaseModel):
    __test__ = False  # stop pytest from collecting this class
    scenario: str = Field(description="One behaviour being tested, e.g. 'empty input returns EmptyInputErr'")
    target: str = Field(description="Function label being tested, e.g. 'Mean' or 'Float64Data.Mean'")


class SuspectedBug(BaseModel):
    function: str
    description: str


class TestSnippet(BaseModel):
    __test__ = False
    test_plan: list[TestScenario] = Field(description="What you decided to test and why, one entry per scenario")
    imports: list[str] = Field(description="Import paths the new code needs, e.g. ['testing', 'math']")
    code: str = Field(description="ONLY new top-level Go declarations: Test functions and helpers. No package clause, no imports.")
    suspected_bugs: list[SuspectedBug] = Field(description="Behaviour that looks wrong in the source; empty if none")


# --- Jobs ---
class JobOptions(BaseModel):
    max_iterations: int = Field(10, ge=1, le=30)
    min_gain: float = Field(1.0, ge=0, le=10)
    patience: int = Field(2, ge=1, le=5)
    targets_per_iteration: int = Field(3, ge=1, le=5)
    max_fix_attempts: int = Field(2, ge=0, le=4)
    delete_existing_tests: bool = True
    max_llm_tokens: int = Field(180_000, ge=10_000, le=2_000_000)
    exclude_patterns: list[str] = Field(default_factory=lambda: ["examples/**", "testdata/**"])


class JobRequest(BaseModel):
    repo_path: str = Field(min_length=1)
    target_coverage: float = Field(80, ge=1, le=100)
    options: JobOptions = Field(default_factory=JobOptions)


class StopReason(StrEnum):
    TARGET_REACHED = "target_reached"
    MARGINAL_GAINS = "marginal_gains"
    MAX_ITERATIONS = "max_iterations"
    NO_REMAINING_TARGETS = "no_remaining_targets"
    BUDGET_EXHAUSTED = "budget_exhausted"
    CANCELLED = "cancelled"


class JobStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Event(BaseModel):
    seq: int
    ts: float
    type: str
    data: dict[str, Any]


class TokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def add(self, other: TokenUsage) -> TokenUsage:
        return TokenUsage(prompt_tokens=self.prompt_tokens + other.prompt_tokens,
                          completion_tokens=self.completion_tokens + other.completion_tokens)


class IterationRecord(BaseModel):
    index: int
    start_percent: float
    end_percent: float
    accepted: int
    rejected: int


class FileDelta(BaseModel):
    file: str
    before: float
    after: float


class Summary(BaseModel):
    stop_reason: StopReason
    message: str
    target: float
    baseline_percent: float
    final_percent: float
    iterations: list[IterationRecord]
    test_files: list[str]
    tests_added: list[str]
    suspected_bugs: list[SuspectedBug]
    per_file: list[FileDelta]
    tokens: TokenUsage
    duration_s: float
```

Create empty `backend/app/__init__.py`, `backend/app/llm/__init__.py`, `backend/app/agents/__init__.py`, `backend/app/engine/__init__.py`, `backend/tests/__init__.py`.

- [ ] **Step 8: Run the tests to verify they pass**

Run: `cd backend && uv run pytest -q`
Expected: 6 passed.

- [ ] **Step 9: Commit**

```bash
git add .
git commit -m "chore: scaffold project, settings and shared models"
```

---

### Task 2: gohelper — `funcs` and `decls`

**Files:**
- Create: `tools/gohelper/go.mod`, `tools/gohelper/main.go`, `tools/gohelper/funcs.go`
- Test: `tools/gohelper/funcs_test.go`

**Interfaces:**
- Produces CLI: `gohelper funcs <dir>` → JSON array `[{"file","package","receiver","name","start_line","end_line","exported"}]` (sorted by file, then start_line; `[]` when empty). `gohelper decls <dir>` → JSON array of sorted, unique top-level identifiers declared in `<dir>/*_test.go` (non-recursive; methods and `_` excluded).
- Produces Go funcs `Funcs(root string) ([]FuncInfo, error)` and `Decls(dir string) ([]string, error)`, used by Task 3.

- [ ] **Step 1: Create the module**

`tools/gohelper/go.mod`:
```
module gohelper

go 1.22
```

- [ ] **Step 2: Write the failing tests** — `tools/gohelper/funcs_test.go`

```go
// AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
package main

import (
	"os"
	"path/filepath"
	"reflect"
	"testing"
)

func writeFile(t *testing.T, dir, name, src string) {
	t.Helper()
	path := filepath.Join(dir, name)
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte(src), 0o644); err != nil {
		t.Fatal(err)
	}
}

func TestFuncs_FunctionsAndMethods(t *testing.T) {
	dir := t.TempDir()
	writeFile(t, dir, "a.go", "package p\n\ntype T []float64\n\nfunc Mean(x []float64) float64 {\n\treturn 0\n}\n\nfunc (t T) Mean() float64 {\n\treturn Mean(t)\n}\n\nfunc (t *T) reset() {}\n")
	writeFile(t, dir, "a_test.go", "package p\n\nfunc helper() {}\n")

	got, err := Funcs(dir)
	if err != nil {
		t.Fatal(err)
	}
	want := []FuncInfo{
		{File: "a.go", Package: "p", Receiver: "", Name: "Mean", StartLine: 5, EndLine: 7, Exported: true},
		{File: "a.go", Package: "p", Receiver: "T", Name: "Mean", StartLine: 9, EndLine: 11, Exported: true},
		{File: "a.go", Package: "p", Receiver: "T", Name: "reset", StartLine: 13, EndLine: 13, Exported: false},
	}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("got  %+v\nwant %+v", got, want)
	}
}

func TestFuncs_WalksSubdirsSkipsVendorTestdataHidden(t *testing.T) {
	dir := t.TempDir()
	writeFile(t, dir, "sub/b.go", "package sub\n\nfunc B() {}\n")
	writeFile(t, dir, "vendor/v/v.go", "package v\n\nfunc V() {}\n")
	writeFile(t, dir, "testdata/x.go", "package x\n\nfunc X() {}\n")
	writeFile(t, dir, ".hidden/h.go", "package h\n\nfunc H() {}\n")

	got, err := Funcs(dir)
	if err != nil {
		t.Fatal(err)
	}
	if len(got) != 1 || got[0].File != "sub/b.go" || got[0].Name != "B" {
		t.Fatalf("unexpected result: %+v", got)
	}
}

func TestFuncs_EmptyDirReturnsEmptySlice(t *testing.T) {
	got, err := Funcs(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	if got == nil || len(got) != 0 {
		t.Fatalf("want empty non-nil slice, got %#v", got)
	}
}

func TestDecls_TopLevelTestIdentifiers(t *testing.T) {
	dir := t.TempDir()
	writeFile(t, dir, "a_test.go", "package p\n\nimport \"testing\"\n\nvar tol = 1e-9\n\ntype tc struct{}\n\nconst k = 1\n\nvar _ = k\n\nfunc approxEqual(a, b float64) bool { return true }\n\nfunc TestX(t *testing.T) {}\n\nfunc (tc) m() {}\n")
	writeFile(t, dir, "b.go", "package p\n\nfunc Real() {}\n")
	writeFile(t, dir, "sub/c_test.go", "package sub\n\nfunc TestNested() {}\n")

	got, err := Decls(dir)
	if err != nil {
		t.Fatal(err)
	}
	want := []string{"TestX", "approxEqual", "k", "tc", "tol"}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("got %v want %v", got, want)
	}
}
```

- [ ] **Step 3: Run the tests to verify they fail**

Run (local Go): `cd tools/gohelper && go test ./...`
Or Docker: `docker run --rm -v "$PWD/tools/gohelper:/src" -w /src golang:$(cat .go-version) go test ./...`
Expected: FAIL, `undefined: Funcs`.

- [ ] **Step 4: Implement `tools/gohelper/funcs.go`**

```go
// AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
package main

import (
	"fmt"
	"go/ast"
	"go/parser"
	"go/token"
	"io/fs"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

// FuncInfo locates one function or method in a non-test source file.
type FuncInfo struct {
	File      string `json:"file"`
	Package   string `json:"package"`
	Receiver  string `json:"receiver"`
	Name      string `json:"name"`
	StartLine int    `json:"start_line"`
	EndLine   int    `json:"end_line"`
	Exported  bool   `json:"exported"`
}

func skipDir(root, path, name string) bool {
	return path != root && (strings.HasPrefix(name, ".") || name == "vendor" || name == "testdata")
}

// Funcs lists every function with a body in non-test .go files under root.
func Funcs(root string) ([]FuncInfo, error) {
	out := []FuncInfo{}
	fset := token.NewFileSet()
	err := filepath.WalkDir(root, func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if d.IsDir() {
			if skipDir(root, path, d.Name()) {
				return filepath.SkipDir
			}
			return nil
		}
		if !strings.HasSuffix(path, ".go") || strings.HasSuffix(path, "_test.go") {
			return nil
		}
		f, err := parser.ParseFile(fset, path, nil, parser.SkipObjectResolution)
		if err != nil {
			return fmt.Errorf("parse %s: %w", path, err)
		}
		rel, err := filepath.Rel(root, path)
		if err != nil {
			return err
		}
		rel = filepath.ToSlash(rel)
		for _, decl := range f.Decls {
			fd, ok := decl.(*ast.FuncDecl)
			if !ok || fd.Body == nil {
				continue
			}
			out = append(out, FuncInfo{
				File:      rel,
				Package:   f.Name.Name,
				Receiver:  receiverName(fd),
				Name:      fd.Name.Name,
				StartLine: fset.Position(fd.Pos()).Line,
				EndLine:   fset.Position(fd.End()).Line,
				Exported:  fd.Name.IsExported(),
			})
		}
		return nil
	})
	if err != nil {
		return nil, err
	}
	sort.SliceStable(out, func(i, j int) bool {
		if out[i].File != out[j].File {
			return out[i].File < out[j].File
		}
		return out[i].StartLine < out[j].StartLine
	})
	return out, nil
}

func receiverName(fd *ast.FuncDecl) string {
	if fd.Recv == nil || len(fd.Recv.List) == 0 {
		return ""
	}
	t := fd.Recv.List[0].Type
	if star, ok := t.(*ast.StarExpr); ok {
		t = star.X
	}
	switch x := t.(type) {
	case *ast.Ident:
		return x.Name
	case *ast.IndexExpr:
		if id, ok := x.X.(*ast.Ident); ok {
			return id.Name
		}
	case *ast.IndexListExpr:
		if id, ok := x.X.(*ast.Ident); ok {
			return id.Name
		}
	}
	return ""
}

// Decls returns the sorted top-level identifiers declared in dir/*_test.go (not recursive).
func Decls(dir string) ([]string, error) {
	entries, err := os.ReadDir(dir)
	if err != nil {
		return nil, err
	}
	seen := map[string]bool{}
	fset := token.NewFileSet()
	for _, e := range entries {
		if e.IsDir() || !strings.HasSuffix(e.Name(), "_test.go") {
			continue
		}
		f, err := parser.ParseFile(fset, filepath.Join(dir, e.Name()), nil, parser.SkipObjectResolution)
		if err != nil {
			return nil, fmt.Errorf("parse %s: %w", e.Name(), err)
		}
		for _, name := range declNames(f) {
			seen[name] = true
		}
	}
	out := make([]string, 0, len(seen))
	for name := range seen {
		out = append(out, name)
	}
	sort.Strings(out)
	return out, nil
}

// declNames lists top-level funcs (not methods), types, vars and consts, excluding "_".
func declNames(f *ast.File) []string {
	var names []string
	add := func(n string) {
		if n != "_" {
			names = append(names, n)
		}
	}
	for _, decl := range f.Decls {
		switch d := decl.(type) {
		case *ast.FuncDecl:
			if d.Recv == nil {
				add(d.Name.Name)
			}
		case *ast.GenDecl:
			for _, spec := range d.Specs {
				switch s := spec.(type) {
				case *ast.TypeSpec:
					add(s.Name.Name)
				case *ast.ValueSpec:
					for _, n := range s.Names {
						add(n.Name)
					}
				}
			}
		}
	}
	return names
}
```

- [ ] **Step 5: Implement `tools/gohelper/main.go`**

```go
// AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
// Command gohelper gives the Python backend reliable Go source analysis and editing.
package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
)

const usage = `usage:
  gohelper funcs <dir>
  gohelper decls <dir>
  gohelper merge <test_file> <snippet_file>
  gohelper prune <test_file> <TestName>...`

func main() {
	if err := run(os.Args[1:], os.Stdout); err != nil {
		fmt.Fprintln(os.Stderr, "gohelper:", err)
		os.Exit(1)
	}
}

func run(args []string, stdout io.Writer) error {
	if len(args) < 2 {
		return errors.New(usage)
	}
	switch args[0] {
	case "funcs":
		out, err := Funcs(args[1])
		if err != nil {
			return err
		}
		return json.NewEncoder(stdout).Encode(out)
	case "decls":
		out, err := Decls(args[1])
		if err != nil {
			return err
		}
		return json.NewEncoder(stdout).Encode(out)
	case "merge":
		if len(args) != 3 {
			return errors.New(usage)
		}
		return Merge(args[1], args[2])
	case "prune":
		return Prune(args[1], args[2:])
	default:
		return errors.New(usage)
	}
}
```

`Merge` and `Prune` don't exist yet, so add temporary stubs at the bottom of `funcs.go`. Task 3 deletes them.
```go
func Merge(testFile, snippetFile string) error { return errors.New("not implemented") }
func Prune(testFile string, names []string) error { return errors.New("not implemented") }
```
(add `"errors"` to the `funcs.go` imports).

- [ ] **Step 6: Run the tests to verify they pass**

Run: `go test ./...` (in `tools/gohelper`, or the Docker variant)
Expected: `ok gohelper`.

- [ ] **Step 7: Commit**

```bash
git add tools/gohelper
git commit -m "feat(gohelper): funcs and decls subcommands"
```

---

### Task 3: gohelper — append-only `merge` and `prune`

**Files:**
- Create: `tools/gohelper/merge.go`
- Modify: `tools/gohelper/funcs.go` (delete the two stubs and the `errors` import if unused)
- Test: `tools/gohelper/merge_test.go`

**Interfaces:**
- Consumes: `Decls(dir)` and `declNames(f)` from Task 2.
- Produces CLI: `gohelper merge <test_file> <snippet_file>` exits 0 and rewrites/creates `test_file`. It exits 1 with a stderr message containing `duplicate declaration: <name>`, `package mismatch`, or a parse error. `test_file` is untouched on failure. `gohelper prune <test_file> <names...>` removes those top-level functions and unused imports. Both write gofmt'd output and drop unused imports.

- [ ] **Step 1: Write the failing tests** — `tools/gohelper/merge_test.go`

```go
// AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
package main

import (
	"go/parser"
	"go/token"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func read(t *testing.T, path string) string {
	t.Helper()
	b, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	return string(b)
}

func mustParse(t *testing.T, src string) {
	t.Helper()
	if _, err := parser.ParseFile(token.NewFileSet(), "x.go", src, 0); err != nil {
		t.Fatalf("output does not parse: %v\n%s", err, src)
	}
}

func TestMerge_CreatesFileAndDropsUnusedImports(t *testing.T) {
	dir := t.TempDir()
	writeFile(t, dir, "snip.go", "package p\n\nimport (\n\t\"math\"\n\t\"testing\"\n)\n\n// TestMean checks the zero case.\nfunc TestMean(t *testing.T) {\n\tif Mean(nil) != 0 {\n\t\tt.Fatal(\"x\")\n\t}\n}\n")
	target := filepath.Join(dir, "a_test.go")

	if err := Merge(target, filepath.Join(dir, "snip.go")); err != nil {
		t.Fatal(err)
	}
	got := read(t, target)
	mustParse(t, got)
	if !strings.HasPrefix(got, "package p\n") || !strings.Contains(got, "func TestMean(") {
		t.Fatalf("unexpected output:\n%s", got)
	}
	if strings.Contains(got, `"math"`) {
		t.Fatalf("unused import kept:\n%s", got)
	}
	if !strings.Contains(got, "// TestMean checks the zero case.") {
		t.Fatalf("doc comment lost:\n%s", got)
	}
}

func TestMerge_AppendsAndKeepsExisting(t *testing.T) {
	dir := t.TempDir()
	writeFile(t, dir, "a_test.go", "package p\n\nimport \"testing\"\n\nfunc TestA(t *testing.T) {}\n")
	writeFile(t, dir, "snip.go", "package p\n\nimport (\n\t\"errors\"\n\t\"testing\"\n)\n\nfunc TestB(t *testing.T) {\n\t_ = errors.New(\"x\")\n}\n")
	target := filepath.Join(dir, "a_test.go")

	if err := Merge(target, filepath.Join(dir, "snip.go")); err != nil {
		t.Fatal(err)
	}
	got := read(t, target)
	mustParse(t, got)
	for _, want := range []string{"func TestA(", "func TestB(", `"errors"`} {
		if !strings.Contains(got, want) {
			t.Fatalf("missing %q in:\n%s", want, got)
		}
	}
	if strings.Count(got, `"testing"`) != 1 {
		t.Fatalf("testing import not deduplicated:\n%s", got)
	}
	if strings.Index(got, "func TestA(") > strings.Index(got, "func TestB(") {
		t.Fatalf("existing tests must stay first:\n%s", got)
	}
}

func TestMerge_RejectsDuplicateInSameFile(t *testing.T) {
	dir := t.TempDir()
	orig := "package p\n\nimport \"testing\"\n\nfunc TestA(t *testing.T) {}\n"
	writeFile(t, dir, "a_test.go", orig)
	writeFile(t, dir, "snip.go", "package p\n\nimport \"testing\"\n\nfunc TestA(t *testing.T) {}\n")

	err := Merge(filepath.Join(dir, "a_test.go"), filepath.Join(dir, "snip.go"))
	if err == nil || !strings.Contains(err.Error(), "duplicate declaration: TestA") {
		t.Fatalf("want duplicate error, got %v", err)
	}
	if read(t, filepath.Join(dir, "a_test.go")) != orig {
		t.Fatal("file modified on failure")
	}
}

func TestMerge_RejectsDuplicateFromSiblingTestFile(t *testing.T) {
	dir := t.TempDir()
	writeFile(t, dir, "b_test.go", "package p\n\nfunc approxEqual(a, b float64) bool { return a == b }\n")
	writeFile(t, dir, "snip.go", "package p\n\nfunc approxEqual(a, b float64) bool { return true }\n")

	err := Merge(filepath.Join(dir, "a_test.go"), filepath.Join(dir, "snip.go"))
	if err == nil || !strings.Contains(err.Error(), "duplicate declaration: approxEqual") {
		t.Fatalf("want duplicate error, got %v", err)
	}
	if _, statErr := os.Stat(filepath.Join(dir, "a_test.go")); !os.IsNotExist(statErr) {
		t.Fatal("file created on failure")
	}
}

func TestMerge_PackageMismatch(t *testing.T) {
	dir := t.TempDir()
	writeFile(t, dir, "a_test.go", "package p\n")
	writeFile(t, dir, "snip.go", "package q\n\nfunc TestQ() {}\n")
	err := Merge(filepath.Join(dir, "a_test.go"), filepath.Join(dir, "snip.go"))
	if err == nil || !strings.Contains(err.Error(), "package mismatch") {
		t.Fatalf("want package mismatch, got %v", err)
	}
}

func TestMerge_SnippetSyntaxError(t *testing.T) {
	dir := t.TempDir()
	writeFile(t, dir, "snip.go", "package p\n\nfunc TestBroken( {\n")
	err := Merge(filepath.Join(dir, "a_test.go"), filepath.Join(dir, "snip.go"))
	if err == nil || !strings.Contains(err.Error(), "snippet") {
		t.Fatalf("want snippet parse error, got %v", err)
	}
}

func TestPrune_RemovesNamedTestsAndUnusedImports(t *testing.T) {
	dir := t.TempDir()
	writeFile(t, dir, "a_test.go", "package p\n\nimport (\n\t\"errors\"\n\t\"testing\"\n)\n\nfunc TestA(t *testing.T) {\n\t_ = errors.New(\"x\")\n}\n\nfunc TestB(t *testing.T) {}\n")
	target := filepath.Join(dir, "a_test.go")

	if err := Prune(target, []string{"TestA"}); err != nil {
		t.Fatal(err)
	}
	got := read(t, target)
	mustParse(t, got)
	if strings.Contains(got, "TestA") || strings.Contains(got, `"errors"`) || !strings.Contains(got, "func TestB(") {
		t.Fatalf("unexpected prune result:\n%s", got)
	}
}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `go test ./...` → Expected: FAIL (stubs return "not implemented").

- [ ] **Step 3: Implement `tools/gohelper/merge.go`** and delete the stubs from `funcs.go`

```go
// AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
package main

import (
	"bytes"
	"errors"
	"fmt"
	"go/ast"
	"go/format"
	"go/parser"
	"go/token"
	"io/fs"
	"os"
	"path"
	"path/filepath"
	"strconv"
)

type importSpec struct{ Name, Path string }

func (s importSpec) localName() string {
	if s.Name != "" {
		return s.Name
	}
	return path.Base(s.Path)
}

// Merge appends the snippet's declarations and imports to testFile (creating it if needed).
// It never modifies existing declarations and fails on any identifier collision in the package's tests.
func Merge(testFile, snippetFile string) error {
	snipSrc, err := os.ReadFile(snippetFile)
	if err != nil {
		return err
	}
	fset := token.NewFileSet()
	snip, err := parser.ParseFile(fset, "snippet.go", snipSrc, parser.ParseComments)
	if err != nil {
		return fmt.Errorf("snippet: %w", err)
	}

	var base *ast.File
	baseSrc, err := os.ReadFile(testFile)
	switch {
	case err == nil:
		base, err = parser.ParseFile(fset, testFile, baseSrc, parser.ParseComments)
		if err != nil {
			return fmt.Errorf("existing test file: %w", err)
		}
		if base.Name.Name != snip.Name.Name {
			return fmt.Errorf("package mismatch: %s has %q, snippet has %q", filepath.Base(testFile), base.Name.Name, snip.Name.Name)
		}
	case errors.Is(err, fs.ErrNotExist):
		baseSrc = nil
	default:
		return err
	}

	existing, err := Decls(filepath.Dir(testFile))
	if err != nil && !errors.Is(err, fs.ErrNotExist) {
		return err
	}
	taken := map[string]bool{}
	for _, n := range existing {
		taken[n] = true
	}
	for _, n := range declNames(snip) {
		if taken[n] {
			return fmt.Errorf("duplicate declaration: %s", n)
		}
	}

	var imports []importSpec
	var body bytes.Buffer
	if base != nil {
		imports = append(imports, importsOf(base)...)
		writeDecls(&body, fset, base, baseSrc, nil)
	}
	imports = append(imports, importsOf(snip)...)
	writeDecls(&body, fset, snip, snipSrc, nil)

	out, err := tidy(render(snip.Name.Name, imports, body.Bytes()))
	if err != nil {
		return fmt.Errorf("merged result: %w", err)
	}
	return writeAtomic(testFile, out)
}

// Prune removes the named top-level functions from testFile and drops unused imports.
func Prune(testFile string, names []string) error {
	src, err := os.ReadFile(testFile)
	if err != nil {
		return err
	}
	fset := token.NewFileSet()
	f, err := parser.ParseFile(fset, testFile, src, parser.ParseComments)
	if err != nil {
		return err
	}
	drop := map[string]bool{}
	for _, n := range names {
		drop[n] = true
	}
	var body bytes.Buffer
	writeDecls(&body, fset, f, src, func(d ast.Decl) bool {
		fd, ok := d.(*ast.FuncDecl)
		return ok && fd.Recv == nil && drop[fd.Name.Name]
	})
	out, err := tidy(render(f.Name.Name, importsOf(f), body.Bytes()))
	if err != nil {
		return err
	}
	return writeAtomic(testFile, out)
}

func importsOf(f *ast.File) []importSpec {
	var out []importSpec
	for _, s := range f.Imports {
		p, _ := strconv.Unquote(s.Path.Value)
		spec := importSpec{Path: p}
		if s.Name != nil {
			spec.Name = s.Name.Name
		}
		out = append(out, spec)
	}
	return out
}

// writeDecls copies each non-import declaration's source text (including its doc comment).
func writeDecls(buf *bytes.Buffer, fset *token.FileSet, f *ast.File, src []byte, skip func(ast.Decl) bool) {
	for _, decl := range f.Decls {
		if gd, ok := decl.(*ast.GenDecl); ok && gd.Tok == token.IMPORT {
			continue
		}
		if skip != nil && skip(decl) {
			continue
		}
		start := decl.Pos()
		switch d := decl.(type) {
		case *ast.FuncDecl:
			if d.Doc != nil {
				start = d.Doc.Pos()
			}
		case *ast.GenDecl:
			if d.Doc != nil {
				start = d.Doc.Pos()
			}
		}
		buf.Write(src[fset.Position(start).Offset:fset.Position(decl.End()).Offset])
		buf.WriteString("\n\n")
	}
}

func render(pkg string, imports []importSpec, body []byte) []byte {
	var buf bytes.Buffer
	fmt.Fprintf(&buf, "package %s\n\n", pkg)
	seen := map[importSpec]bool{}
	var uniq []importSpec
	for _, s := range imports {
		if !seen[s] {
			seen[s] = true
			uniq = append(uniq, s)
		}
	}
	if len(uniq) > 0 {
		buf.WriteString("import (\n")
		for _, s := range uniq {
			if s.Name != "" {
				fmt.Fprintf(&buf, "\t%s %q\n", s.Name, s.Path)
			} else {
				fmt.Fprintf(&buf, "\t%q\n", s.Path)
			}
		}
		buf.WriteString(")\n\n")
	}
	buf.Write(body)
	return buf.Bytes()
}

// tidy drops imports whose package name is never referenced, then gofmts.
func tidy(src []byte) ([]byte, error) {
	fset := token.NewFileSet()
	f, err := parser.ParseFile(fset, "", src, parser.ParseComments)
	if err != nil {
		return nil, err
	}
	used := map[string]bool{}
	ast.Inspect(f, func(n ast.Node) bool {
		if sel, ok := n.(*ast.SelectorExpr); ok {
			if id, ok := sel.X.(*ast.Ident); ok {
				used[id.Name] = true
			}
		}
		return true
	})
	var keep []importSpec
	for _, s := range importsOf(f) {
		if s.Name == "_" || s.Name == "." || used[s.localName()] {
			keep = append(keep, s)
		}
	}
	var body bytes.Buffer
	writeDecls(&body, fset, f, src, nil)
	return format.Source(render(f.Name.Name, keep, body.Bytes()))
}

func writeAtomic(dst string, data []byte) error {
	tmp, err := os.CreateTemp(filepath.Dir(dst), ".gohelper-*")
	if err != nil {
		return err
	}
	defer os.Remove(tmp.Name())
	if _, err := tmp.Write(data); err != nil {
		tmp.Close()
		return err
	}
	if err := tmp.Close(); err != nil {
		return err
	}
	if err := os.Chmod(tmp.Name(), 0o644); err != nil {
		return err
	}
	return os.Rename(tmp.Name(), dst)
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `go test ./...` → Expected: `ok gohelper`. Also run `go vet ./...` → no output.

- [ ] **Step 5: Commit**

```bash
git add tools/gohelper
git commit -m "feat(gohelper): append-only merge and prune with import tidying"
```

---

### Task 4: Coverage profile parsing and summaries

**Files:**
- Create: `backend/app/coverage.py`
- Test: `backend/tests/test_coverage.py`

**Interfaces:**
- Consumes: `Block`, `FuncInfo`, `FuncKey`, `FuncCoverage`, `FileCoverage`, `CoverageReport` (Task 1).
- Produces: `parse_profile(text: str, module: str) -> dict[Block, bool]` (module-relative file paths; duplicate blocks OR-merged; raises `ValueError` on malformed lines) and `summarize(hits: dict[Block, bool], funcs: list[FuncInfo]) -> CoverageReport` (percentages rounded to 2 dp; `uncovered_lines` merged and sorted; functions sorted by `(file, receiver, name)`).

- [ ] **Step 1: Write the failing tests** — `backend/tests/test_coverage.py`

```python
import pytest

from app.coverage import parse_profile, summarize
from app.models import FuncInfo, FuncKey

PROFILE = """mode: set
example.com/m/a.go:3.20,5.2 1 1
example.com/m/a.go:5.2,7.3 2 0
example.com/m/a.go:9.30,11.2 1 0
example.com/m/sub/b.go:1.1,2.2 3 1
example.com/m/a.go:3.20,5.2 1 0
"""

FUNCS = [
    FuncInfo(key=FuncKey(file="a.go", name="Abs"), package="m", start_line=3, end_line=8, exported=True),
    FuncInfo(key=FuncKey(file="a.go", receiver="T", name="Mean"), package="m", start_line=9, end_line=11, exported=True),
    FuncInfo(key=FuncKey(file="sub/b.go", name="B"), package="sub", start_line=1, end_line=2, exported=True),
]


def test_parse_profile_strips_module_and_or_merges_duplicates():
    hits = parse_profile(PROFILE, "example.com/m")
    assert len(hits) == 4
    by_id = {b.id: h for b, h in hits.items()}
    assert by_id["a.go:3.20,5.2"] is True  # one run hit it, the duplicate did not
    assert by_id["sub/b.go:1.1,2.2"] is True
    assert by_id["a.go:5.2,7.3"] is False


def test_parse_profile_rejects_garbage():
    with pytest.raises(ValueError, match="unrecognized coverage line"):
        parse_profile("mode: set\nnot a profile line\n", "example.com/m")


def test_parse_profile_empty_is_empty():
    assert parse_profile("mode: set\n", "example.com/m") == {}


def test_summarize_totals_files_and_functions():
    report = summarize(parse_profile(PROFILE, "example.com/m"), FUNCS)
    assert (report.total_statements, report.covered_statements) == (7, 4)
    assert report.percent == 57.14
    files = {f.file: f for f in report.files}
    assert (files["a.go"].statements, files["a.go"].covered, files["a.go"].percent) == (4, 1, 25.0)
    assert files["sub/b.go"].percent == 100.0

    fns = {f.key.label(): f for f in report.functions}
    assert (fns["Abs"].statements, fns["Abs"].covered) == (3, 1)
    assert fns["Abs"].uncovered_lines == [(5, 7)]
    assert fns["T.Mean"].uncovered_lines == [(9, 11)]
    assert fns["B"].uncovered_lines == []
    assert sorted(report.covered_block_ids) == ["a.go:3.20,5.2", "sub/b.go:1.1,2.2"]


def test_summarize_merges_adjacent_uncovered_ranges():
    profile = "mode: set\nm/a.go:3.1,4.2 1 0\nm/a.go:4.2,6.1 1 0\nm/a.go:8.1,8.9 1 0\n"
    funcs = [FuncInfo(key=FuncKey(file="a.go", name="F"), package="m", start_line=1, end_line=9, exported=True)]
    report = summarize(parse_profile(profile, "m"), funcs)
    assert report.functions[0].uncovered_lines == [(3, 6), (8, 8)]


def test_summarize_zero_statements_is_zero_percent():
    report = summarize({}, [])
    assert report.percent == 0.0 and report.files == [] and report.functions == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_coverage.py -q` → Expected: FAIL, `ModuleNotFoundError: app.coverage`.

- [ ] **Step 3: Implement `backend/app/coverage.py`**

```python
# AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
"""Parse `go test -coverprofile` output and attribute statements to files and functions."""
from __future__ import annotations

import re
from collections import defaultdict

from app.models import Block, CoverageReport, FileCoverage, FuncCoverage, FuncInfo, FuncKey

_LINE = re.compile(
    r"^(?P<file>.+):(?P<sl>\d+)\.(?P<sc>\d+),(?P<el>\d+)\.(?P<ec>\d+) (?P<n>\d+) (?P<count>\d+)$"
)


def parse_profile(text: str, module: str) -> dict[Block, bool]:
    prefix = module + "/"
    hits: dict[Block, bool] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("mode:"):
            continue
        m = _LINE.match(line)
        if m is None:
            raise ValueError(f"unrecognized coverage line: {line!r}")
        file = m["file"].removeprefix(prefix)
        block = Block(file=file, start_line=int(m["sl"]), start_col=int(m["sc"]),
                      end_line=int(m["el"]), end_col=int(m["ec"]), statements=int(m["n"]))
        hits[block] = hits.get(block, False) or int(m["count"]) > 0
    return hits


def _pct(covered: int, total: int) -> float:
    return round(100.0 * covered / total, 2) if total else 0.0


def _merge_ranges(ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for start, end in sorted(ranges):
        if merged and start <= merged[-1][1] + 1:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def summarize(hits: dict[Block, bool], funcs: list[FuncInfo]) -> CoverageReport:
    funcs_by_file: dict[str, list[FuncInfo]] = defaultdict(list)
    for f in funcs:
        funcs_by_file[f.key.file].append(f)

    file_totals: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    fn_totals: dict[FuncKey, list[int]] = {}
    fn_uncovered: dict[FuncKey, list[tuple[int, int]]] = defaultdict(list)

    for block, hit in hits.items():
        ft = file_totals[block.file]
        ft[0] += block.statements
        ft[1] += block.statements if hit else 0
        owner = next((f for f in funcs_by_file.get(block.file, [])
                      if f.start_line <= block.start_line <= f.end_line), None)
        if owner is None:
            continue
        totals = fn_totals.setdefault(owner.key, [0, 0])
        totals[0] += block.statements
        totals[1] += block.statements if hit else 0
        if not hit:
            fn_uncovered[owner.key].append((block.start_line, block.end_line))

    total = sum(t[0] for t in file_totals.values())
    covered = sum(t[1] for t in file_totals.values())
    files = [FileCoverage(file=f, statements=t[0], covered=t[1], percent=_pct(t[1], t[0]))
             for f, t in sorted(file_totals.items())]
    functions = [
        FuncCoverage(key=k, statements=t[0], covered=t[1], uncovered_lines=_merge_ranges(fn_uncovered[k]))
        for k, t in sorted(fn_totals.items(), key=lambda kv: (kv[0].file, kv[0].receiver, kv[0].name))
    ]
    return CoverageReport(
        total_statements=total, covered_statements=covered, percent=_pct(covered, total),
        files=files, functions=functions,
        covered_block_ids=sorted(b.id for b, h in hits.items() if h),
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_coverage.py -q` → Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/coverage.py backend/tests/test_coverage.py
git commit -m "feat(backend): coverage profile parsing and summaries"
```

---

### Task 5: Workspace — path guard, copy, seed files, snapshot/restore

**Files:**
- Create: `backend/app/workspace.py`
- Test: `backend/tests/test_workspace.py`

**Interfaces:**
- Produces:
  - `SEED_FILE = "zz_coverage_seed_test.go"`, `class WorkspaceError(ValueError)`
  - `resolve_repo(repos_dir: Path, repo_path: str) -> Path`
  - `test_path_for(source_file: str) -> str` (`"sub/x.go"` → `"sub/x_test.go"`)
  - `class Workspace` with attributes `root: Path` and `scratch: Path` and methods:
    - `create(work_dir: Path, job_id: str, source: Path) -> Workspace` (classmethod)
    - `delete_existing_tests() -> list[str]`
    - `seed_packages(packages: list[tuple[str, str]]) -> list[str]`, where `(rel_dir, package_name)` and `rel_dir` is `"."` for the root
    - `test_files(include_seeds: bool = False) -> list[str]`
    - `read(rel: str) -> str | None`, `write_test(rel: str, content: str) -> None`
    - `snapshot(rels: list[str]) -> dict[str, str | None]`, `restore(snap) -> None`
    - `path(rel: str) -> Path` (guarded)

- [ ] **Step 1: Write the failing tests** — `backend/tests/test_workspace.py`

```python
from pathlib import Path

import pytest

from app.workspace import SEED_FILE, Workspace, WorkspaceError, resolve_repo, test_path_for


def make_repo(root: Path) -> Path:
    repo = root / "repos" / "demo"
    (repo / ".git").mkdir(parents=True)
    (repo / ".git" / "HEAD").write_text("ref")
    (repo / "go.mod").write_text("module example.com/demo\n\ngo 1.17\n")
    (repo / "a.go").write_text("package demo\n")
    (repo / "a_test.go").write_text("package demo\n")
    (repo / "sub").mkdir()
    (repo / "sub" / "b.go").write_text("package sub\n")
    return repo


def test_resolve_repo_accepts_relative_and_container_absolute(tmp_path):
    repo = make_repo(tmp_path)
    repos = tmp_path / "repos"
    assert resolve_repo(repos, "demo") == repo.resolve()
    assert resolve_repo(repos, str(repo)) == repo.resolve()


def test_resolve_repo_rejects_traversal(tmp_path):
    make_repo(tmp_path)
    with pytest.raises(WorkspaceError, match="inside"):
        resolve_repo(tmp_path / "repos", "../../etc")


def test_resolve_repo_explains_host_paths(tmp_path):
    make_repo(tmp_path)
    elsewhere = tmp_path / "Users" / "me" / "code" / "stats"
    elsewhere.mkdir(parents=True)
    with pytest.raises(WorkspaceError, match=r"\./repos"):
        resolve_repo(tmp_path / "repos", str(elsewhere))


def test_resolve_repo_requires_go_mod(tmp_path):
    (tmp_path / "repos" / "nomod").mkdir(parents=True)
    with pytest.raises(WorkspaceError, match="go.mod"):
        resolve_repo(tmp_path / "repos", "nomod")


def test_test_path_for():
    assert test_path_for("mean.go") == "mean_test.go"
    assert test_path_for("sub/x.go") == "sub/x_test.go"


def test_create_copies_without_git_and_leaves_source_untouched(tmp_path):
    repo = make_repo(tmp_path)
    ws = Workspace.create(tmp_path / "work", "job1", repo)
    assert (ws.root / "a.go").exists() and not (ws.root / ".git").exists()
    removed = ws.delete_existing_tests()
    assert removed == ["a_test.go"]
    assert (repo / "a_test.go").exists(), "source repo must never be modified"
    assert ws.scratch.is_dir() and not ws.scratch.is_relative_to(ws.root)


def test_seed_packages_only_where_no_tests(tmp_path):
    ws = Workspace.create(tmp_path / "work", "job1", make_repo(tmp_path))
    seeded = ws.seed_packages([(".", "demo"), ("sub", "sub")])  # root still has a_test.go
    assert seeded == [f"sub/{SEED_FILE}"]
    assert ws.read(f"sub/{SEED_FILE}") == "package sub\n"
    assert ws.test_files() == ["a_test.go"]
    assert ws.test_files(include_seeds=True) == ["a_test.go", f"sub/{SEED_FILE}"]


def test_write_test_guards(tmp_path):
    ws = Workspace.create(tmp_path / "work", "job1", make_repo(tmp_path))
    with pytest.raises(WorkspaceError):
        ws.write_test("a.go", "package demo\n")
    with pytest.raises(WorkspaceError):
        ws.write_test("../escape_test.go", "x")
    ws.write_test("sub/b_test.go", "package sub\n")
    assert ws.read("sub/b_test.go") == "package sub\n"


def test_snapshot_restore_handles_absent_files(tmp_path):
    ws = Workspace.create(tmp_path / "work", "job1", make_repo(tmp_path))
    snap = ws.snapshot(["new_test.go", "go.mod"])
    ws.write_test("new_test.go", "package demo\n")
    (ws.root / "go.mod").write_text("module changed\n")
    ws.restore(snap)
    assert ws.read("new_test.go") is None
    assert ws.read("go.mod") == "module example.com/demo\n\ngo 1.17\n"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_workspace.py -q` → Expected: FAIL, `ModuleNotFoundError: app.workspace`.

- [ ] **Step 3: Implement `backend/app/workspace.py`**

```python
# AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
"""A throwaway copy of the user's repo. The only place generated files are ever written."""
from __future__ import annotations

import os
import posixpath
import shutil
from pathlib import Path, PurePosixPath, PureWindowsPath

SEED_FILE = "zz_coverage_seed_test.go"
_RESTORABLE = {"go.mod", "go.sum"}


class WorkspaceError(ValueError):
    pass


def _looks_absolute(repo_path: str) -> bool:
    # Check both path flavours: tests run on a Windows host, the app runs on Linux.
    return (repo_path.startswith(("/", "\\", "~")) or PurePosixPath(repo_path).is_absolute()
            or PureWindowsPath(repo_path).is_absolute())


def resolve_repo(repos_dir: Path, repo_path: str) -> Path:
    root = repos_dir.resolve()
    candidate = (root / repo_path).resolve()
    if not candidate.is_relative_to(root):
        if _looks_absolute(repo_path):
            raise WorkspaceError(
                f"{repo_path!r} looks like a path on your machine, which the container cannot see. "
                "Put the repo under ./repos (or set HOST_REPOS_DIR in .env) and pick it from the list."
            )
        raise WorkspaceError("repo_path must point inside the repos folder")
    if not (candidate / "go.mod").is_file():
        raise WorkspaceError(f"no go.mod found in {repo_path!r}; choose the module root")
    return candidate


def test_path_for(source_file: str) -> str:
    stem, _ = posixpath.splitext(source_file)
    return f"{stem}_test.go"


test_path_for.__test__ = False  # imported by test modules; not a pytest test


class Workspace:
    def __init__(self, root: Path, scratch: Path):
        self.root = root.resolve()
        self.scratch = scratch.resolve()

    @classmethod
    def create(cls, work_dir: Path, job_id: str, source: Path) -> Workspace:
        base = work_dir / job_id
        root = base / "repo"
        shutil.copytree(source, root, ignore=shutil.ignore_patterns(".git"))
        (base / "scratch").mkdir(parents=True, exist_ok=True)
        return cls(root, base / "scratch")

    def path(self, rel: str) -> Path:
        p = (self.root / rel).resolve()
        if not p.is_relative_to(self.root):
            raise WorkspaceError(f"path escapes workspace: {rel!r}")
        return p

    def _rel(self, p: Path) -> str:
        return p.relative_to(self.root).as_posix()

    def test_files(self, include_seeds: bool = False) -> list[str]:
        files = sorted(self._rel(p) for p in self.root.rglob("*_test.go"))
        return files if include_seeds else [f for f in files if posixpath.basename(f) != SEED_FILE]

    def delete_existing_tests(self) -> list[str]:
        removed = self.test_files(include_seeds=True)
        for rel in removed:
            self.path(rel).unlink()
        return removed

    def seed_packages(self, packages: list[tuple[str, str]]) -> list[str]:
        seeded = []
        for rel_dir, name in packages:
            directory = self.path(rel_dir)
            if any(directory.glob("*_test.go")):
                continue
            rel = posixpath.normpath(posixpath.join(rel_dir, SEED_FILE))
            self.path(rel).write_text(f"package {name}\n")
            seeded.append(rel)
        return seeded

    def read(self, rel: str) -> str | None:
        p = self.path(rel)
        return p.read_text() if p.exists() else None

    def write_test(self, rel: str, content: str) -> None:
        if not rel.endswith("_test.go"):
            raise WorkspaceError(f"only *_test.go files may be written: {rel!r}")
        self._write(self.path(rel), content)

    def snapshot(self, rels: list[str]) -> dict[str, str | None]:
        return {rel: self.read(rel) for rel in rels}

    def restore(self, snap: dict[str, str | None]) -> None:
        for rel, content in snap.items():
            if not (rel.endswith("_test.go") or rel in _RESTORABLE):
                raise WorkspaceError(f"refusing to restore non-test file {rel!r}")
            p = self.path(rel)
            if content is None:
                p.unlink(missing_ok=True)
            else:
                self._write(p, content)

    @staticmethod
    def _write(p: Path, content: str) -> None:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(p.name + ".tmp")
        tmp.write_text(content)
        os.replace(tmp, p)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_workspace.py -q` → Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/workspace.py backend/tests/test_workspace.py
git commit -m "feat(backend): workspace copy, seeding and snapshot/restore"
```

---

### Task 6: Command runner, GoTools, backend image, Go fixtures

**Files:**
- Create: `backend/app/gotools.py`, `backend/Dockerfile`
- Create: `backend/tests/fixtures/gomod/go.mod`, `.../calc.go`, `.../cmd/tool/main.go`, `.../examples/demo/demo.go`
- Create: `backend/tests/fixtures/broken/go.mod`, `.../broken.go`
- Create: `backend/tests/integration/__init__.py`, `backend/tests/integration/conftest.py`, `backend/tests/integration/test_gotools.py`
- Test: `backend/tests/test_gotools_unit.py`

**Interfaces:**
- Consumes: `Settings`, `FuncInfo`, `FuncKey`.
- Produces:
  - `CommandResult(argv, exit_code, stdout, stderr, duration_ms, timed_out, cancelled)`, a dataclass with property `combined: str`
  - `async run(argv: list[str], cwd: Path, timeout: float, env: dict[str, str], cancel: asyncio.Event | None = None, max_chars: int = 20_000) -> CommandResult`
  - `go_env(settings) -> dict[str, str]`, `read_module_info(root: Path) -> tuple[str, str]` (module path, go version)
  - `GoPackage(import_path, rel_dir, name)`, a frozen dataclass
  - `class GoToolError(RuntimeError)` with attribute `result`
  - `class GoTools(root: Path, settings: Settings, cancel: asyncio.Event | None = None)` with async methods:
    - `list_packages(exclude: list[str]) -> list[GoPackage]`
    - `compile(pkgs) -> CommandResult`, `vet(pkgs) -> CommandResult`, `test(pkgs, profile: Path) -> CommandResult`
    - `funcs() -> list[FuncInfo]`, `decls(rel_dir: str) -> list[str]`
    - `merge(test_file: str, snippet: Path) -> CommandResult`, `prune(test_file: str, names: list[str]) -> CommandResult`
  - Pure helpers `iter_json(text)` and `is_excluded(rel_dir, patterns)`.

- [ ] **Step 1: Write unit tests for the pure helpers** — `backend/tests/test_gotools_unit.py`

```python
from pathlib import Path

from app.config import Settings
from app.gotools import go_env, is_excluded, iter_json, read_module_info


def test_iter_json_reads_concatenated_objects():
    assert [o["a"] for o in iter_json('{"a": 1}\n{"a": 2}\n  ')] == [1, 2]


def test_is_excluded_matches_dir_and_children():
    pats = ["examples/**", "testdata/**"]
    assert is_excluded("examples", pats)
    assert is_excluded("examples/functions", pats)
    assert not is_excluded(".", pats)
    assert not is_excluded("sub", pats)


def test_read_module_info(tmp_path: Path):
    (tmp_path / "go.mod").write_text('module github.com/montanaflynn/stats\n\ngo 1.17\n')
    assert read_module_info(tmp_path) == ("github.com/montanaflynn/stats", "1.17")
    (tmp_path / "go.mod").write_text("module x\n")
    assert read_module_info(tmp_path) == ("x", "1.16")


def test_go_env_is_an_allowlist(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "secret")
    monkeypatch.setenv("PATH", "/usr/bin")
    env = go_env(Settings())
    assert "GROQ_API_KEY" not in env
    assert env["GOFLAGS"] == "-mod=readonly"
    assert env["GOTOOLCHAIN"] == "local"
    assert env["CGO_ENABLED"] == "0"
    assert env["PATH"] == "/usr/bin"
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_gotools_unit.py -q` → Expected: FAIL, `ModuleNotFoundError: app.gotools`.

- [ ] **Step 3: Implement `backend/app/gotools.py`**

```python
# AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
"""The only module that executes commands. Fixed argv lists, scrubbed env, timeouts, process-group kill."""
from __future__ import annotations

import asyncio
import json
import os
import re
import signal
import time
from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any, Iterator

from app.config import Settings
from app.models import FuncInfo, FuncKey

_PASSTHROUGH = ("PATH", "HOME", "TMPDIR", "GOPROXY", "GOPRIVATE", "GONOSUMDB",
                "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY")


@dataclass
class CommandResult:
    argv: list[str]
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool = False
    cancelled: bool = False

    @property
    def combined(self) -> str:
        return "\n".join(part for part in (self.stdout.strip(), self.stderr.strip()) if part)


class GoToolError(RuntimeError):
    def __init__(self, message: str, result: CommandResult):
        super().__init__(f"{message}: {result.combined[:2000]}")
        self.result = result


@dataclass(frozen=True)
class GoPackage:
    import_path: str
    rel_dir: str
    name: str


def _cap(data: bytes, max_chars: int) -> str:
    text = data.decode("utf-8", errors="replace")
    return text if len(text) <= max_chars else text[:max_chars] + "\n…[output truncated]"


def _kill_group(proc: asyncio.subprocess.Process) -> None:
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


async def run(argv: list[str], cwd: Path, timeout: float, env: dict[str, str],
              cancel: asyncio.Event | None = None, max_chars: int = 20_000) -> CommandResult:
    started = time.monotonic()
    proc = await asyncio.create_subprocess_exec(
        *argv, cwd=str(cwd), env=env,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        start_new_session=True,
    )
    comm = asyncio.ensure_future(proc.communicate())
    waiters: set[asyncio.Future[Any]] = {comm}
    cancel_wait = asyncio.ensure_future(cancel.wait()) if cancel else None
    if cancel_wait:
        waiters.add(cancel_wait)
    try:
        done, _ = await asyncio.wait(waiters, timeout=timeout, return_when=asyncio.FIRST_COMPLETED)
        finished = comm in done
        if not finished:
            _kill_group(proc)
        out, err = await comm
    finally:
        if cancel_wait:
            cancel_wait.cancel()
    return CommandResult(
        argv=argv,
        exit_code=proc.returncode if finished else -1,
        stdout=_cap(out, max_chars), stderr=_cap(err, max_chars),
        duration_ms=int((time.monotonic() - started) * 1000),
        timed_out=not finished and not (cancel is not None and cancel.is_set()),
        cancelled=cancel is not None and cancel.is_set(),
    )


def go_env(settings: Settings) -> dict[str, str]:
    env = {k: os.environ[k] for k in _PASSTHROUGH if k in os.environ}
    env.update(
        GOCACHE=str(settings.gocache), GOMODCACHE=str(settings.gomodcache),
        GOFLAGS="-mod=readonly", GOTOOLCHAIN="local", CGO_ENABLED="0", GOTELEMETRY="off",
    )
    return env


def read_module_info(root: Path) -> tuple[str, str]:
    text = (root / "go.mod").read_text()
    module = re.search(r"^module\s+(\S+)", text, re.M)
    go = re.search(r"^go\s+(\S+)", text, re.M)
    if module is None:
        raise ValueError("go.mod has no module directive")
    return module.group(1).strip('"'), go.group(1) if go else "1.16"


def iter_json(text: str) -> Iterator[dict[str, Any]]:
    decoder, i, n = json.JSONDecoder(), 0, len(text)
    while True:
        while i < n and text[i].isspace():
            i += 1
        if i >= n:
            return
        obj, i = decoder.raw_decode(text, i)
        yield obj


def is_excluded(rel_dir: str, patterns: list[str]) -> bool:
    return any(fnmatchcase(rel_dir, p) or fnmatchcase(rel_dir + "/", p) for p in patterns)


class GoTools:
    def __init__(self, root: Path, settings: Settings, cancel: asyncio.Event | None = None):
        self.root = root.resolve()
        self.settings = settings
        self.cancel = cancel
        self._env = go_env(settings)

    async def _run(self, argv: list[str], timeout: float | None = None) -> CommandResult:
        return await run(argv, self.root, timeout or self.settings.command_timeout_s, self._env,
                         self.cancel, self.settings.max_output_chars)

    async def list_packages(self, exclude: list[str]) -> list[GoPackage]:
        r = await self._run(["go", "list", "-json", "./..."])
        if r.exit_code != 0:
            raise GoToolError("go list failed", r)
        pkgs = []
        for obj in iter_json(r.stdout):
            if obj.get("Name") == "main" or not obj.get("GoFiles"):
                continue
            rel = Path(obj["Dir"]).resolve().relative_to(self.root).as_posix()
            if is_excluded(rel, exclude):
                continue
            pkgs.append(GoPackage(import_path=obj["ImportPath"], rel_dir=rel, name=obj["Name"]))
        return pkgs

    async def compile(self, pkgs: list[GoPackage]) -> CommandResult:
        return await self._run(["go", "test", "-count=1", "-run=^$", *[p.import_path for p in pkgs]])

    async def vet(self, pkgs: list[GoPackage]) -> CommandResult:
        return await self._run(["go", "vet", *[p.import_path for p in pkgs]])

    async def test(self, pkgs: list[GoPackage], profile: Path) -> CommandResult:
        return await self._run(["go", "test", "-count=2", "-covermode=set", f"-coverprofile={profile}",
                                f"-timeout={self.settings.test_timeout}", *[p.import_path for p in pkgs]])

    async def funcs(self) -> list[FuncInfo]:
        r = await self._run(["gohelper", "funcs", "."])
        if r.exit_code != 0:
            raise GoToolError("gohelper funcs failed", r)
        return [FuncInfo(key=FuncKey(file=o["file"], receiver=o["receiver"], name=o["name"]),
                         package=o["package"], start_line=o["start_line"], end_line=o["end_line"],
                         exported=o["exported"]) for o in json.loads(r.stdout)]

    async def decls(self, rel_dir: str) -> list[str]:
        r = await self._run(["gohelper", "decls", rel_dir])
        if r.exit_code != 0:
            raise GoToolError("gohelper decls failed", r)
        return json.loads(r.stdout)

    async def merge(self, test_file: str, snippet: Path) -> CommandResult:
        return await self._run(["gohelper", "merge", test_file, str(snippet)])

    async def prune(self, test_file: str, names: list[str]) -> CommandResult:
        return await self._run(["gohelper", "prune", test_file, *names])
```

- [ ] **Step 4: Run the unit tests to verify they pass**

Run: `uv run pytest tests/test_gotools_unit.py -q` → Expected: 4 passed.

- [ ] **Step 5: Create the Go fixtures**

`backend/tests/fixtures/gomod/go.mod`:
```
module example.com/fixture

go 1.17
```
`backend/tests/fixtures/gomod/calc.go`:
```go
package calc

import "errors"

// ErrNegative is returned for negative input.
var ErrNegative = errors.New("negative input")

// Abs returns the absolute value of x.
func Abs(x int) int {
	if x < 0 {
		return -x
	}
	return x
}

// Sqrt returns the integer square root of x.
func Sqrt(x int) (int, error) {
	if x < 0 {
		return 0, ErrNegative
	}
	r := 0
	for (r+1)*(r+1) <= x {
		r++
	}
	return r, nil
}
```
`backend/tests/fixtures/gomod/cmd/tool/main.go`:
```go
package main

func main() {}
```
`backend/tests/fixtures/gomod/examples/demo/demo.go`:
```go
package demo

// Hello is excluded from coverage by the default exclude patterns.
func Hello() string { return "hi" }
```
`backend/tests/fixtures/broken/go.mod`:
```
module example.com/broken

go 1.17
```
`backend/tests/fixtures/broken/broken.go`:
```go
package broken

func Broken() int {
	return "not an int"
}
```

- [ ] **Step 6: Write the backend Dockerfile** — `backend/Dockerfile` (build context is the repo root)

First run `uv --version` locally and put that exact version in the `pip install uv==` line. Then set the `GO_IMAGE` default to `golang:` + the contents of `.go-version`.

```dockerfile
# AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
ARG GO_IMAGE=golang:1.27-bookworm
FROM ${GO_IMAGE} AS go
WORKDIR /src
COPY tools/gohelper/ ./
RUN CGO_ENABLED=0 go build -o /out/gohelper .

FROM python:3.12-slim-bookworm
RUN apt-get update \
 && apt-get install -y --no-install-recommends git ca-certificates \
 && rm -rf /var/lib/apt/lists/*
COPY --from=go /usr/local/go /usr/local/go
COPY --from=go /out/gohelper /usr/local/bin/gohelper
ENV PATH=/usr/local/go/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy
RUN pip install --no-cache-dir uv==0.8.0
RUN useradd --create-home --uid 1000 app \
 && mkdir -p /work /output /repos /home/app/.cache/go-build /home/app/.cache/go-mod /opt/venv \
 && chown -R app:app /work /output /repos /home/app/.cache /opt/venv
WORKDIR /app
COPY --chown=app:app backend/pyproject.toml backend/uv.lock ./
USER app
RUN uv sync --frozen --no-install-project
COPY --chown=app:app backend/ ./
EXPOSE 8000
CMD ["uv", "run", "--no-sync", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 7: Write the integration tests**

`backend/tests/integration/conftest.py`:
```python
from pathlib import Path

import pytest

from app.config import Settings
from app.gotools import GoTools
from app.workspace import Workspace

FIXTURES = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def settings() -> Settings:
    return Settings()


@pytest.fixture
def make_ws(tmp_path):
    def _make(name: str = "gomod") -> Workspace:
        return Workspace.create(tmp_path / "work", "job", FIXTURES / name)
    return _make


@pytest.fixture
def tools_for(settings):
    def _tools(ws: Workspace) -> GoTools:
        return GoTools(ws.root, settings)
    return _tools
```

`backend/tests/integration/test_gotools.py`:
```python
import asyncio
import os
import time

import pytest

from app.coverage import parse_profile, summarize
from app.gotools import read_module_info, run

pytestmark = pytest.mark.integration


async def test_list_packages_excludes_main_and_examples(make_ws, tools_for):
    ws = make_ws()
    pkgs = await tools_for(ws).list_packages(["examples/**", "testdata/**"])
    assert [(p.rel_dir, p.name) for p in pkgs] == [(".", "calc")]


async def test_funcs_and_seeded_baseline_is_zero_with_full_denominator(make_ws, tools_for):
    ws = make_ws()
    tools = tools_for(ws)
    pkgs = await tools.list_packages(["examples/**"])
    ws.seed_packages([(p.rel_dir, p.name) for p in pkgs])
    profile = ws.scratch / "cover.out"
    r = await tools.test(pkgs, profile)
    assert r.exit_code == 0, r.combined
    module, _ = read_module_info(ws.root)
    report = summarize(parse_profile(profile.read_text(), module), await tools.funcs())
    assert report.total_statements > 0
    assert report.percent == 0.0
    assert {f.key.label() for f in report.functions} == {"Abs", "Sqrt"}


async def test_decls_merge_prune_roundtrip(make_ws, tools_for):
    ws = make_ws()
    tools = tools_for(ws)
    snippet = ws.scratch / "snippet.go"
    snippet.write_text('package calc\n\nimport "testing"\n\nfunc TestAbs(t *testing.T) {\n\tif Abs(-2) != 2 {\n\t\tt.Fatal("bad")\n\t}\n}\n')
    assert (await tools.merge("calc_test.go", snippet)).exit_code == 0
    assert await tools.decls(".") == ["TestAbs"]
    assert (await tools.prune("calc_test.go", ["TestAbs"])).exit_code == 0
    assert await tools.decls(".") == []


async def test_run_timeout_kills_whole_process_group(tmp_path):
    started = time.monotonic()
    r = await run(["sh", "-c", "sleep 30 & sleep 30"], cwd=tmp_path, timeout=1,
                  env={"PATH": os.environ["PATH"]})
    assert r.timed_out and r.exit_code == -1
    assert time.monotonic() - started < 5, "background child kept the pipes open"


async def test_run_cancel_event_stops_command(tmp_path):
    cancel = asyncio.Event()
    asyncio.get_running_loop().call_later(0.5, cancel.set)
    r = await run(["sleep", "30"], cwd=tmp_path, timeout=20, env={"PATH": os.environ["PATH"]}, cancel=cancel)
    assert r.cancelled and not r.timed_out
```

- [ ] **Step 8: Build the image and run the integration tests**

Run: `make test-integration` (or `docker build -f backend/Dockerfile -t gca-backend . && docker run --rm gca-backend uv run --no-sync pytest -m integration`)
Expected: 5 passed. If `test_funcs_and_seeded_baseline...` fails because the profile is empty, stop and investigate. The spec's denominator guarantee depends on this test.

- [ ] **Step 9: Commit**

```bash
git add backend/app/gotools.py backend/Dockerfile backend/tests
git commit -m "feat(backend): sandboxed command runner, GoTools and backend image"
```

---

### Task 7: Snippet guard and Validator

**Files:**
- Create: `backend/app/guard.py`, `backend/app/validator.py`
- Test: `backend/tests/test_guard.py`, `backend/tests/test_validator.py`, `backend/tests/integration/test_validator_integration.py`

**Interfaces:**
- Consumes: `Workspace` (Task 5); `GoTools`, `GoPackage`, `CommandResult` (Task 6); `parse_profile`, `summarize` (Task 4); `TestSnippet`, `CoverageReport`, `FuncInfo` (Task 1).
- Produces:
  - `check_snippet(snippet: TestSnippet, module: str, max_bytes: int = 40_000) -> list[str]`, `render_snippet(package: str, snippet: TestSnippet) -> str`, `test_names(code: str) -> list[str]`
  - `ValidationKind` (StrEnum: `accepted`, `compile_error`, `vet_error`, `test_failure`, `no_gain`, `guard_rejected`, `llm_error`)
  - `ValidationResult` (dataclass: `kind`, `output`, `failed_tests`, `report`, `new_tests`; property `accepted`; method `event() -> dict`)
  - `Measurement(result: CommandResult, report: CoverageReport | None)`
  - `parse_failed_tests(output: str) -> list[str]`
  - `class Validator(ws, tools, packages: list[GoPackage], funcs: list[FuncInfo], module: str)` with async methods:
    - `measure() -> Measurement`
    - `validate(test_file: str, package: str, snippet: TestSnippet, prev: CoverageReport) -> ValidationResult`
    - `prune_and_check(test_file: str, names: list[str], prev: CoverageReport, new_tests: list[str]) -> ValidationResult`
    - `check(prev: CoverageReport, new_tests: list[str]) -> ValidationResult`

- [ ] **Step 1: Write the guard tests** — `backend/tests/test_guard.py`

```python
from app.guard import check_snippet, render_snippet, test_names
from app.models import TestSnippet

MOD = "github.com/montanaflynn/stats"


def snip(code="func TestX(t *testing.T) {}", imports=("testing",)) -> TestSnippet:
    return TestSnippet(test_plan=[], imports=list(imports), code=code, suspected_bugs=[])


def test_clean_snippet_passes():
    assert check_snippet(snip(), MOD) == []


def test_denied_and_third_party_imports():
    problems = check_snippet(snip(imports=["testing", "os/exec", "net/http", "github.com/stretchr/testify/assert"]), MOD)
    assert any("os/exec" in p for p in problems)
    assert any("net/http" in p for p in problems)
    assert any("testify" in p for p in problems)


def test_module_own_packages_allowed():
    assert check_snippet(snip(imports=["testing", MOD + "/sub"]), MOD) == []


def test_code_must_not_contain_package_or_imports_or_build_tags():
    assert check_snippet(snip(code="package stats\nfunc TestX(t *testing.T) {}"), MOD)
    assert check_snippet(snip(code='import "os"\nfunc TestX(t *testing.T) {}'), MOD)
    assert check_snippet(snip(code="//go:build ignore\nfunc TestX(t *testing.T) {}"), MOD)


def test_requires_a_test_function_and_size_cap():
    assert check_snippet(snip(code="func helper() {}"), MOD)
    assert check_snippet(snip(code="func TestX(t *testing.T) {}\n" + "//" + "x" * 50_000), MOD)


def test_render_and_names():
    s = snip(code="func TestA(t *testing.T) {}\n\nfunc TestB(t *testing.T) {}", imports=["testing", "testing"])
    assert render_snippet("stats", s) == 'package stats\n\nimport (\n\t"testing"\n)\n\nfunc TestA(t *testing.T) {}\n\nfunc TestB(t *testing.T) {}\n'
    assert test_names(s.code) == ["TestA", "TestB"]
```

- [ ] **Step 2: Run them to verify they fail**, then implement `backend/app/guard.py`

Run: `uv run pytest tests/test_guard.py -q` → Expected: FAIL, `ModuleNotFoundError`.

```python
# AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
"""Static checks on LLM-written test code before anything is compiled or executed."""
from __future__ import annotations

import re

from app.models import TestSnippet

DENIED_IMPORTS = {"os/exec", "net", "syscall", "unsafe", "plugin", "runtime/debug"}
_TEST_FUNC = re.compile(r"^func (Test\w+)\(", re.M)


def _is_stdlib(path: str) -> bool:
    return "." not in path.split("/")[0]


def check_snippet(snippet: TestSnippet, module: str, max_bytes: int = 40_000) -> list[str]:
    problems: list[str] = []
    for imp in snippet.imports:
        if imp in DENIED_IMPORTS or imp.startswith("net/"):
            problems.append(f"import {imp!r} is not allowed in generated tests")
        elif not _is_stdlib(imp) and imp != module and not imp.startswith(module + "/"):
            problems.append(f"import {imp!r} is not in the standard library or this module")
    code = snippet.code
    if re.search(r"^\s*(package|import)\b", code, re.M):
        problems.append("`code` must not contain a package clause or import declarations; list import paths in `imports`")
    if re.search(r"^\s*//\s*(go:build|\+build)", code, re.M):
        problems.append("build constraints are not allowed")
    if len(code.encode()) > max_bytes:
        problems.append(f"code is larger than {max_bytes} bytes")
    if not _TEST_FUNC.search(code):
        problems.append("no `func TestXxx(t *testing.T)` found")
    return problems


def render_snippet(package: str, snippet: TestSnippet) -> str:
    imports = sorted(set(snippet.imports))
    block = "import (\n" + "".join(f'\t"{p}"\n' for p in imports) + ")\n\n" if imports else ""
    return f"package {package}\n\n{block}{snippet.code.strip()}\n"


def test_names(code: str) -> list[str]:
    return _TEST_FUNC.findall(code)


test_names.__test__ = False  # not a pytest test
```

Run: `uv run pytest tests/test_guard.py -q` → Expected: 6 passed.

- [ ] **Step 3: Write the validator unit tests (fake tools)** — `backend/tests/test_validator.py`

```python
from pathlib import Path

from app.gotools import CommandResult, GoPackage
from app.models import CoverageReport, FuncInfo, FuncKey, TestSnippet
from app.validator import ValidationKind, Validator, parse_failed_tests
from app.workspace import Workspace

MOD = "example.com/m"
PKG = [GoPackage(import_path=MOD, rel_dir=".", name="m")]
FUNCS = [FuncInfo(key=FuncKey(file="a.go", name="F"), package="m", start_line=1, end_line=20, exported=True)]


def ok(out: str = "") -> CommandResult:
    return CommandResult(argv=[], exit_code=0, stdout=out, stderr="", duration_ms=1)


def fail(out: str) -> CommandResult:
    return CommandResult(argv=[], exit_code=1, stdout=out, stderr="", duration_ms=1)


class FakeTools:
    def __init__(self, compile_r=None, vet_r=None, test_r=None, profile="mode: set\n", merge_r=None):
        self.compile_r, self.vet_r, self.test_r = compile_r or ok(), vet_r or ok(), test_r or ok()
        self.merge_r, self.profile = merge_r or ok(), profile
        self.pruned: list[str] = []

    async def merge(self, test_file, snippet): return self.merge_r
    async def prune(self, test_file, names): self.pruned = names; return ok()
    async def compile(self, pkgs): return self.compile_r
    async def vet(self, pkgs): return self.vet_r

    async def test(self, pkgs, profile: Path):
        profile.write_text(self.profile)
        return self.test_r


def make(tmp_path, tools) -> Validator:
    (tmp_path / "repo").mkdir(parents=True)
    (tmp_path / "scratch").mkdir(parents=True)
    return Validator(Workspace(tmp_path / "repo", tmp_path / "scratch"), tools, PKG, FUNCS, MOD)


def prev(ids=()) -> CoverageReport:
    return CoverageReport(total_statements=4, covered_statements=len(ids), percent=0, files=[], functions=[],
                          covered_block_ids=list(ids))


SNIP = TestSnippet(test_plan=[], imports=["testing"], code="func TestA(t *testing.T) {}\nfunc TestB(t *testing.T) {}", suspected_bugs=[])


def test_parse_failed_tests_top_level_unique():
    out = "--- FAIL: TestA (0.00s)\n    --- FAIL: TestA/neg (0.00s)\n--- FAIL: TestB (0.00s)\n--- FAIL: TestA (0.00s)\n"
    assert parse_failed_tests(out) == ["TestA", "TestB"]


async def test_guard_rejection_short_circuits(tmp_path):
    bad = SNIP.model_copy(update={"imports": ["os/exec"]})
    r = await make(tmp_path, FakeTools()).validate("a_test.go", "m", bad, prev())
    assert r.kind is ValidationKind.GUARD_REJECTED


async def test_merge_failure_is_compile_error(tmp_path):
    r = await make(tmp_path, FakeTools(merge_r=fail("duplicate declaration: TestA"))).validate("a_test.go", "m", SNIP, prev())
    assert r.kind is ValidationKind.COMPILE_ERROR and "duplicate" in r.output


async def test_compile_then_vet_classification(tmp_path):
    r = await make(tmp_path, FakeTools(compile_r=fail("undefined: Foo"))).validate("a_test.go", "m", SNIP, prev())
    assert r.kind is ValidationKind.COMPILE_ERROR
    r = await make(tmp_path / "2", FakeTools(vet_r=fail("printf: bad verb"))).validate("a_test.go", "m", SNIP, prev())
    assert r.kind is ValidationKind.VET_ERROR


async def test_test_failure_lists_failed_tests(tmp_path):
    tools = FakeTools(test_r=fail("--- FAIL: TestB (0.00s)\nFAIL"))
    r = await make(tmp_path, tools).validate("a_test.go", "m", SNIP, prev())
    assert r.kind is ValidationKind.TEST_FAILURE
    assert r.failed_tests == ["TestB"] and r.new_tests == ["TestA", "TestB"]


async def test_no_gain_when_nothing_new_or_regression(tmp_path):
    profile = "mode: set\nexample.com/m/a.go:1.1,2.2 1 1\n"
    r = await make(tmp_path, FakeTools(profile=profile)).validate("a_test.go", "m", SNIP, prev(["a.go:1.1,2.2"]))
    assert r.kind is ValidationKind.NO_GAIN
    r = await make(tmp_path / "2", FakeTools(profile=profile)).validate("a_test.go", "m", SNIP, prev(["a.go:5.1,6.2"]))
    assert r.kind is ValidationKind.NO_GAIN  # lost a previously covered block


async def test_accepted_returns_new_report(tmp_path):
    profile = "mode: set\nexample.com/m/a.go:1.1,2.2 1 1\nexample.com/m/a.go:3.1,4.2 1 0\n"
    r = await make(tmp_path, FakeTools(profile=profile)).validate("a_test.go", "m", SNIP, prev())
    assert r.accepted and r.report.percent == 50.0


async def test_prune_and_check_drops_failed_names(tmp_path):
    profile = "mode: set\nexample.com/m/a.go:1.1,2.2 1 1\n"
    tools = FakeTools(profile=profile)
    r = await make(tmp_path, tools).prune_and_check("a_test.go", ["TestB"], prev(), ["TestA", "TestB"])
    assert tools.pruned == ["TestB"] and r.accepted and r.new_tests == ["TestA"]
```

- [ ] **Step 4: Run them to verify they fail**, then implement `backend/app/validator.py`

Run: `uv run pytest tests/test_validator.py -q` → Expected: FAIL, `ModuleNotFoundError`.

```python
# AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
"""Decides whether a candidate test snippet is kept: guard → merge → compile → vet → test → coverage."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.coverage import parse_profile, summarize
from app.gotools import CommandResult, GoPackage
from app.guard import check_snippet, render_snippet, test_names
from app.models import CoverageReport, FuncInfo, TestSnippet
from app.workspace import Workspace

_FAIL = re.compile(r"^\s*--- FAIL: (\S+)", re.M)


class ValidationKind(StrEnum):
    ACCEPTED = "accepted"
    COMPILE_ERROR = "compile_error"
    VET_ERROR = "vet_error"
    TEST_FAILURE = "test_failure"
    NO_GAIN = "no_gain"
    GUARD_REJECTED = "guard_rejected"
    LLM_ERROR = "llm_error"


@dataclass
class ValidationResult:
    kind: ValidationKind
    output: str = ""
    failed_tests: list[str] = field(default_factory=list)
    report: CoverageReport | None = None
    new_tests: list[str] = field(default_factory=list)

    @property
    def accepted(self) -> bool:
        return self.kind is ValidationKind.ACCEPTED

    def event(self) -> dict[str, Any]:
        return {"kind": self.kind.value, "output": self.output[:4000], "failed_tests": self.failed_tests}


@dataclass
class Measurement:
    result: CommandResult
    report: CoverageReport | None


def parse_failed_tests(output: str) -> list[str]:
    names: list[str] = []
    for m in _FAIL.finditer(output):
        top = m.group(1).split("/")[0]
        if top not in names:
            names.append(top)
    return names


class Validator:
    def __init__(self, ws: Workspace, tools: Any, packages: list[GoPackage], funcs: list[FuncInfo], module: str):
        self.ws, self.tools, self.packages, self.funcs, self.module = ws, tools, packages, funcs, module

    async def measure(self) -> Measurement:
        profile = self.ws.scratch / "cover.out"
        profile.unlink(missing_ok=True)
        r = await self.tools.test(self.packages, profile)
        if r.exit_code != 0 or r.timed_out or not profile.exists():
            return Measurement(r, None)
        return Measurement(r, summarize(parse_profile(profile.read_text(), self.module), self.funcs))

    async def validate(self, test_file: str, package: str, snippet: TestSnippet,
                       prev: CoverageReport) -> ValidationResult:
        new_tests = test_names(snippet.code)
        problems = check_snippet(snippet, self.module)
        if problems:
            return ValidationResult(ValidationKind.GUARD_REJECTED, "\n".join(problems), new_tests=new_tests)
        snippet_path = self.ws.scratch / "snippet.go"
        snippet_path.write_text(render_snippet(package, snippet))
        r = await self.tools.merge(test_file, snippet_path)
        if r.exit_code != 0:
            return ValidationResult(ValidationKind.COMPILE_ERROR, r.combined, new_tests=new_tests)
        return await self.check(prev, new_tests)

    async def prune_and_check(self, test_file: str, names: list[str], prev: CoverageReport,
                              new_tests: list[str]) -> ValidationResult:
        r = await self.tools.prune(test_file, names)
        if r.exit_code != 0:
            return ValidationResult(ValidationKind.COMPILE_ERROR, r.combined, new_tests=new_tests)
        return await self.check(prev, [n for n in new_tests if n not in names])

    async def check(self, prev: CoverageReport, new_tests: list[str]) -> ValidationResult:
        r = await self.tools.compile(self.packages)
        if r.exit_code != 0:
            return ValidationResult(ValidationKind.COMPILE_ERROR, r.combined, new_tests=new_tests)
        r = await self.tools.vet(self.packages)
        if r.exit_code != 0:
            return ValidationResult(ValidationKind.VET_ERROR, r.combined, new_tests=new_tests)
        m = await self.measure()
        if m.report is None:
            output = "tests timed out (60s)\n" + m.result.combined if m.result.timed_out else m.result.combined
            failed = parse_failed_tests(m.result.combined) or list(new_tests)
            return ValidationResult(ValidationKind.TEST_FAILURE, output, failed_tests=failed, new_tests=new_tests)
        before, after = prev.covered_set(), m.report.covered_set()
        if not before <= after or after == before:
            return ValidationResult(ValidationKind.NO_GAIN, "the new tests executed no previously uncovered statements",
                                    report=m.report, new_tests=new_tests)
        return ValidationResult(ValidationKind.ACCEPTED, report=m.report, new_tests=new_tests)
```

Run: `uv run pytest tests/test_validator.py -q` → Expected: 8 passed.

- [ ] **Step 5: Write the integration test against real Go** — `backend/tests/integration/test_validator_integration.py`

```python
import pytest

from app.gotools import read_module_info
from app.models import TestSnippet
from app.validator import ValidationKind, Validator

pytestmark = pytest.mark.integration

GOOD = 'func TestAbs(t *testing.T) {\n\tif Abs(-3) != 3 || Abs(2) != 2 {\n\t\tt.Fatal("abs")\n\t}\n}'
WRONG = 'func TestSqrtWrong(t *testing.T) {\n\tif r, _ := Sqrt(9); r != 4 {\n\t\tt.Fatalf("got %d", r)\n\t}\n}'
BROKEN = 'func TestBroken(t *testing.T) {\n\tvar x int = "s"\n\t_ = x\n}'


def snip(code: str) -> TestSnippet:
    return TestSnippet(test_plan=[], imports=["testing"], code=code, suspected_bugs=[])


async def setup(make_ws, tools_for):
    ws = make_ws()
    tools = tools_for(ws)
    pkgs = await tools.list_packages(["examples/**"])
    ws.seed_packages([(p.rel_dir, p.name) for p in pkgs])
    module, _ = read_module_info(ws.root)
    v = Validator(ws, tools, pkgs, await tools.funcs(), module)
    baseline = (await v.measure()).report
    assert baseline is not None and baseline.percent == 0.0
    return ws, v, baseline


async def test_accepts_good_tests(make_ws, tools_for):
    _, v, baseline = await setup(make_ws, tools_for)
    r = await v.validate("calc_test.go", "calc", snip(GOOD), baseline)
    assert r.accepted, r.output
    assert r.report.percent > 0


async def test_compile_error_is_classified(make_ws, tools_for):
    _, v, baseline = await setup(make_ws, tools_for)
    r = await v.validate("calc_test.go", "calc", snip(BROKEN), baseline)
    assert r.kind is ValidationKind.COMPILE_ERROR


async def test_failure_then_prune_keeps_good_test(make_ws, tools_for):
    _, v, baseline = await setup(make_ws, tools_for)
    r = await v.validate("calc_test.go", "calc", snip(GOOD + "\n\n" + WRONG), baseline)
    assert r.kind is ValidationKind.TEST_FAILURE and r.failed_tests == ["TestSqrtWrong"]
    r = await v.prune_and_check("calc_test.go", r.failed_tests, baseline, r.new_tests)
    assert r.accepted and r.new_tests == ["TestAbs"]


async def test_duplicate_coverage_is_no_gain(make_ws, tools_for):
    _, v, baseline = await setup(make_ws, tools_for)
    first = await v.validate("calc_test.go", "calc", snip(GOOD), baseline)
    again = snip(GOOD.replace("TestAbs", "TestAbsAgain"))
    r = await v.validate("calc_test.go", "calc", again, first.report)
    assert r.kind is ValidationKind.NO_GAIN
```

Run: `make test-integration` → Expected: all integration tests pass (9).

- [ ] **Step 6: Commit**

```bash
git add backend/app/guard.py backend/app/validator.py backend/tests
git commit -m "feat(backend): snippet guard and validator"
```

---

### Task 8: Strict schema normalizer, rate limiter, daily usage ledger

**Files:**
- Create: `backend/app/llm/schema.py`, `backend/app/llm/limits.py`
- Test: `backend/tests/test_llm_schema.py`, `backend/tests/test_llm_limits.py`

**Interfaces:**
- Produces:
  - `to_strict_schema(model: type[BaseModel]) -> dict`
  - `parse_duration(text: str) -> float` (seconds)
  - `RateLimiter(clock=time.monotonic)` with `.update(headers: Mapping[str, str])`, `.wait_needed(tokens: int) -> float`, `.reset()`
  - `UsageLedger(path: Path, daily_budget: int, today: Callable[[], str] | None = None)` with `.used_today() -> int`, `.remaining() -> int`, `.add(tokens: int)`

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_llm_schema.py`:
```python
from pydantic import BaseModel, Field

from app.llm.schema import to_strict_schema
from app.models import TestSnippet


def walk(node):
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from walk(v)


def test_every_object_is_strict():
    schema = to_strict_schema(TestSnippet)
    objects = [n for n in walk(schema) if n.get("type") == "object"]
    assert objects, "expected object nodes"
    for obj in objects:
        assert obj["additionalProperties"] is False
        assert sorted(obj["required"]) == sorted(obj["properties"])


def test_unsupported_keywords_removed_but_property_names_kept():
    class M(BaseModel):
        title: str = Field(default="x", min_length=1, title="Title")
        description: list[str] = Field(default_factory=list, max_length=3)

    schema = to_strict_schema(M)
    assert set(schema["properties"]) == {"title", "description"}
    flat = list(walk(schema))
    for banned in ("default", "minLength", "maxItems", "title"):
        assert not any(banned in n and n is not schema["properties"] for n in flat), banned
```

`backend/tests/test_llm_limits.py`:
```python
import json

import pytest

from app.llm.limits import RateLimiter, UsageLedger, parse_duration


@pytest.mark.parametrize("text,seconds", [("7.66s", 7.66), ("2m59.56s", 179.56), ("120ms", 0.12), ("1h2m3s", 3723.0), ("", 0.0)])
def test_parse_duration(text, seconds):
    assert parse_duration(text) == pytest.approx(seconds)


def test_rate_limiter_waits_until_reset_when_low():
    now = [100.0]
    rl = RateLimiter(clock=lambda: now[0])
    assert rl.wait_needed(7000) == 0.0  # nothing known yet
    rl.update({"x-ratelimit-remaining-tokens": "3000", "x-ratelimit-reset-tokens": "40s"})
    assert rl.wait_needed(2000) == 0.0
    assert rl.wait_needed(7000) == pytest.approx(40.0)
    now[0] = 150.0
    assert rl.wait_needed(7000) == 0.0  # reset passed


def test_ledger_tracks_per_day_and_survives_corruption(tmp_path):
    day = ["2026-10-08"]
    path = tmp_path / ".usage.json"
    ledger = UsageLedger(path, daily_budget=1000, today=lambda: day[0])
    ledger.add(300)
    assert ledger.remaining() == 700
    assert UsageLedger(path, 1000, today=lambda: day[0]).used_today() == 300
    day[0] = "2026-10-09"
    assert ledger.remaining() == 1000
    path.write_text("{not json")
    assert UsageLedger(path, 1000, today=lambda: day[0]).used_today() == 0
    ledger.add(10)
    assert json.loads(path.read_text())["2026-10-09"] == 10
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_llm_schema.py tests/test_llm_limits.py -q` → Expected: FAIL, `ModuleNotFoundError`.

- [ ] **Step 3: Implement `backend/app/llm/schema.py`**

```python
# AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
"""Convert a Pydantic JSON Schema into the subset Groq strict mode accepts."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel

_UNSUPPORTED = {"title", "default", "minLength", "maxLength", "minItems", "maxItems",
                "pattern", "format", "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum"}


def _walk(node: Any) -> Any:
    if isinstance(node, list):
        return [_walk(v) for v in node]
    if not isinstance(node, dict):
        return node
    out: dict[str, Any] = {}
    for key, value in node.items():
        if key in _UNSUPPORTED:
            continue
        if key in ("properties", "$defs"):
            out[key] = {name: _walk(sub) for name, sub in value.items()}  # keep names, clean bodies
        else:
            out[key] = _walk(value)
    if out.get("type") == "object" and "properties" in out:
        out["required"] = list(out["properties"])
        out["additionalProperties"] = False
    return out


def to_strict_schema(model: type[BaseModel]) -> dict[str, Any]:
    return _walk(model.model_json_schema())
```

- [ ] **Step 4: Implement `backend/app/llm/limits.py`**

```python
# AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
"""Client-side pacing for Groq's tokens-per-minute limit and a local tokens-per-day ledger."""
from __future__ import annotations

import json
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, Mapping

_DUR = re.compile(r"(?P<v>\d+(?:\.\d+)?)(?P<u>ms|h|m|s)")
_UNIT = {"ms": 0.001, "s": 1.0, "m": 60.0, "h": 3600.0}


def parse_duration(text: str) -> float:
    return sum(float(m["v"]) * _UNIT[m["u"]] for m in _DUR.finditer(text or ""))


class RateLimiter:
    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self._clock = clock
        self._remaining: int | None = None
        self._reset_at = 0.0

    def update(self, headers: Mapping[str, str]) -> None:
        remaining = headers.get("x-ratelimit-remaining-tokens")
        if remaining is None:
            return
        try:
            self._remaining = int(float(remaining))
        except ValueError:
            return
        reset = headers.get("x-ratelimit-reset-tokens")
        self._reset_at = self._clock() + (parse_duration(reset) if reset else 60.0)

    def wait_needed(self, tokens: int) -> float:
        if self._remaining is None or self._remaining >= tokens:
            return 0.0
        wait = self._reset_at - self._clock()
        if wait <= 0:
            self.reset()
            return 0.0
        return wait

    def reset(self) -> None:
        self._remaining = None


class UsageLedger:
    def __init__(self, path: Path, daily_budget: int, today: Callable[[], str] | None = None):
        self.path = path
        self.daily_budget = daily_budget
        self._today = today or (lambda: datetime.now(UTC).date().isoformat())

    def _load(self) -> dict[str, int]:
        try:
            data = json.loads(self.path.read_text())
            return {k: int(v) for k, v in data.items()} if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def used_today(self) -> int:
        return self._load().get(self._today(), 0)

    def remaining(self) -> int:
        return max(0, self.daily_budget - self.used_today())

    def add(self, tokens: int) -> None:
        day = self._today()
        data = {day: self._load().get(day, 0) + tokens}  # keep only today; old days are irrelevant
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data))
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_llm_schema.py tests/test_llm_limits.py -q` → Expected: 9 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/app/llm backend/tests/test_llm_schema.py backend/tests/test_llm_limits.py
git commit -m "feat(llm): strict schema normalizer, rate limiter and usage ledger"
```

---

### Task 9: Groq LLM client

**Files:**
- Create: `backend/app/llm/client.py`
- Test: `backend/tests/test_llm_client.py`

**Interfaces:**
- Consumes: `Settings`, `TokenUsage`, `to_strict_schema`, `RateLimiter`, `UsageLedger`.
- Produces:
  - `estimate_tokens(text: str) -> int`
  - Exceptions: `LLMError(Exception)`, `LLMBudgetExhausted(LLMError)` (graceful stop), `LLMFatal(LLMError)` (job failure, e.g. bad key), `LLMCancelled(LLMError)` (user cancelled mid-wait or mid-request)
  - `Emit = Callable[[str, dict], Awaitable[None]]`
  - `LLMClient` Protocol: `async complete(*, role: str, system: str, user: str, schema: type[T]) -> tuple[T, TokenUsage]`
  - `GroqLLM(settings, ledger, limiter, emit: Emit | None = None, client=None, sleep=asyncio.sleep, cancel: asyncio.Event | None = None)`, which implements `LLMClient`

- [ ] **Step 1: Write the failing tests** — `backend/tests/test_llm_client.py`

```python
import httpx
import groq
import pytest
from pydantic import BaseModel

from app.config import Settings
from app.llm.client import GroqLLM, LLMBudgetExhausted, LLMError, LLMFatal
from app.llm.limits import RateLimiter, UsageLedger


class Out(BaseModel):
    answer: str


class Msg:
    def __init__(self, content): self.content = content


class Choice:
    def __init__(self, content, finish): self.message, self.finish_reason = Msg(content), finish


class Usage:
    prompt_tokens, completion_tokens = 100, 50


class Completion:
    def __init__(self, content, finish): self.choices, self.usage = [Choice(content, finish)], Usage()


class Raw:
    def __init__(self, completion, headers=None): self._c, self.headers = completion, headers or {}
    def parse(self): return self._c


def http_error(cls, status, headers=None):
    req = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    return cls("err", response=httpx.Response(status, headers=headers or {}, request=req), body=None)


class FakeGroq:
    """Mimics client.chat.completions.with_raw_response.create(...)."""

    def __init__(self, script):
        self.script, self.calls = list(script), []
        self.chat = self
        self.completions = self
        self.with_raw_response = self

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def make(tmp_path, script, events=None):
    slept = []
    async def sleep(s): slept.append(s)
    async def emit(t, d): (events if events is not None else []).append((t, d))
    fake = FakeGroq(script)
    llm = GroqLLM(Settings(groq_api_key="k"), UsageLedger(tmp_path / "u.json", 190_000), RateLimiter(),
                  emit=emit, client=fake, sleep=sleep)
    return llm, fake, slept


async def call(llm):
    return await llm.complete(role="writer", system="sys", user="usr", schema=Out)


async def test_success_parses_and_counts_usage(tmp_path):
    llm, fake, _ = make(tmp_path, [Raw(Completion('{"answer": "hi"}', "stop"))])
    out, usage = await call(llm)
    assert out.answer == "hi" and usage.total == 150
    kw = fake.calls[0]
    assert kw["response_format"]["json_schema"]["strict"] is True
    assert kw["reasoning_effort"] == "low"
    assert kw["max_completion_tokens"] == 7000 - 2  # "sys"+"usr" ≈ 2 tokens
    assert llm.ledger.used_today() == 150


async def test_401_is_fatal(tmp_path):
    llm, _, _ = make(tmp_path, [http_error(groq.AuthenticationError, 401)])
    with pytest.raises(LLMFatal, match="API key"):
        await call(llm)


async def test_short_429_waits_and_retries(tmp_path):
    events = []
    llm, _, slept = make(tmp_path, [http_error(groq.RateLimitError, 429, {"retry-after": "12"}),
                                    Raw(Completion('{"answer": "ok"}', "stop"))], events)
    out, _ = await call(llm)
    assert out.answer == "ok" and slept == [12.0]
    assert ("rate_limited", {"seconds": 12.0, "reason": "429"}) in events


async def test_long_429_means_daily_cap(tmp_path):
    llm, _, _ = make(tmp_path, [http_error(groq.RateLimitError, 429, {"retry-after": "3600"})])
    with pytest.raises(LLMBudgetExhausted):
        await call(llm)


async def test_truncation_at_low_effort_fails_without_retry(tmp_path):
    llm, fake, _ = make(tmp_path, [Raw(Completion("{", "length"))])
    with pytest.raises(LLMError, match="truncated"):
        await call(llm)
    assert len(fake.calls) == 1


async def test_schema_mismatch_is_llm_error(tmp_path):
    llm, _, _ = make(tmp_path, [Raw(Completion('{"wrong": 1}', "stop"))])
    with pytest.raises(LLMError, match="does not match"):
        await call(llm)


async def test_daily_budget_checked_before_calling(tmp_path):
    llm, fake, _ = make(tmp_path, [])
    llm.ledger.add(190_000)
    with pytest.raises(LLMBudgetExhausted):
        await call(llm)
    assert fake.calls == []


async def test_cancel_interrupts_rate_limit_wait(tmp_path):
    import asyncio
    from app.llm.client import LLMCancelled
    cancel = asyncio.Event()
    fake = FakeGroq([http_error(groq.RateLimitError, 429, {"retry-after": "60"})])
    llm = GroqLLM(Settings(groq_api_key="k"), UsageLedger(tmp_path / "u.json", 190_000), RateLimiter(),
                  client=fake, cancel=cancel)
    asyncio.get_running_loop().call_later(0.05, cancel.set)
    with pytest.raises(LLMCancelled):
        await asyncio.wait_for(call(llm), timeout=2)  # must not sleep the full 60s


async def test_oversized_prompt_rejected(tmp_path):
    llm, _, _ = make(tmp_path, [])
    with pytest.raises(LLMError, match="prompt"):
        await llm.complete(role="writer", system="s", user="x" * 20_000, schema=Out)
```

> Note (Task 32): `GROQ_REASONING_EFFORT` was replaced by the per-role settings `GROQ_WRITER_REASONING_EFFORT` (default `medium`) and `GROQ_FIXER_REASONING_EFFORT` (default `high`); see the spec §5.1.

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_llm_client.py -q` → Expected: FAIL, `ModuleNotFoundError`.

- [ ] **Step 3: Implement `backend/app/llm/client.py`**

```python
# AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
"""Groq chat completions with strict structured output, pacing, budgets and clear failure modes."""
from __future__ import annotations

import asyncio
import math
from typing import Any, Awaitable, Callable, Protocol, TypeVar

import groq
from pydantic import BaseModel, ValidationError

from app.config import Settings
from app.llm.limits import RateLimiter, UsageLedger
from app.llm.schema import to_strict_schema
from app.models import TokenUsage

T = TypeVar("T", bound=BaseModel)
Emit = Callable[[str, dict[str, Any]], Awaitable[None]]


class LLMError(Exception):
    """The current item failed; the loop can continue."""


class LLMBudgetExhausted(LLMError):
    """No more tokens available (job budget, daily ledger, or Groq daily cap). Stop gracefully."""


class LLMFatal(LLMError):
    """Configuration problem (e.g. invalid key). Fail the job."""


class LLMCancelled(LLMError):
    """The job was cancelled while waiting on the LLM (e.g. during a rate-limit pause)."""


def estimate_tokens(text: str) -> int:
    return math.ceil(len(text) / 3.5)


class LLMClient(Protocol):
    async def complete(self, *, role: str, system: str, user: str, schema: type[T]) -> tuple[T, TokenUsage]: ...


class GroqLLM:
    MAX_RATE_RETRIES = 5
    MAX_NET_RETRIES = 3
    MAX_RETRY_AFTER_S = 90.0

    def __init__(self, settings: Settings, ledger: UsageLedger, limiter: RateLimiter,
                 emit: Emit | None = None, client: Any = None,
                 sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
                 cancel: asyncio.Event | None = None):
        self.s, self.ledger, self.limiter = settings, ledger, limiter
        self._emit, self._sleep, self._cancel = emit, sleep, cancel
        self._client = client or groq.AsyncGroq(api_key=settings.groq_api_key, max_retries=0, timeout=120.0)

    async def _wait(self, seconds: float, reason: str) -> None:
        if self._emit:
            await self._emit("rate_limited", {"seconds": round(seconds, 1), "reason": reason})
        if self._cancel is None:
            await self._sleep(seconds)
            return
        try:  # wake up immediately if the user cancels during a long rate-limit pause
            await asyncio.wait_for(self._cancel.wait(), timeout=seconds)
        except asyncio.TimeoutError:
            return
        raise LLMCancelled("cancelled while waiting for the rate limit")

    async def _request(self, **kwargs: Any) -> Any:
        call = asyncio.ensure_future(self._client.chat.completions.with_raw_response.create(**kwargs))
        if self._cancel is None:
            return await call
        stop = asyncio.ensure_future(self._cancel.wait())
        done, _ = await asyncio.wait({call, stop}, return_when=asyncio.FIRST_COMPLETED)
        if call in done:
            stop.cancel()
            return call.result()
        call.cancel()
        raise LLMCancelled("cancelled during an LLM request")

    async def complete(self, *, role: str, system: str, user: str, schema: type[T]) -> tuple[T, TokenUsage]:
        prompt_tokens = estimate_tokens(system) + estimate_tokens(user)
        if prompt_tokens > self.s.max_prompt_tokens:
            raise LLMError(f"prompt is ~{prompt_tokens} tokens, over the {self.s.max_prompt_tokens} limit")
        if self.ledger.remaining() < self.s.max_tokens_per_call:
            raise LLMBudgetExhausted("The daily Groq token budget is used up. It resets at 00:00 UTC.")

        effort = self.s.groq_reasoning_effort
        truncated = False
        rate_retries = net_retries = 0
        spent = TokenUsage()
        response_format = {"type": "json_schema", "json_schema": {
            "name": schema.__name__, "strict": True, "schema": to_strict_schema(schema)}}

        while True:
            wait = self.limiter.wait_needed(self.s.max_tokens_per_call)
            if wait > 0:
                await self._wait(wait, "tpm")
                self.limiter.reset()
            try:
                raw = await self._request(
                    model=self.s.groq_model,
                    messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                    response_format=response_format,
                    reasoning_effort=effort,
                    max_completion_tokens=self.s.max_tokens_per_call - prompt_tokens,
                    temperature=0.2,
                )
            except groq.AuthenticationError as e:
                raise LLMFatal("Groq rejected the API key (401). Check GROQ_API_KEY in .env.") from e
            except groq.RateLimitError as e:
                retry_after = float(e.response.headers.get("retry-after", "60"))
                if retry_after > self.MAX_RETRY_AFTER_S or rate_retries >= self.MAX_RATE_RETRIES:
                    raise LLMBudgetExhausted(
                        f"Groq asked us to wait {retry_after:.0f}s, which usually means the daily token cap was hit."
                    ) from e
                rate_retries += 1
                await self._wait(retry_after, "429")
                continue
            except (groq.APIConnectionError, groq.InternalServerError) as e:
                if net_retries >= self.MAX_NET_RETRIES:
                    raise LLMError(f"Groq is unreachable: {e}") from e
                net_retries += 1
                await self._sleep(2.0 ** net_retries)
                continue
            except groq.APIStatusError as e:
                raise LLMError(f"Groq returned {e.status_code}: {e.message}") from e

            self.limiter.update(raw.headers)
            completion = raw.parse()
            usage = TokenUsage(prompt_tokens=completion.usage.prompt_tokens,
                               completion_tokens=completion.usage.completion_tokens)
            spent = spent.add(usage)
            self.ledger.add(usage.total)
            choice = completion.choices[0]
            if choice.finish_reason == "length":
                # Retrying only helps if we can lower the reasoning effort; otherwise it re-spends the same tokens.
                if truncated or effort == "low":
                    raise LLMError("the model's answer was truncated; skipping this target")
                truncated, effort = True, "low"
                continue
            try:
                return schema.model_validate_json(choice.message.content or ""), spent
            except ValidationError as e:
                raise LLMError(f"model output does not match {schema.__name__} ({e.error_count()} errors)") from e
```

> Note (Task 32): `GROQ_REASONING_EFFORT` was replaced by the per-role settings `GROQ_WRITER_REASONING_EFFORT` (default `medium`) and `GROQ_FIXER_REASONING_EFFORT` (default `high`); see the spec §5.1.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_llm_client.py -q` → Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/llm/client.py backend/tests/test_llm_client.py
git commit -m "feat(llm): Groq client with structured output, pacing and failure modes"
```

---

### Task 10: Prompt context builder (+ `gohelper symbols`)

**Files:**
- Create: `tools/gohelper/symbols.go`, `tools/gohelper/symbols_test.go`
- Modify: `tools/gohelper/main.go` (add the `symbols` case and usage line)
- Modify: `backend/app/gotools.py` (add `Symbol` and `GoTools.symbols()`)
- Create: `backend/app/agents/context.py`
- Test: `backend/tests/test_context.py`

**Interfaces:**
- Consumes: `GoTools.decls`, `Workspace.read`, `test_path_for`, `estimate_tokens` (Task 9), `FuncInfo`, `PlanItem`, `CoverageReport`.
- Produces:
  - CLI `gohelper symbols <dir>` → JSON `[{"name","kind","file","start_line","end_line"}]` for top-level `type`/`var`/`const` in non-test files. A spec inside a `( … )` group spans only its own lines; an ungrouped declaration spans the whole declaration plus its doc comment.
  - Python `Symbol(name, kind, file, start_line, end_line)` (frozen dataclass in `app.gotools`) and `async GoTools.symbols() -> list[Symbol]`.
  - `ContextInputs` (dataclass with fields `module`, `package`, `go_version`, `source_file`, `test_file`, `targets: list[tuple[str, str]]`, `declared: list[str]`, `referenced: list[str]`, `existing_tests: list[str]`)
  - `class ContextTooLarge(Exception)`
  - Pure functions: `go_version_rules(version: str) -> list[str]`, `annotate_source(lines: list[str], start: int, end: int, uncovered: list[tuple[int, int]]) -> str`, `test_signatures(src: str | None) -> list[str]`, `render_context(inp: ContextInputs, budget_tokens: int) -> str`
  - `ContextProvider(ws, tools, funcs: list[FuncInfo], symbols: list[Symbol], module: str, go_version: str, packages: dict[str, GoPackage])` with `async inputs_for(item: PlanItem, report: CoverageReport) -> ContextInputs`

- [ ] **Step 1: Write the failing Go test** — `tools/gohelper/symbols_test.go`

```go
// AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
package main

import (
	"reflect"
	"testing"
)

func TestSymbols_TypesVarsConsts(t *testing.T) {
	dir := t.TempDir()
	writeFile(t, dir, "e.go", "package p\n\nimport \"errors\"\n\n// T is data.\ntype T []float64\n\nvar (\n\tErrA = errors.New(\"a\")\n\tErrB = errors.New(\"b\")\n)\n\nconst k = 1\n\nfunc F() {}\n")
	writeFile(t, dir, "e_test.go", "package p\n\nvar ignored = 1\n")

	got, err := Symbols(dir)
	if err != nil {
		t.Fatal(err)
	}
	want := []Symbol{
		{Name: "T", Kind: "type", File: "e.go", StartLine: 5, EndLine: 6},
		{Name: "ErrA", Kind: "var", File: "e.go", StartLine: 9, EndLine: 9},
		{Name: "ErrB", Kind: "var", File: "e.go", StartLine: 10, EndLine: 10},
		{Name: "k", Kind: "const", File: "e.go", StartLine: 13, EndLine: 13},
	}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("got  %+v\nwant %+v", got, want)
	}
}
```

Run: `go test ./...` → Expected: FAIL, `undefined: Symbols`.

- [ ] **Step 2: Implement `tools/gohelper/symbols.go`** and wire it into `main.go`

```go
// AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
package main

import (
	"fmt"
	"go/ast"
	"go/parser"
	"go/token"
	"io/fs"
	"path/filepath"
	"strings"
)

// Symbol locates a top-level type, var or const declaration.
type Symbol struct {
	Name      string `json:"name"`
	Kind      string `json:"kind"`
	File      string `json:"file"`
	StartLine int    `json:"start_line"`
	EndLine   int    `json:"end_line"`
}

// Symbols lists top-level type/var/const declarations in non-test files under root.
func Symbols(root string) ([]Symbol, error) {
	out := []Symbol{}
	fset := token.NewFileSet()
	err := filepath.WalkDir(root, func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if d.IsDir() {
			if skipDir(root, path, d.Name()) {
				return filepath.SkipDir
			}
			return nil
		}
		if !strings.HasSuffix(path, ".go") || strings.HasSuffix(path, "_test.go") {
			return nil
		}
		f, err := parser.ParseFile(fset, path, nil, parser.ParseComments|parser.SkipObjectResolution)
		if err != nil {
			return fmt.Errorf("parse %s: %w", path, err)
		}
		rel, err := filepath.Rel(root, path)
		if err != nil {
			return err
		}
		rel = filepath.ToSlash(rel)
		for _, decl := range f.Decls {
			gd, ok := decl.(*ast.GenDecl)
			if !ok || gd.Tok == token.IMPORT {
				continue
			}
			for _, spec := range gd.Specs {
				start, end := spec.Pos(), spec.End()
				if !gd.Lparen.IsValid() {
					start, end = gd.Pos(), gd.End()
					if gd.Doc != nil {
						start = gd.Doc.Pos()
					}
				}
				for _, name := range specNames(spec) {
					out = append(out, Symbol{Name: name, Kind: gd.Tok.String(), File: rel,
						StartLine: fset.Position(start).Line, EndLine: fset.Position(end).Line})
				}
			}
		}
		return nil
	})
	return out, err
}

func specNames(spec ast.Spec) []string {
	switch s := spec.(type) {
	case *ast.TypeSpec:
		return []string{s.Name.Name}
	case *ast.ValueSpec:
		var names []string
		for _, n := range s.Names {
			if n.Name != "_" {
				names = append(names, n.Name)
			}
		}
		return names
	}
	return nil
}
```

In `main.go`, add `gohelper symbols <dir>` to `usage` and this case to the switch:
```go
	case "symbols":
		out, err := Symbols(args[1])
		if err != nil {
			return err
		}
		return json.NewEncoder(stdout).Encode(out)
```

Run: `go test ./...` → Expected: `ok gohelper`.

- [ ] **Step 3: Add `Symbol` + `GoTools.symbols()` to `backend/app/gotools.py`**

```python
@dataclass(frozen=True)
class Symbol:
    name: str
    kind: str
    file: str
    start_line: int
    end_line: int
```
And inside `GoTools`:
```python
    async def symbols(self) -> list[Symbol]:
        r = await self._run(["gohelper", "symbols", "."])
        if r.exit_code != 0:
            raise GoToolError("gohelper symbols failed", r)
        return [Symbol(**o) for o in json.loads(r.stdout)]
```

- [ ] **Step 4: Write the failing context tests** — `backend/tests/test_context.py`

```python
import pytest

from app.agents.context import (ContextInputs, ContextProvider, ContextTooLarge, annotate_source,
                                go_version_rules, render_context, test_signatures)
from app.gotools import GoPackage, Symbol
from app.models import CoverageReport, FuncCoverage, FuncInfo, FuncKey, PlanItem
from app.workspace import Workspace


def test_go_version_rules_for_old_and_new_go():
    old = " ".join(go_version_rules("1.17"))
    assert "generics" in old and "slices" in old and "tc := tc" in old and "t.Parallel" in old
    new = " ".join(go_version_rules("1.22.1"))
    assert "generics" not in new and "slices" not in new and "tc := tc" not in new and "t.Parallel" in new


def test_annotate_source_marks_uncovered_and_keeps_doc_comment():
    lines = ["package p", "", "// Abs returns |x|.", "func Abs(x int) int {", "\tif x < 0 {", "\t\treturn -x", "\t}", "\treturn x", "}"]
    out = annotate_source(lines, 4, 9, [(5, 6)])
    assert out.splitlines()[0] == "// Abs returns |x|."
    assert "\t\treturn -x  // UNCOVERED" in out
    assert "\treturn x  // UNCOVERED" not in out


def test_test_signatures():
    src = "package p\n\nfunc TestA(t *testing.T) {\n}\n\nfunc helper() {}\n"
    assert test_signatures(src) == ["func TestA(t *testing.T)", "func helper()"]
    assert test_signatures(None) == []


def inputs(**over) -> ContextInputs:
    base = dict(module="m", package="p", go_version="1.17", source_file="a.go", test_file="a_test.go",
                targets=[("Abs", "func Abs() {}")], declared=["approxEqual"],
                referenced=["var ErrA = errors.New(\"a\")"] * 50, existing_tests=["func TestOld(t *testing.T)"])
    base.update(over)
    return ContextInputs(**base)


def test_render_context_includes_must_sections_and_trims_optional():
    full = render_context(inputs(referenced=["var ErrA = 1"]), 4000)
    for part in ("package p", "approxEqual", "func Abs() {}", "var ErrA = 1", "func TestOld"):
        assert part in full
    tight = render_context(inputs(), 400)
    assert "func Abs() {}" in tight and "approxEqual" in tight
    assert tight.count("ErrA") < 50


def test_render_context_raises_when_targets_do_not_fit():
    with pytest.raises(ContextTooLarge):
        render_context(inputs(targets=[("Huge", "x" * 10_000)]), 500)


class FakeTools:
    async def decls(self, rel_dir): return ["approxEqual"]


async def test_provider_builds_inputs(tmp_path):
    (tmp_path / "repo").mkdir()
    (tmp_path / "scratch").mkdir()
    ws = Workspace(tmp_path / "repo", tmp_path / "scratch")
    (ws.root / "a.go").write_text("package p\n\nimport \"errors\"\n\nvar ErrNeg = errors.New(\"neg\")\n\nfunc Abs(x int) (int, error) {\n\tif x < 0 {\n\t\treturn 0, ErrNeg\n\t}\n\treturn x, nil\n}\n")
    key = FuncKey(file="a.go", name="Abs")
    funcs = [FuncInfo(key=key, package="p", start_line=7, end_line=12, exported=True)]
    symbols = [Symbol(name="ErrNeg", kind="var", file="a.go", start_line=5, end_line=5)]
    report = CoverageReport(total_statements=3, covered_statements=0, percent=0, files=[], covered_block_ids=[],
                            functions=[FuncCoverage(key=key, statements=3, covered=0, uncovered_lines=[(8, 11)])])
    provider = ContextProvider(ws, FakeTools(), funcs, symbols, "m", "1.17", {".": GoPackage("m", ".", "p")})
    inp = await provider.inputs_for(PlanItem(file="a.go", functions=[key], uncovered_statements=3), report)
    assert inp.package == "p" and inp.test_file == "a_test.go" and inp.declared == ["approxEqual"]
    assert inp.targets[0][0] == "Abs" and "return 0, ErrNeg  // UNCOVERED" in inp.targets[0][1]
    assert inp.referenced == ['var ErrNeg = errors.New("neg")']
```

Run: `uv run pytest tests/test_context.py -q` → Expected: FAIL, `ModuleNotFoundError`.

- [ ] **Step 5: Implement `backend/app/agents/context.py`**

```python
# AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
"""Builds the compact, budgeted prompt context for one plan item. Deterministic and LLM-free."""
from __future__ import annotations

import posixpath
import re
from dataclasses import dataclass
from typing import Any

from app.gotools import GoPackage, Symbol
from app.llm.client import estimate_tokens
from app.models import CoverageReport, FuncInfo, FuncKey, PlanItem
from app.workspace import Workspace, test_path_for

_IDENT = re.compile(r"\b[A-Za-z_]\w*\b")
_SIGNATURE = re.compile(r"^(func \w+\([^)]*\)[^{\n]*)", re.M)


class ContextTooLarge(Exception):
    pass


@dataclass
class ContextInputs:
    module: str
    package: str
    go_version: str
    source_file: str
    test_file: str
    targets: list[tuple[str, str]]
    declared: list[str]
    referenced: list[str]
    existing_tests: list[str]


def go_version_rules(version: str) -> list[str]:
    parts = (version.split(".") + ["0"])[:2]
    minor = int(re.sub(r"\D.*", "", parts[1]) or 0)
    rules = ["Use only the Go standard library; never change go.mod."]
    if minor < 18:
        rules.append("No generics (type parameters) and no `any` alias; use interface{} if needed.")
    if minor < 21:
        rules.append("Do not use the `slices`, `maps` or `cmp` packages or the `min`/`max`/`clear` builtins.")
    if minor < 22:
        rules.append("Range loop variables are shared across iterations: copy them first (`tc := tc`) before using them in a closure.")
    rules.append("Do not call t.Parallel().")
    return rules


def annotate_source(lines: list[str], start: int, end: int, uncovered: list[tuple[int, int]]) -> str:
    first = start
    while first > 1 and lines[first - 2].lstrip().startswith("//"):
        first -= 1
    out = []
    for n in range(first, end + 1):
        text = lines[n - 1]
        if n >= start and any(a <= n <= b for a, b in uncovered):
            text += "  // UNCOVERED"
        out.append(text)
    return "\n".join(out)


def test_signatures(src: str | None) -> list[str]:
    return [m.group(1).strip() for m in _SIGNATURE.finditer(src or "")]


test_signatures.__test__ = False


def _header(inp: ContextInputs) -> str:
    rules = "\n".join(f"- {r}" for r in go_version_rules(inp.go_version))
    return (f"## Module\nmodule: {inp.module}\npackage: {inp.package} (write tests in `package {inp.package}`)\n"
            f"test file: {inp.test_file}\nGo language version: {inp.go_version}\nConstraints:\n{rules}")


def _declared(inp: ContextInputs) -> str:
    names = ", ".join(inp.declared) if inp.declared else "(none)"
    return f"## Names already declared in this package's tests (never redeclare these)\n{names}"


def _targets(inp: ContextInputs) -> str:
    blocks = [f"### {label} ({inp.source_file})\n```go\n{src}\n```" for label, src in inp.targets]
    return "## Functions to test (lines ending in `// UNCOVERED` are not executed by any test yet)\n" + "\n\n".join(blocks)


def _fit(text: str, title: str, items: list[str], budget: int, prefix: str = "", suffix: str = "") -> str:
    kept: list[str] = []
    for item in items:
        candidate = f"{text}\n\n{title}\n{prefix}" + "\n".join(kept + [item]) + suffix
        if estimate_tokens(candidate) > budget:
            break
        kept.append(item)
    if not kept:
        return text
    return f"{text}\n\n{title}\n{prefix}" + "\n".join(kept) + suffix


def render_context(inp: ContextInputs, budget_tokens: int) -> str:
    text = "\n\n".join([_header(inp), _declared(inp), _targets(inp)])
    if estimate_tokens(text) > budget_tokens:
        raise ContextTooLarge(f"targets need ~{estimate_tokens(text)} tokens; budget is {budget_tokens}")
    text = _fit(text, "## Related declarations in this package", inp.referenced, budget_tokens, "```go\n", "\n```")
    text = _fit(text, f"## Tests already in {inp.test_file} (signatures only; do not duplicate)",
                [f"- {s}" for s in inp.existing_tests], budget_tokens)
    return text


class ContextProvider:
    def __init__(self, ws: Workspace, tools: Any, funcs: list[FuncInfo], symbols: list[Symbol],
                 module: str, go_version: str, packages: dict[str, GoPackage]):
        self.ws, self.tools, self.module, self.go_version, self.packages = ws, tools, module, go_version, packages
        self.funcs: dict[FuncKey, FuncInfo] = {f.key: f for f in funcs}
        self.symbols = symbols
        self._lines: dict[str, list[str]] = {}

    def _file_lines(self, rel: str) -> list[str]:
        if rel not in self._lines:
            self._lines[rel] = (self.ws.read(rel) or "").splitlines()
        return self._lines[rel]

    async def inputs_for(self, item: PlanItem, report: CoverageReport) -> ContextInputs:
        rel_dir = posixpath.dirname(item.file) or "."
        coverage = {fc.key: fc for fc in report.functions}
        lines = self._file_lines(item.file)
        targets = []
        for key in item.functions:
            info = self.funcs[key]
            uncovered = coverage[key].uncovered_lines if key in coverage else []
            targets.append((key.label(), annotate_source(lines, info.start_line, info.end_line, uncovered)))
        target_text = "\n".join(src for _, src in targets)
        idents = set(_IDENT.findall(target_text)) - {k.name for k in item.functions}
        referenced, seen = [], set()
        for sym in self.symbols:
            if sym.name in idents and (posixpath.dirname(sym.file) or ".") == rel_dir and (sym.file, sym.start_line) not in seen:
                seen.add((sym.file, sym.start_line))
                referenced.append("\n".join(self._file_lines(sym.file)[sym.start_line - 1:sym.end_line]).strip())
        test_file = test_path_for(item.file)
        return ContextInputs(
            module=self.module, package=self.packages[rel_dir].name, go_version=self.go_version,
            source_file=item.file, test_file=test_file, targets=targets,
            declared=await self.tools.decls(rel_dir), referenced=referenced,
            existing_tests=test_signatures(self.ws.read(test_file)),
        )
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest tests/test_context.py -q` → Expected: 6 passed. Then `make test-integration` to confirm nothing regressed.

- [ ] **Step 7: Commit**

```bash
git add tools/gohelper backend/app/gotools.py backend/app/agents/context.py backend/tests/test_context.py
git commit -m "feat(agents): budgeted prompt context and gohelper symbols"
```

---

### Task 11: Deterministic planner and stop policy

**Files:**
- Create: `backend/app/agents/planner.py`, `backend/app/engine/policy.py`
- Test: `backend/tests/test_planner.py`, `backend/tests/test_policy.py`

**Interfaces:**
- Produces:
  - `plan(report: CoverageReport, failed: Mapping[FuncKey, int], skipped: set[FuncKey], *, max_items: int = 3, max_statements: int = 60, max_failures: int = 2) -> list[PlanItem]`
  - `StopPolicy(target: float, min_gain: float, patience: int)` with `.target_reached(percent) -> bool` and `.marginal(gains: list[float]) -> bool`
  - `stop_message(reason: StopReason, request: JobRequest, detail: str = "") -> str`

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_planner.py`:
```python
from app.agents.planner import plan
from app.models import CoverageReport, FuncCoverage, FuncKey


def fc(file, name, statements, covered=0):
    return FuncCoverage(key=FuncKey(file=file, name=name), statements=statements, covered=covered)


def report(*fns):
    return CoverageReport(total_statements=0, covered_statements=0, percent=0, files=[], functions=list(fns), covered_block_ids=[])


def test_groups_by_file_ranked_by_uncovered():
    r = report(fc("a.go", "A1", 10), fc("b.go", "B1", 30), fc("a.go", "A2", 5), fc("c.go", "C1", 1, covered=1))
    items = plan(r, {}, set())
    assert [i.file for i in items] == ["b.go", "a.go"]
    assert [k.name for k in items[1].functions] == ["A1", "A2"]
    assert items[1].uncovered_statements == 15


def test_respects_max_items_and_statement_cap():
    r = report(fc("a.go", "A1", 50), fc("a.go", "A2", 20), fc("b.go", "B", 9), fc("c.go", "C", 8), fc("d.go", "D", 7))
    items = plan(r, {}, set(), max_items=3, max_statements=60)
    assert [i.file for i in items] == ["a.go", "b.go", "c.go"]
    assert [k.name for k in items[0].functions] == ["A1"]  # A2 would exceed 60


def test_first_function_always_included_even_if_over_cap():
    items = plan(report(fc("a.go", "Big", 200)), {}, set(), max_statements=60)
    assert items[0].functions[0].name == "Big"


def test_skips_failed_and_skipped():
    a, b = FuncKey(file="a.go", name="A"), FuncKey(file="b.go", name="B")
    r = report(fc("a.go", "A", 10), fc("b.go", "B", 9), fc("c.go", "C", 1))
    assert [i.file for i in plan(r, {a: 2}, {b})] == ["c.go"]
    assert [i.file for i in plan(r, {a: 1}, set())][0] == "a.go"


def test_empty_when_nothing_left():
    assert plan(report(fc("a.go", "A", 3, covered=3)), {}, set()) == []
```

`backend/tests/test_policy.py`:
```python
from app.engine.policy import StopPolicy, stop_message
from app.models import JobRequest, StopReason


def test_target_and_marginal():
    p = StopPolicy(target=80, min_gain=1.0, patience=2)
    assert p.target_reached(80.0) and not p.target_reached(79.99)
    assert not p.marginal([0.5])
    assert not p.marginal([0.5, 3.0])
    assert p.marginal([5.0, 0.2, 0.9])


def test_messages_are_plain_language():
    req = JobRequest(repo_path="stats", target_coverage=80)
    assert stop_message(StopReason.TARGET_REACHED, req) == "Reached the 80% coverage target."
    assert "2 iterations" in stop_message(StopReason.MARGINAL_GAINS, req)
    assert stop_message(StopReason.BUDGET_EXHAUSTED, req, "daily cap").endswith("daily cap")
```

Run: `uv run pytest tests/test_planner.py tests/test_policy.py -q` → Expected: FAIL, `ModuleNotFoundError`.

- [ ] **Step 2: Implement `backend/app/agents/planner.py`**

```python
# AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
"""Chooses what to test next. Deterministic on purpose: it costs no LLM tokens and is easy to test."""
from __future__ import annotations

from typing import Mapping

from app.models import CoverageReport, FuncKey, PlanItem


def plan(report: CoverageReport, failed: Mapping[FuncKey, int], skipped: set[FuncKey], *,
         max_items: int = 3, max_statements: int = 60, max_failures: int = 2) -> list[PlanItem]:
    candidates = [fc for fc in report.functions
                  if fc.uncovered > 0 and failed.get(fc.key, 0) < max_failures and fc.key not in skipped]
    candidates.sort(key=lambda fc: (-fc.uncovered, fc.key.file, fc.key.receiver, fc.key.name))
    items: dict[str, PlanItem] = {}
    for fc in candidates:
        item = items.get(fc.key.file)
        if item is None:
            if len(items) >= max_items:
                continue
            item = items[fc.key.file] = PlanItem(file=fc.key.file, functions=[], uncovered_statements=0)
        if item.functions and item.uncovered_statements + fc.uncovered > max_statements:
            continue
        item.functions.append(fc.key)
        item.uncovered_statements += fc.uncovered
    return list(items.values())
```

- [ ] **Step 3: Implement `backend/app/engine/policy.py`**

```python
# AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
from __future__ import annotations

from dataclasses import dataclass

from app.models import JobRequest, StopReason


@dataclass
class StopPolicy:
    target: float
    min_gain: float
    patience: int

    def target_reached(self, percent: float) -> bool:
        return percent + 1e-9 >= self.target

    def marginal(self, gains: list[float]) -> bool:
        return len(gains) >= self.patience and all(g < self.min_gain for g in gains[-self.patience:])


def stop_message(reason: StopReason, request: JobRequest, detail: str = "") -> str:
    o = request.options
    target = f"{request.target_coverage:g}"
    text = {
        StopReason.TARGET_REACHED: f"Reached the {target}% coverage target.",
        StopReason.MARGINAL_GAINS: f"Stopped early: the last {o.patience} iterations each added less than {o.min_gain:g} percentage points.",
        StopReason.MAX_ITERATIONS: f"Stopped after the maximum of {o.max_iterations} iterations.",
        StopReason.NO_REMAINING_TARGETS: "Stopped: every remaining uncovered function was attempted without success or is too large for one request.",
        StopReason.BUDGET_EXHAUSTED: "Stopped: the LLM token budget ran out. Accepted tests were kept.",
        StopReason.CANCELLED: "Cancelled. Accepted tests were kept.",
    }[reason]
    return f"{text} {detail}".strip() if detail else text
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_planner.py tests/test_policy.py -q` → Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/planner.py backend/app/engine/policy.py backend/tests/test_planner.py backend/tests/test_policy.py
git commit -m "feat(engine): deterministic planner and stop policy"
```

---

### Task 12: Writer and Fixer agents, prompts, Groq smoke test

**Files:**
- Create: `backend/app/agents/llm_agents.py`, `backend/app/agents/prompts/writer.md`, `backend/app/agents/prompts/fixer.md`
- Create: `backend/tests/fakes.py`, `backend/scripts/groq_smoke.py`
- Test: `backend/tests/test_llm_agents.py`

**Interfaces:**
- Consumes: `LLMClient`, `estimate_tokens` (Task 9); `ContextInputs`, `render_context` (Task 10); `ValidationResult` (Task 7); `PlanItem`, `TestSnippet`, `TokenUsage`.
- Produces:
  - `Agents(llm: LLMClient, max_prompt_tokens: int)` with `async write(item, inputs) -> tuple[TestSnippet, TokenUsage]` and `async fix(item, inputs, snippet: TestSnippet, result: ValidationResult) -> tuple[TestSnippet, TokenUsage]`
  - `load_prompt(name: str) -> str`
  - In `tests/fakes.py`: `FakeLLM(responses)` with `.calls`, and a `snippet(code, imports=("testing",), plan=(), bugs=())` helper

- [ ] **Step 1: Write the prompts**

`backend/app/agents/prompts/writer.md`:
```markdown
You are an expert Go engineer writing unit tests that raise statement coverage.

You receive the module and package, the Go language version and its constraints, the names already declared in this package's tests, and the source of the target functions. Lines ending in `// UNCOVERED` are not executed by any test yet.

Write NEW tests that execute the uncovered lines and assert real behaviour.

Rules:
- Answer with JSON matching the schema. `code` contains only new top-level declarations (Test functions and, if needed, small helpers). Never include a package clause or import statements; list import paths in `imports`.
- Tests are internal: they live in the same package, so unexported identifiers are accessible.
- Use only the Go standard library. Never redeclare a name listed under "already declared".
- Prefer table-driven tests: a slice of cases with a `name` field, run with `t.Run(tc.name, ...)`. Never call `t.Parallel()`.
- Name tests like `TestMean`, `TestFloat64Data_Mean`, `TestPercentile_EmptyInput`.
- Check errors with `errors.Is` or by comparing with the package's exported error values. Check both the result and the error.
- Compare float64 results with a tolerance (for example `math.Abs(got-want) > 1e-9`). Handle NaN and Inf explicitly with `math.IsNaN` / `math.IsInf`.
- Only assert values you can derive with certainty from the source. If you cannot compute an exact expected value, assert a property instead (sign, ordering, length, error or no error).
- Exercise the edge cases the uncovered lines guard: empty input, nil, a single element, negative numbers, boundary indexes, invalid arguments.
- No `time.Sleep`, network, environment variables, unsynchronised goroutines, printing, or file writes outside `t.TempDir()`.
- Keep the answer focused: at most about 150 lines of code.
- `test_plan`: one entry per scenario you test, naming the target function.
- `suspected_bugs`: only when the source clearly contradicts its own documentation; otherwise an empty list.
```

`backend/app/agents/prompts/fixer.md`:
```markdown
You are fixing Go unit tests that were just rejected by an automated validator. You receive the original context, the rejected snippet, the rejection kind and the tool output.

Return a complete replacement snippet using the same JSON schema. The rejected snippet has been discarded, so include everything you want to keep.

How to handle each rejection kind:
- compile_error / vet_error: fix exactly the errors in the output. Common causes: undefined names, wrong types, unused variables or imports, redeclared identifiers (rename yours), Go version constraints.
- test_failure: the source code is the source of truth. If an assertion expected a value you mis-computed and the observed value is plausible for what the function documents, correct the expected value. If the observed behaviour contradicts the function's documentation, drop that case and describe it in `suspected_bugs`.
- no_gain: the tests ran but executed no new statements. Target the lines marked `// UNCOVERED` directly by constructing inputs that reach those branches.
- guard_rejected: the snippet broke a hard rule listed in the output. Remove the offending import or construct.

Every rule from the original task still applies: same package, standard library only, table-driven tests, no t.Parallel, and `code` without a package clause or imports.
```

- [ ] **Step 2: Write the shared fakes** — `backend/tests/fakes.py`

```python
from app.models import SuspectedBug, TestScenario, TestSnippet, TokenUsage


def snippet(code: str, imports=("testing",), plan=(), bugs=()) -> TestSnippet:
    return TestSnippet(test_plan=[TestScenario(scenario=s, target=t) for s, t in plan], imports=list(imports),
                       code=code, suspected_bugs=[SuspectedBug(function=f, description=d) for f, d in bugs])


class FakeLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls: list[dict] = []

    async def complete(self, *, role, system, user, schema):
        self.calls.append({"role": role, "system": system, "user": user, "schema": schema})
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item, TokenUsage(prompt_tokens=100, completion_tokens=50)
```

- [ ] **Step 3: Write the failing tests** — `backend/tests/test_llm_agents.py`

```python
from app.agents.context import ContextInputs
from app.agents.llm_agents import Agents
from app.llm.client import estimate_tokens
from app.models import FuncKey, PlanItem, TestSnippet
from app.validator import ValidationKind, ValidationResult
from tests.fakes import FakeLLM, snippet

ITEM = PlanItem(file="mean.go", functions=[FuncKey(file="mean.go", name="Mean")], uncovered_statements=4)
INPUTS = ContextInputs(module="m", package="stats", go_version="1.17", source_file="mean.go", test_file="mean_test.go",
                       targets=[("Mean", "func Mean(input Float64Data) (float64, error) {\n\treturn 0, nil  // UNCOVERED\n}")],
                       declared=[], referenced=["type Float64Data []float64"] * 400, existing_tests=[])


async def test_write_sends_context_task_and_schema_within_budget():
    llm = FakeLLM([snippet("func TestMean(t *testing.T) {}")])
    out, usage = await Agents(llm, max_prompt_tokens=1500).write(ITEM, INPUTS)
    call = llm.calls[0]
    assert call["role"] == "writer" and call["schema"] is TestSnippet
    assert "mean_test.go" in call["user"] and "Mean" in call["user"] and "// UNCOVERED" in call["user"]
    assert estimate_tokens(call["system"]) + estimate_tokens(call["user"]) <= 1500
    assert out.code.startswith("func TestMean") and usage.total == 150


async def test_fix_includes_rejection_kind_output_and_previous_code():
    llm = FakeLLM([snippet("func TestMean(t *testing.T) {}")])
    bad = snippet("func TestMean(t *testing.T) { undefinedThing() }")
    result = ValidationResult(ValidationKind.COMPILE_ERROR, "./mean_test.go:3:2: undefined: undefinedThing")
    await Agents(llm, max_prompt_tokens=2000).fix(ITEM, INPUTS, bad, result)
    user = llm.calls[0]["user"]
    assert llm.calls[0]["role"] == "fixer"
    assert "compile_error" in user and "undefined: undefinedThing" in user and "undefinedThing()" in user


async def test_fix_trims_huge_tool_output():
    llm = FakeLLM([snippet("func TestMean(t *testing.T) {}")])
    result = ValidationResult(ValidationKind.TEST_FAILURE, "x" * 50_000)
    await Agents(llm, max_prompt_tokens=4500).fix(ITEM, INPUTS, snippet("func TestMean(t *testing.T) {}"), result)
    assert len(llm.calls[0]["user"]) < 4500 * 3.5
```

Run: `uv run pytest tests/test_llm_agents.py -q` → Expected: FAIL, `ModuleNotFoundError`.

- [ ] **Step 4: Implement `backend/app/agents/llm_agents.py`**

```python
# AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
"""The two LLM roles: Writer (new tests) and Fixer (repair rejected tests)."""
from __future__ import annotations

from functools import cache
from pathlib import Path

from app.agents.context import ContextInputs, render_context
from app.llm.client import LLMClient, estimate_tokens
from app.models import PlanItem, TestSnippet, TokenUsage
from app.validator import ValidationResult

_PROMPTS = Path(__file__).parent / "prompts"


@cache
def load_prompt(name: str) -> str:
    return (_PROMPTS / f"{name}.md").read_text()


def _trim(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + "\n…[truncated]"


def _labels(item: PlanItem) -> str:
    return ", ".join(f"`{k.label()}`" for k in item.functions)


class Agents:
    def __init__(self, llm: LLMClient, max_prompt_tokens: int):
        self.llm = llm
        self.max_prompt_tokens = max_prompt_tokens

    def _user(self, system: str, inputs: ContextInputs, task: str) -> str:
        budget = self.max_prompt_tokens - estimate_tokens(system) - estimate_tokens(task) - 20
        return f"{render_context(inputs, budget)}\n\n{task}"

    async def write(self, item: PlanItem, inputs: ContextInputs) -> tuple[TestSnippet, TokenUsage]:
        system = load_prompt("writer")
        task = (f"## Task\nWrite new tests for {_labels(item)} that will be appended to `{inputs.test_file}`. "
                "Focus on executing the lines marked `// UNCOVERED`.")
        return await self.llm.complete(role="writer", system=system, user=self._user(system, inputs, task),
                                       schema=TestSnippet)

    async def fix(self, item: PlanItem, inputs: ContextInputs, snippet: TestSnippet,
                  result: ValidationResult) -> tuple[TestSnippet, TokenUsage]:
        system = load_prompt("fixer")
        task = (f"## Rejected snippet (kind: {result.kind.value})\n```go\n{_trim(snippet.code, 5000)}\n```\n\n"
                f"## Validator output\n```\n{_trim(result.output, 2500)}\n```\n\n"
                f"## Task\nReturn a corrected replacement snippet for {_labels(item)}.")
        return await self.llm.complete(role="fixer", system=system, user=self._user(system, inputs, task),
                                       schema=TestSnippet)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_llm_agents.py -q` → Expected: 3 passed.

- [ ] **Step 6: Write the smoke script** — `backend/scripts/groq_smoke.py`

```python
# AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
"""One real Groq Writer call against a repo, to measure tokens and latency. Run inside the backend image."""
import asyncio
import sys
import time

from app.agents.context import ContextProvider
from app.agents.llm_agents import Agents
from app.agents.planner import plan
from app.config import Settings
from app.gotools import GoTools, read_module_info
from app.llm.client import GroqLLM
from app.llm.limits import RateLimiter, UsageLedger
from app.validator import Validator
from app.workspace import Workspace, resolve_repo, test_path_for


async def main(repo: str) -> None:
    s = Settings()
    ws = Workspace.create(s.work_dir, f"smoke-{int(time.time())}", resolve_repo(s.repos_dir, repo))
    ws.delete_existing_tests()
    tools = GoTools(ws.root, s)
    pkgs = await tools.list_packages(["examples/**", "testdata/**"])
    ws.seed_packages([(p.rel_dir, p.name) for p in pkgs])
    module, go_version = read_module_info(ws.root)
    funcs = await tools.funcs()
    validator = Validator(ws, tools, pkgs, funcs, module)
    baseline = (await validator.measure()).report
    print(f"baseline: {baseline.percent}% of {baseline.total_statements} statements")
    item = plan(baseline, {}, set(), max_items=1)[0]
    contexts = ContextProvider(ws, tools, funcs, await tools.symbols(), module, go_version, {p.rel_dir: p for p in pkgs})
    inputs = await contexts.inputs_for(item, baseline)

    async def emit(t, d):
        print("event:", t, d)

    llm = GroqLLM(s, UsageLedger(s.output_dir / ".usage.json", s.daily_token_budget), RateLimiter(), emit=emit)
    started = time.monotonic()
    snippet, usage = await Agents(llm, s.max_prompt_tokens).write(item, inputs)
    print(f"target: {item.file} {[k.label() for k in item.functions]}")
    print(f"usage: prompt={usage.prompt_tokens} completion={usage.completion_tokens} seconds={time.monotonic() - started:.1f}")
    print(snippet.code)
    result = await validator.validate(test_path_for(item.file), inputs.package, snippet, baseline)
    print("validation:", result.kind.value, result.report.percent if result.report else None)
    print(result.output[:2000])


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "stats"))
```

- [ ] **Step 7: Run the smoke test against `stats` and record the numbers**

```bash
git clone --depth 1 https://github.com/montanaflynn/stats repos/stats
cp .env.example .env   # then put your real GROQ_API_KEY in .env
make backend-image
docker run --rm --env-file .env -v "$PWD/repos:/repos" -v "$PWD/output:/output" gca-backend \
  uv run --no-sync python -m scripts.groq_smoke stats
```
(Create an empty `backend/scripts/__init__.py` so `-m scripts.groq_smoke` works.)

Expected: a baseline of `0.0%`, one plan item, a usage line, Go code, and a validation result. Write the prompt/completion tokens and seconds into spec §6.7 under a new line "Measured on <date>: …".
- If `completion_tokens` is above ~2,500, set `GROQ_REASONING_EFFORT=low` (already the default) and lower `targets_per_iteration`.
  > Note (Task 32): `GROQ_REASONING_EFFORT` was replaced by the per-role settings `GROQ_WRITER_REASONING_EFFORT` (default `medium`) and `GROQ_FIXER_REASONING_EFFORT` (default `high`); see the spec §5.1. This low-effort advice no longer applies; the defaults are Writer `medium`, Fixer `high`.
- If validation is `compile_error` on idiom issues, tighten `writer.md` and re-run. Each run costs ~5K tokens.

- [ ] **Step 8: Commit**

```bash
git add backend/app/agents backend/tests/fakes.py backend/tests/test_llm_agents.py backend/scripts docs/
git commit -m "feat(agents): writer and fixer prompts with Groq smoke script"
```

---

### Task 13: Orchestrator

**Files:**
- Create: `backend/app/engine/orchestrator.py`
- Test: `backend/tests/test_orchestrator.py`

**Interfaces:**
- Consumes: `plan` (Task 11), `StopPolicy`, `stop_message` (Task 11), `ValidationKind`, `ValidationResult` (Task 7), `LLMError`, `LLMBudgetExhausted`, `LLMFatal`, `Emit` (Task 9), `ContextTooLarge` (Task 10), `Workspace`, `test_path_for` (Task 5), models.
- Produces:
  - `class Cancelled(Exception)`
  - `RunDeps(ws: Workspace, validator, agents, contexts, package_of: Callable[[str], str])` (dataclass; `validator`/`agents`/`contexts` are duck-typed to Task 7/12/10 classes)
  - `Orchestrator(deps: RunDeps, request: JobRequest, emit: Emit, cancel: asyncio.Event, clock=time.monotonic)` with `async run(baseline: CoverageReport) -> Summary`
  - Raises `LLMFatal` to the caller; all other stops become a `Summary`.

- [ ] **Step 1: Write the failing tests** — `backend/tests/test_orchestrator.py`

```python
import asyncio

import pytest

from app.agents.context import ContextTooLarge
from app.engine.orchestrator import Orchestrator, RunDeps
from app.llm.client import LLMBudgetExhausted, LLMFatal
from app.models import (CoverageReport, FileCoverage, FuncCoverage, FuncKey, JobOptions, JobRequest, StopReason,
                        TokenUsage)
from app.validator import ValidationKind, ValidationResult
from app.workspace import Workspace
from tests.fakes import snippet

# Toy coverage model: every function has two blocks "<name>:1" and "<name>:2".


def report(covered: set[str], funcs=(("a.go", "A"), ("b.go", "B"))) -> CoverageReport:
    fcs, files = [], {}
    for file, name in funcs:
        n = sum(1 for i in (1, 2) if f"{name}:{i}" in covered)
        fcs.append(FuncCoverage(key=FuncKey(file=file, name=name), statements=2, covered=n,
                                uncovered_lines=[] if n == 2 else [(1, 2)]))
        s, c = files.get(file, (0, 0))
        files[file] = (s + 2, c + n)
    total, cov = 2 * len(funcs), len(covered)
    return CoverageReport(total_statements=total, covered_statements=cov, percent=round(100 * cov / total, 2),
                          files=[FileCoverage(file=f, statements=s, covered=c, percent=round(100 * c / s, 2)) for f, (s, c) in files.items()],
                          functions=fcs, covered_block_ids=sorted(covered))


def accepted(covered, tests=("TestA",), funcs=(("a.go", "A"), ("b.go", "B"))):
    return ValidationResult(ValidationKind.ACCEPTED, report=report(set(covered), funcs), new_tests=list(tests))


class FakeValidator:
    def __init__(self, ws, results, prune_results=()):
        self.ws, self.results, self.prune_results = ws, list(results), list(prune_results)
        self.pruned = []

    async def validate(self, test_file, package, snip, prev):
        self.ws.write_test(test_file, "package p\n// merged\n")  # simulate gohelper merge
        return self.results.pop(0)

    async def prune_and_check(self, test_file, names, prev, new_tests):
        self.pruned.append(names)
        return self.prune_results.pop(0)


class FakeAgents:
    def __init__(self, writes, fixes=(), too_large_when_multi=False):
        self.writes, self.fixes = list(writes), list(fixes)
        self.write_items, self.fix_kinds = [], []
        self.too_large_when_multi = too_large_when_multi

    async def write(self, item, inputs):
        if self.too_large_when_multi and len(item.functions) > 1:
            raise ContextTooLarge("too big")  # the real Agents.write raises it from render_context
        self.write_items.append(item)
        r = self.writes.pop(0)
        if isinstance(r, Exception):
            raise r
        return r, TokenUsage(prompt_tokens=10, completion_tokens=5)

    async def fix(self, item, inputs, snip, result):
        self.fix_kinds.append(result.kind)
        return self.fixes.pop(0), TokenUsage(prompt_tokens=10, completion_tokens=5)


class FakeContexts:
    async def inputs_for(self, item, rep):
        return object()


@pytest.fixture
def ws(tmp_path):
    (tmp_path / "repo").mkdir()
    (tmp_path / "scratch").mkdir()
    return Workspace(tmp_path / "repo", tmp_path / "scratch")


def run(ws, validator, agents, target=100.0, contexts=None, cancel=None, **opts):
    events = []

    async def emit(t, d):
        events.append((t, d))

    req = JobRequest(repo_path="x", target_coverage=target, options=JobOptions(**opts))
    deps = RunDeps(ws=ws, validator=validator, agents=agents, contexts=contexts or FakeContexts(),
                   package_of=lambda f: "p")
    orch = Orchestrator(deps, req, emit, cancel or asyncio.Event())
    return orch, events


GOOD = snippet("func TestA(t *testing.T) {}", bugs=[("A", "looks odd")])


async def test_reaches_target_and_records_everything(ws):
    v = FakeValidator(ws, [accepted({"A:1", "A:2"})])
    orch, events = run(ws, v, FakeAgents([GOOD]), target=50)
    summary = await orch.run(report(set()))
    assert summary.stop_reason is StopReason.TARGET_REACHED
    assert summary.final_percent == 50.0 and summary.baseline_percent == 0.0
    assert summary.tests_added == ["TestA"] and summary.test_files == ["a_test.go"]
    assert summary.suspected_bugs[0].function == "A"
    assert summary.iterations[0].accepted == 1
    types = [t for t, _ in events]
    assert types[:3] == ["iteration_started", "plan_created", "llm_call"]
    assert "candidate_accepted" in types and "iteration_completed" in types
    assert ws.read("a_test.go") is not None


async def test_prunes_failing_new_tests_without_calling_fixer(ws):
    failing = ValidationResult(ValidationKind.TEST_FAILURE, "--- FAIL: TestBad", failed_tests=["TestBad"],
                               new_tests=["TestGood", "TestBad"])
    v = FakeValidator(ws, [failing], prune_results=[accepted({"A:1"}, tests=["TestGood"])])
    agents = FakeAgents([GOOD])
    orch, events = run(ws, v, agents, target=25)
    summary = await orch.run(report(set()))
    assert v.pruned == [["TestBad"]] and agents.fix_kinds == []
    assert summary.tests_added == ["TestGood"]
    assert ("tests_pruned", {"index": 1, "file": "a.go", "tests": ["TestBad"]}) in events


async def test_fixer_then_rejection_rolls_back_and_eventually_gives_up(ws):
    bad = ValidationResult(ValidationKind.COMPILE_ERROR, "undefined: x")
    v = FakeValidator(ws, [bad, bad, bad, bad])
    agents = FakeAgents([GOOD, GOOD], fixes=[GOOD, GOOD])
    orch, events = run(ws, v, agents, max_fix_attempts=1, patience=5, targets_per_iteration=1)
    summary = await orch.run(report(set(), funcs=(("a.go", "A"),)))
    assert agents.fix_kinds == [ValidationKind.COMPILE_ERROR, ValidationKind.COMPILE_ERROR]
    assert summary.stop_reason is StopReason.NO_REMAINING_TARGETS
    assert ws.read("a_test.go") is None, "rejected candidates must be rolled back"
    assert sum(1 for t, _ in events if t == "candidate_rejected") == 2


async def test_marginal_gains_stop(ws):
    v = FakeValidator(ws, [accepted({"A:1"})])
    orch, _ = run(ws, v, FakeAgents([GOOD]), min_gain=60, patience=1, targets_per_iteration=1)
    summary = await orch.run(report(set()))
    assert summary.stop_reason is StopReason.MARGINAL_GAINS


async def test_budget_exhaustion_stops_gracefully(ws):
    orch, _ = run(ws, FakeValidator(ws, []), FakeAgents([LLMBudgetExhausted("daily cap hit")]))
    summary = await orch.run(report(set()))
    assert summary.stop_reason is StopReason.BUDGET_EXHAUSTED and "daily cap hit" in summary.message


async def test_llm_fatal_propagates(ws):
    orch, _ = run(ws, FakeValidator(ws, []), FakeAgents([LLMFatal("bad key")]))
    with pytest.raises(LLMFatal):
        await orch.run(report(set()))


async def test_cancel_before_first_attempt(ws):
    cancel = asyncio.Event()
    cancel.set()
    orch, _ = run(ws, FakeValidator(ws, []), FakeAgents([]), cancel=cancel)
    assert (await orch.run(report(set()))).stop_reason is StopReason.CANCELLED


async def test_context_too_large_splits_multi_function_items(ws):
    funcs = (("a.go", "A"), ("a.go", "A2"))
    v = FakeValidator(ws, [accepted({"A:1", "A:2"}, funcs=funcs)])
    agents = FakeAgents([GOOD], too_large_when_multi=True)
    orch, _ = run(ws, v, agents, target=50)
    await orch.run(report(set(), funcs=funcs))
    assert len(agents.write_items[0].functions) == 1
```

Run: `uv run pytest tests/test_orchestrator.py -q` → Expected: FAIL, `ModuleNotFoundError`.

- [ ] **Step 2: Implement `backend/app/engine/orchestrator.py`**

```python
# AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
"""The autonomous loop: plan → write → validate → prune/fix → accept or roll back → repeat."""
from __future__ import annotations

import asyncio
import time
from collections import Counter
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from app.agents.context import ContextTooLarge
from app.agents.planner import plan
from app.engine.policy import StopPolicy, stop_message
from app.llm.client import Emit, LLMBudgetExhausted, LLMCancelled, LLMError, LLMFatal
from app.models import (CoverageReport, FileDelta, FuncKey, IterationRecord, JobRequest, PlanItem, StopReason,
                        Summary, SuspectedBug, TestSnippet, TokenUsage)
from app.validator import ValidationKind, ValidationResult
from app.workspace import Workspace, test_path_for


class Cancelled(Exception):
    pass


@dataclass
class RunDeps:
    ws: Workspace
    validator: Any
    agents: Any
    contexts: Any
    package_of: Callable[[str], str]


class Orchestrator:
    def __init__(self, deps: RunDeps, request: JobRequest, emit: Emit, cancel: asyncio.Event,
                 clock: Callable[[], float] = time.monotonic):
        self.deps, self.request, self.emit, self.cancel, self.clock = deps, request, emit, cancel, clock
        self.opts = request.options
        self.policy = StopPolicy(request.target_coverage, self.opts.min_gain, self.opts.patience)
        self.tokens = TokenUsage()
        self.failed: Counter[FuncKey] = Counter()
        self.skipped: set[FuncKey] = set()
        self.iterations: list[IterationRecord] = []
        self.gains: list[float] = []
        self.tests_added: list[str] = []
        self.test_files: list[str] = []
        self.bugs: list[SuspectedBug] = []
        self.index = 0

    async def run(self, baseline: CoverageReport) -> Summary:
        started = self.clock()
        self.baseline = self.report = baseline
        detail = ""
        try:
            reason = await self._loop()
        except LLMBudgetExhausted as e:
            reason, detail = StopReason.BUDGET_EXHAUSTED, str(e)
        except Cancelled:
            reason = StopReason.CANCELLED
        return self._summary(reason, detail, self.clock() - started)

    async def _loop(self) -> StopReason:
        for index in range(1, self.opts.max_iterations + 1):
            if self.policy.target_reached(self.report.percent):
                return StopReason.TARGET_REACHED
            items = plan(self.report, self.failed, self.skipped, max_items=self.opts.targets_per_iteration)
            if not items:
                return StopReason.NO_REMAINING_TARGETS
            self.index, start = index, self.report.percent
            await self.emit("iteration_started", {"index": index, "percent": start})
            await self.emit("plan_created", {"index": index, "items": [
                {"file": i.file, "functions": [k.label() for k in i.functions],
                 "uncovered_statements": i.uncovered_statements} for i in items]})
            accepted = rejected = 0
            for item in items:
                if await self._attempt(item):
                    accepted += 1
                else:
                    rejected += 1
                if self.policy.target_reached(self.report.percent):
                    await self._record(index, start, accepted, rejected)
                    return StopReason.TARGET_REACHED
            await self._record(index, start, accepted, rejected)
            if self.policy.marginal(self.gains):
                return StopReason.MARGINAL_GAINS
        return StopReason.MAX_ITERATIONS

    async def _record(self, index: int, start: float, accepted: int, rejected: int) -> None:
        end = self.report.percent
        self.iterations.append(IterationRecord(index=index, start_percent=start, end_percent=end,
                                               accepted=accepted, rejected=rejected))
        self.gains.append(end - start)
        await self.emit("iteration_completed", {"index": index, "start_percent": start, "end_percent": end,
                                                "accepted": accepted, "rejected": rejected})

    def _check(self) -> None:
        if self.cancel.is_set():
            raise Cancelled()
        if self.tokens.total >= self.opts.max_llm_tokens:
            raise LLMBudgetExhausted("Reached this job's token budget (max_llm_tokens).")

    async def _call(self, role: str, item: PlanItem,
                    coro: Awaitable[tuple[TestSnippet, TokenUsage]]) -> TestSnippet:
        try:
            snip, usage = await coro
        except LLMCancelled as e:
            raise Cancelled() from e
        self.tokens = self.tokens.add(usage)
        await self.emit("llm_call", {"index": self.index, "file": item.file, "role": role,
                                     "prompt_tokens": usage.prompt_tokens, "completion_tokens": usage.completion_tokens,
                                     "total_tokens": self.tokens.total})
        return snip

    async def _validate(self, base: dict[str, Any], coro: Awaitable[ValidationResult]) -> ValidationResult:
        result = await coro
        await self.emit("validation_result", {**base, **result.event()})
        return result

    async def _generated(self, base: dict[str, Any], test_file: str, snip: TestSnippet) -> None:
        await self.emit("candidate_generated", {**base, "test_file": test_file, "code": snip.code,
                                                "test_plan": [s.model_dump() for s in snip.test_plan]})

    async def _attempt(self, item: PlanItem) -> bool:
        self._check()
        ws, validator = self.deps.ws, self.deps.validator
        test_file, package = test_path_for(item.file), self.deps.package_of(item.file)
        base = {"index": self.index, "file": item.file}
        try:
            inputs = await self.deps.contexts.inputs_for(item, self.report)
        except ContextTooLarge:
            if len(item.functions) > 1:
                return await self._attempt(item.model_copy(update={"functions": item.functions[:1]}))
            self.skipped.update(item.functions)
            await self.emit("candidate_rejected", {**base, "reason": "too_large"})
            return False

        snap = ws.snapshot([test_file, "go.mod", "go.sum"])
        snip: TestSnippet | None = None
        try:
            try:
                # render_context (inside agents.write) is where ContextTooLarge is actually raised
                snip = await self._call("writer", item, self.deps.agents.write(item, inputs))
            except ContextTooLarge:
                ws.restore(snap)
                if len(item.functions) > 1:
                    return await self._attempt(item.model_copy(update={"functions": item.functions[:1]}))
                self.skipped.update(item.functions)
                await self.emit("candidate_rejected", {**base, "reason": "too_large"})
                return False
            await self._generated(base, test_file, snip)
            result = await self._validate(base, validator.validate(test_file, package, snip, self.report))
            attempts = 0
            while not result.accepted and attempts < self.opts.max_fix_attempts:
                self._check()
                if result.kind is ValidationKind.TEST_FAILURE:
                    doomed = [n for n in result.failed_tests if n in result.new_tests]
                    if doomed and len(doomed) == len(result.failed_tests) and len(doomed) < len(result.new_tests):
                        await self.emit("tests_pruned", {**base, "tests": doomed})
                        result = await self._validate(
                            base, validator.prune_and_check(test_file, doomed, self.report, result.new_tests))
                        if result.accepted:
                            break
                attempts += 1
                await self.emit("fix_attempt", {**base, "attempt": attempts, "kind": result.kind.value})
                ws.restore(snap)
                snip = await self._call("fixer", item, self.deps.agents.fix(item, inputs, snip, result))
                await self._generated(base, test_file, snip)
                result = await self._validate(base, validator.validate(test_file, package, snip, self.report))
        except (LLMBudgetExhausted, LLMFatal, Cancelled):
            ws.restore(snap)
            raise
        except (LLMError, ContextTooLarge) as e:
            result = ValidationResult(ValidationKind.LLM_ERROR, str(e))

        if result.accepted and result.report is not None:
            gain = round(result.report.percent - self.report.percent, 2)
            self.report = result.report
            self.tests_added.extend(result.new_tests)
            if test_file not in self.test_files:
                self.test_files.append(test_file)
            if snip is not None:
                self.bugs.extend(snip.suspected_bugs)
            await self.emit("candidate_accepted", {**base, "test_file": test_file, "tests": result.new_tests,
                                                   "percent": self.report.percent, "gain": gain})
            return True

        ws.restore(snap)
        for key in item.functions:
            self.failed[key] += 1
        await self.emit("candidate_rejected", {**base, "reason": result.kind.value})
        return False

    def _summary(self, reason: StopReason, detail: str, duration: float) -> Summary:
        before = {f.file: f.percent for f in self.baseline.files}
        per_file = sorted((FileDelta(file=f.file, before=before.get(f.file, 0.0), after=f.percent)
                           for f in self.report.files), key=lambda d: (-(d.after - d.before), d.file))
        return Summary(
            stop_reason=reason, message=stop_message(reason, self.request, detail),
            target=self.request.target_coverage, baseline_percent=self.baseline.percent,
            final_percent=self.report.percent, iterations=self.iterations, test_files=sorted(self.test_files),
            tests_added=self.tests_added, suspected_bugs=self.bugs, per_file=per_file, tokens=self.tokens,
            duration_s=round(duration, 1),
        )
```

- [ ] **Step 3: Run the tests to verify they pass**

Run: `uv run pytest tests/test_orchestrator.py -q` → Expected: 8 passed. Then run the whole unit suite: `uv run pytest -q` → all pass.

- [ ] **Step 4: Commit**

```bash
git add backend/app/engine/orchestrator.py backend/tests/test_orchestrator.py
git commit -m "feat(engine): autonomous orchestration loop"
```

---

### Task 14: Run setup, `run_job` and artifacts

**Files:**
- Create: `backend/app/engine/setup.py`, `backend/app/engine/run.py`
- Test: `backend/tests/test_run_unit.py`, `backend/tests/integration/test_run_job.py`

**Interfaces:**
- Consumes: everything from Tasks 5–13.
- Produces:
  - `class JobFailed(Exception)` with `reason`, `message`, `output`
  - `Prepared(deps: RunDeps, baseline: CoverageReport)` (dataclass)
  - `async prepare(job_id, request, settings, llm, emit, cancel) -> Prepared`
  - `write_artifacts(dest: Path, ws: Workspace | None, summary: Summary | None, events: list[Event]) -> None`
  - `async run_job(job_id, request, settings, llm, emit, cancel, events: Callable[[], list[Event]]) -> Summary`, which raises `JobFailed` (including for `LLMFatal`, as reason `llm_auth`)

- [ ] **Step 1: Write the failing unit tests** — `backend/tests/test_run_unit.py`

```python
import asyncio
import json

import pytest

from app.config import Settings
from app.engine.run import JobFailed, prepare, write_artifacts
from app.models import Event, JobRequest, StopReason, Summary, TokenUsage
from app.workspace import SEED_FILE, Workspace


async def test_prepare_rejects_bad_repo_path(tmp_path):
    (tmp_path / "repos").mkdir()
    settings = Settings(repos_dir=tmp_path / "repos", work_dir=tmp_path / "work")

    async def emit(t, d): pass

    with pytest.raises(JobFailed) as exc:
        await prepare("j1", JobRequest(repo_path="missing"), settings, llm=None, emit=emit, cancel=asyncio.Event())
    assert exc.value.reason == "invalid_repo"


def test_write_artifacts_exports_tests_report_and_events(tmp_path):
    (tmp_path / "repo").mkdir()
    (tmp_path / "scratch").mkdir()
    ws = Workspace(tmp_path / "repo", tmp_path / "scratch")
    ws.write_test("mean_test.go", "package stats\n")
    ws.write_test(SEED_FILE, "package stats\n")
    summary = Summary(stop_reason=StopReason.TARGET_REACHED, message="ok", target=80, baseline_percent=0,
                      final_percent=81, iterations=[], test_files=["mean_test.go"], tests_added=["TestMean"],
                      suspected_bugs=[], per_file=[], tokens=TokenUsage(), duration_s=1.0)
    events = [Event(seq=0, ts=1.0, type="job_started", data={})]
    dest = tmp_path / "out" / "j1"
    write_artifacts(dest, ws, summary, events)
    assert (dest / "tests" / "mean_test.go").read_text() == "package stats\n"
    assert not (dest / "tests" / SEED_FILE).exists()
    assert json.loads((dest / "report.json").read_text())["final_percent"] == 81
    assert (dest / "events.jsonl").read_text().count("\n") == 1
```

Run: `uv run pytest tests/test_run_unit.py -q` → Expected: FAIL, `ModuleNotFoundError`.

- [ ] **Step 2: Implement `backend/app/engine/setup.py`**

```python
# AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
"""Turns a JobRequest into a ready-to-run workspace with a measured baseline."""
from __future__ import annotations

import asyncio
import posixpath
from dataclasses import dataclass

from app.agents.context import ContextProvider
from app.agents.llm_agents import Agents
from app.config import Settings
from app.engine.orchestrator import RunDeps
from app.gotools import GoToolError, GoTools, read_module_info
from app.llm.client import Emit, LLMClient
from app.models import CoverageReport, JobRequest
from app.validator import Validator
from app.workspace import Workspace, WorkspaceError, resolve_repo


class JobFailed(Exception):
    def __init__(self, reason: str, message: str, output: str = ""):
        super().__init__(message)
        self.reason, self.message, self.output = reason, message, output


@dataclass
class Prepared:
    deps: RunDeps
    baseline: CoverageReport


async def prepare(job_id: str, request: JobRequest, settings: Settings, llm: LLMClient | None,
                  emit: Emit, cancel: asyncio.Event) -> Prepared:
    try:
        source = resolve_repo(settings.repos_dir, request.repo_path)
    except WorkspaceError as e:
        raise JobFailed("invalid_repo", str(e)) from e

    ws = Workspace.create(settings.work_dir, job_id, source)
    removed = ws.delete_existing_tests() if request.options.delete_existing_tests else []
    tools = GoTools(ws.root, settings, cancel)
    module, go_version = read_module_info(ws.root)
    try:
        packages = await tools.list_packages(request.options.exclude_patterns)
    except GoToolError as e:
        raise JobFailed("repo_does_not_build", "Go could not load this module.", e.result.combined) from e
    if not packages:
        raise JobFailed("no_packages", "No testable Go packages remain after exclusions.")
    ws.seed_packages([(p.rel_dir, p.name) for p in packages])
    await emit("workspace_ready", {"removed_tests": removed, "packages": [p.import_path for p in packages]})

    try:
        funcs = await tools.funcs()
        symbols = await tools.symbols()
    except GoToolError as e:
        raise JobFailed("repo_does_not_build", "Some Go files in this module could not be parsed.",
                        e.result.combined) from e
    validator = Validator(ws, tools, packages, funcs, module)
    measured = await validator.measure()
    if cancel.is_set():
        raise JobFailed("cancelled", "Cancelled before the baseline finished.")
    if measured.report is None:
        if ws.test_files():
            raise JobFailed("existing_tests_fail",
                            "The repo's existing tests fail. Enable 'delete existing tests' or fix them first.",
                            measured.result.combined)
        raise JobFailed("repo_does_not_build", "The repo does not build with this Go toolchain.",
                        measured.result.combined)
    vet = await tools.vet(packages)
    if vet.exit_code != 0:
        # Every candidate would be rejected as vet_error, so fail now instead of wasting the token budget.
        raise JobFailed("repo_vet_fails", "`go vet` already fails on the unmodified repo.", vet.combined)
    await emit("baseline_measured", {"report": measured.report.public()})

    by_dir = {p.rel_dir: p for p in packages}
    contexts = ContextProvider(ws, tools, funcs, symbols, module, go_version, by_dir)
    deps = RunDeps(ws=ws, validator=validator, agents=Agents(llm, settings.max_prompt_tokens), contexts=contexts,
                   package_of=lambda file: by_dir[posixpath.dirname(file) or "."].name)
    return Prepared(deps=deps, baseline=measured.report)
```

- [ ] **Step 3: Implement `backend/app/engine/run.py`**

```python
# AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from typing import Callable

from app.config import Settings
from app.engine.orchestrator import Orchestrator
from app.engine.setup import JobFailed, Prepared, prepare
from app.llm.client import Emit, LLMClient, LLMFatal
from app.models import Event, JobRequest, Summary
from app.workspace import Workspace

__all__ = ["JobFailed", "prepare", "run_job", "write_artifacts"]


def write_artifacts(dest: Path, ws: Workspace | None, summary: Summary | None, events: list[Event]) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    if ws is not None:
        files = summary.test_files if summary is not None else ws.test_files()
        for rel in files:
            src = ws.path(rel)
            if src.exists():
                target = dest / "tests" / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, target)
    if summary is not None:
        (dest / "report.json").write_text(summary.model_dump_json(indent=2))
    (dest / "events.jsonl").write_text("".join(e.model_dump_json() + "\n" for e in events))


async def run_job(job_id: str, request: JobRequest, settings: Settings, llm: LLMClient, emit: Emit,
                  cancel: asyncio.Event, events: Callable[[], list[Event]]) -> Summary:
    prepared: Prepared | None = None
    summary: Summary | None = None
    try:
        prepared = await prepare(job_id, request, settings, llm, emit, cancel)
        summary = await Orchestrator(prepared.deps, request, emit, cancel).run(prepared.baseline)
        return summary
    except LLMFatal as e:
        raise JobFailed("llm_auth", str(e)) from e
    finally:
        write_artifacts(settings.output_dir / job_id, prepared.deps.ws if prepared else None, summary, events())
```

- [ ] **Step 4: Run the unit tests to verify they pass**

Run: `uv run pytest tests/test_run_unit.py -q` → Expected: 2 passed.

- [ ] **Step 5: Write the end-to-end integration test with a fake LLM** — `backend/tests/integration/test_run_job.py`

```python
import asyncio

import pytest

from app.config import Settings
from app.engine.run import JobFailed, run_job
from app.models import JobRequest, StopReason
from tests.fakes import FakeLLM, snippet
from tests.integration.conftest import FIXTURES

pytestmark = pytest.mark.integration

FULL = """func TestAbs(t *testing.T) {
	if Abs(-3) != 3 || Abs(2) != 2 {
		t.Fatal("abs")
	}
}

func TestSqrt(t *testing.T) {
	cases := []struct {
		name string
		in   int
		want int
		err  error
	}{
		{"negative", -1, 0, ErrNegative},
		{"zero", 0, 0, nil},
		{"perfect", 9, 3, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := Sqrt(tc.in)
			if got != tc.want || !errors.Is(err, tc.err) {
				t.Fatalf("Sqrt(%d) = %d, %v", tc.in, got, err)
			}
		})
	}
}"""


def settings_for(tmp_path, fixture: str) -> Settings:
    repos = tmp_path / "repos"
    repos.mkdir()
    import shutil
    shutil.copytree(FIXTURES / fixture, repos / fixture)
    return Settings(repos_dir=repos, work_dir=tmp_path / "work", output_dir=tmp_path / "output")


async def test_full_run_reaches_target_with_fake_llm(tmp_path):
    settings = settings_for(tmp_path, "gomod")
    events = []

    async def emit(t, d):
        events.append(t)

    llm = FakeLLM([snippet(FULL, imports=["testing", "errors"])])
    summary = await run_job("j1", JobRequest(repo_path="gomod", target_coverage=90), settings, llm, emit,
                            asyncio.Event(), lambda: [])
    assert summary.stop_reason is StopReason.TARGET_REACHED, summary
    assert summary.final_percent == 100.0
    assert (settings.output_dir / "j1" / "tests" / "calc_test.go").exists()
    assert events[:2] == ["workspace_ready", "baseline_measured"]


async def test_broken_repo_fails_fast(tmp_path):
    settings = settings_for(tmp_path, "broken")

    async def emit(t, d): pass

    with pytest.raises(JobFailed) as exc:
        await run_job("j2", JobRequest(repo_path="broken"), settings, FakeLLM([]), emit, asyncio.Event(), lambda: [])
    assert exc.value.reason == "repo_does_not_build"
    assert "broken.go" in exc.value.output
```

Run: `make test-integration` → Expected: all integration tests pass (11).

- [ ] **Step 6: Commit**

```bash
git add backend/app/engine backend/tests
git commit -m "feat(engine): job setup, run_job and artifacts"
```

---

### Task 15: Job manager and event streaming

**Files:**
- Create: `backend/app/jobs.py`
- Test: `backend/tests/test_jobs.py`

**Interfaces:**
- Consumes: `run_job`, `JobFailed` (Task 14); `GroqLLM`, `Emit` (Task 9); `RateLimiter`, `UsageLedger` (Task 8); models.
- Produces:
  - `Runner = Callable[[Job, Emit, asyncio.Event], Awaitable[Summary]]`
  - `class JobConflict(Exception)` (`.job_id`) and `class JobRejected(Exception)` (`.status`, `.code`, `.message`)
  - `class Job` with fields `id`, `request`, `status`, `events`, `summary`, `cancel`, `finished`, `percent` and methods:
    - `async emit(type, data)`
    - `close()`
    - `stream() -> AsyncIterator[Event]` (replays from seq 0, then tails; no duplicates; ends after a terminal event)
    - `snapshot() -> dict`
    - `accepted_test_files() -> list[str]`
  - `class JobManager(settings, runner: Runner | None = None)` with attributes `ledger` and `limiter` and methods:
    - `start(request) -> Job`
    - `get(id) -> Job | None`
    - `list() -> list[Job]`
    - `running() -> Job | None`
    - `cancel(id) -> Job | None`

- [ ] **Step 1: Write the failing tests** — `backend/tests/test_jobs.py`

```python
import asyncio

import pytest

from app.config import Settings
from app.engine.run import JobFailed
from app.jobs import JobConflict, JobManager, JobRejected
from app.models import JobRequest, JobStatus, StopReason, Summary, TokenUsage


def summary(reason=StopReason.TARGET_REACHED) -> Summary:
    return Summary(stop_reason=reason, message="m", target=80, baseline_percent=0, final_percent=80,
                   iterations=[], test_files=[], tests_added=[], suspected_bugs=[], per_file=[],
                   tokens=TokenUsage(), duration_s=0.1)


def manager(tmp_path, runner, key="k"):
    s = Settings(groq_api_key=key, output_dir=tmp_path)
    return JobManager(s, runner=runner)


async def finish(job):
    await job.task


async def test_successful_job_emits_lifecycle(tmp_path):
    async def runner(job, emit, cancel):
        await emit("iteration_started", {"index": 1, "percent": 0})
        return summary()

    m = manager(tmp_path, runner)
    job = m.start(JobRequest(repo_path="stats"))
    await finish(job)
    assert job.status is JobStatus.COMPLETED
    assert [e.type for e in job.events] == ["job_started", "iteration_started", "job_completed"]
    assert [e.seq for e in job.events] == [0, 1, 2]


async def test_stream_replays_and_tails_without_duplicates(tmp_path):
    gate = asyncio.Event()

    async def runner(job, emit, cancel):
        await emit("a", {})
        await gate.wait()
        await emit("b", {})
        return summary()

    m = manager(tmp_path, runner)
    job = m.start(JobRequest(repo_path="stats"))
    await asyncio.sleep(0)  # let job_started + "a" happen
    await asyncio.sleep(0)

    async def collect():
        return [e.type async for e in job.stream()]

    early, late = asyncio.create_task(collect()), None
    await asyncio.sleep(0)
    gate.set()
    await finish(job)
    late = [e.type async for e in job.stream()]  # subscribe after completion
    assert await early == late == ["job_started", "a", "b", "job_completed"]


async def test_rejects_without_key_and_when_running_and_when_budget_low(tmp_path):
    async def slow(job, emit, cancel):
        await cancel.wait()
        return summary(StopReason.CANCELLED)

    with pytest.raises(JobRejected) as exc:
        manager(tmp_path, slow, key="").start(JobRequest(repo_path="stats"))
    assert exc.value.status == 400

    m = manager(tmp_path, slow)
    job = m.start(JobRequest(repo_path="stats"))
    with pytest.raises(JobConflict):
        m.start(JobRequest(repo_path="stats"))
    m.cancel(job.id)
    await finish(job)
    assert job.status is JobStatus.CANCELLED and job.events[-1].type == "job_cancelled"

    m.ledger.add(m.settings.daily_token_budget)
    with pytest.raises(JobRejected) as exc:
        m.start(JobRequest(repo_path="stats"))
    assert exc.value.status == 429


async def test_failures_become_job_failed_events(tmp_path):
    async def failing(job, emit, cancel):
        raise JobFailed("repo_does_not_build", "nope", "compiler says no")

    m = manager(tmp_path, failing)
    job = m.start(JobRequest(repo_path="stats"))
    await finish(job)
    assert job.status is JobStatus.FAILED
    assert job.events[-1].data == {"reason": "repo_does_not_build", "message": "nope", "output": "compiler says no"}

    async def crashing(job, emit, cancel):
        raise RuntimeError("boom")

    job = manager(tmp_path, crashing).start(JobRequest(repo_path="stats"))
    await finish(job)
    assert job.events[-1].data["reason"] == "internal_error"
```

Run: `uv run pytest tests/test_jobs.py -q` → Expected: FAIL, `ModuleNotFoundError`.

- [ ] **Step 2: Implement `backend/app/jobs.py`**

```python
# AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
"""In-memory job registry (one running job at a time) with replayable event streams."""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any, AsyncIterator, Awaitable, Callable

from app.config import Settings
from app.engine.run import JobFailed, run_job
from app.llm.client import Emit, GroqLLM
from app.llm.limits import RateLimiter, UsageLedger
from app.models import Event, JobRequest, JobStatus, StopReason, Summary

log = logging.getLogger(__name__)
TERMINAL = {"job_completed", "job_cancelled", "job_failed"}


class JobConflict(Exception):
    def __init__(self, job_id: str):
        super().__init__(job_id)
        self.job_id = job_id


class JobRejected(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


class Job:
    def __init__(self, job_id: str, request: JobRequest):
        self.id, self.request = job_id, request
        self.status = JobStatus.RUNNING
        self.created_at = time.time()
        self.events: list[Event] = []
        self.summary: Summary | None = None
        self.percent: float | None = None
        self.cancel = asyncio.Event()
        self.finished = False
        self.task: asyncio.Task[None] | None = None
        self._subscribers: list[asyncio.Queue[Event | None]] = []

    async def emit(self, type_: str, data: dict[str, Any]) -> None:
        event = Event(seq=len(self.events), ts=time.time(), type=type_, data=data)
        self.events.append(event)
        if type_ == "baseline_measured":
            self.percent = data["report"]["percent"]
        elif type_ == "candidate_accepted":
            self.percent = data["percent"]
        for q in self._subscribers:
            q.put_nowait(event)

    def close(self) -> None:
        self.finished = True
        for q in self._subscribers:
            q.put_nowait(None)

    async def stream(self) -> AsyncIterator[Event]:
        queue: asyncio.Queue[Event | None] = asyncio.Queue()
        self._subscribers.append(queue)
        done_at_subscribe = self.finished  # decide before replay: the job may finish while we yield
        try:
            last = -1
            for event in list(self.events):
                last = event.seq
                yield event
            if done_at_subscribe:
                return
            while (event := await queue.get()) is not None:
                if event.seq > last:
                    last = event.seq
                    yield event
        finally:
            self._subscribers.remove(queue)

    def accepted_test_files(self) -> list[str]:
        return sorted({e.data["test_file"] for e in self.events if e.type == "candidate_accepted"})

    def snapshot(self) -> dict[str, Any]:
        return {"id": self.id, "status": self.status.value, "request": self.request.model_dump(mode="json"),
                "created_at": self.created_at, "percent": self.percent, "event_count": len(self.events),
                "summary": self.summary.model_dump(mode="json") if self.summary else None}


Runner = Callable[[Job, Emit, asyncio.Event], Awaitable[Summary]]


class JobManager:
    def __init__(self, settings: Settings, runner: Runner | None = None):
        self.settings = settings
        self.ledger = UsageLedger(settings.output_dir / ".usage.json", settings.daily_token_budget)
        self.limiter = RateLimiter()
        self.jobs: dict[str, Job] = {}
        self._runner = runner or self._default_runner

    async def _default_runner(self, job: Job, emit: Emit, cancel: asyncio.Event) -> Summary:
        llm = GroqLLM(self.settings, self.ledger, self.limiter, emit=emit, cancel=cancel)
        return await run_job(job.id, job.request, self.settings, llm, emit, cancel, lambda: job.events)

    def running(self) -> Job | None:
        return next((j for j in self.jobs.values() if j.status is JobStatus.RUNNING), None)

    def get(self, job_id: str) -> Job | None:
        return self.jobs.get(job_id)

    def list(self) -> list[Job]:
        return sorted(self.jobs.values(), key=lambda j: j.created_at, reverse=True)

    def start(self, request: JobRequest) -> Job:
        if not self.settings.llm_configured:
            raise JobRejected(400, "llm_not_configured", "Set GROQ_API_KEY in .env and restart the app.")
        remaining = self.ledger.remaining()
        if remaining < self.settings.min_daily_tokens_to_start:
            raise JobRejected(429, "daily_budget_low",
                              f"Only ~{remaining:,} Groq tokens are left today; the budget resets at 00:00 UTC.")
        if (running := self.running()) is not None:
            raise JobConflict(running.id)
        job = Job(uuid.uuid4().hex[:12], request)
        self.jobs[job.id] = job
        job.task = asyncio.create_task(self._run(job))
        return job

    def cancel(self, job_id: str) -> Job | None:
        job = self.jobs.get(job_id)
        if job is not None and job.status is JobStatus.RUNNING:
            job.cancel.set()
        return job

    async def _run(self, job: Job) -> None:
        await job.emit("job_started", {"repo_path": job.request.repo_path,
                                       "target_coverage": job.request.target_coverage,
                                       "options": job.request.options.model_dump(mode="json"),
                                       "model": self.settings.groq_model})
        try:
            summary = await self._runner(job, job.emit, job.cancel)
            job.summary = summary
            if summary.stop_reason is StopReason.CANCELLED:
                job.status = JobStatus.CANCELLED
                await job.emit("job_cancelled", summary.model_dump(mode="json"))
            else:
                job.status = JobStatus.COMPLETED
                await job.emit("job_completed", summary.model_dump(mode="json"))
        except JobFailed as e:
            job.status = JobStatus.FAILED
            await job.emit("job_failed", {"reason": e.reason, "message": e.message, "output": e.output[:8000]})
        except Exception as e:  # noqa: BLE001 — surface anything unexpected to the UI
            log.exception("job %s crashed", job.id)
            job.status = JobStatus.FAILED
            await job.emit("job_failed", {"reason": "internal_error", "message": str(e), "output": ""})
        finally:
            # Rewrite events.jsonl here so it includes the terminal event (run_job wrote it earlier).
            try:
                out = self.settings.output_dir / job.id
                out.mkdir(parents=True, exist_ok=True)
                (out / "events.jsonl").write_text("".join(e.model_dump_json() + "\n" for e in job.events))
            except OSError:
                log.warning("could not write events.jsonl for job %s", job.id)
            job.close()
```

- [ ] **Step 3: Run the tests to verify they pass**

Run: `uv run pytest tests/test_jobs.py -q` → Expected: 4 passed.

- [ ] **Step 4: Commit**

```bash
git add backend/app/jobs.py backend/tests/test_jobs.py
git commit -m "feat(backend): job manager with replayable event streams"
```

---

### Task 16: HTTP API, repo listing, app factory

**Files:**
- Create: `backend/app/repos.py`, `backend/app/api.py`, `backend/app/main.py`
- Test: `backend/tests/test_api.py`, `backend/tests/test_repos.py`

**Interfaces:**
- Consumes: `JobManager`, `JobConflict`, `JobRejected` (Task 15); `resolve_repo`, `WorkspaceError` (Task 5); `run`, `read_module_info` (Task 6); `Settings`.
- Produces:
  - `RepoInfo(path, module, go_files, test_files)`
  - `list_repos(repos_dir: Path) -> list[RepoInfo]`
  - `async clone_sample(settings) -> RepoInfo`
  - `create_app(settings: Settings | None = None, manager: JobManager | None = None) -> FastAPI`, plus the module-level `app`
  - Routes exactly as listed in spec §8, with error body `{"error": {"code", "message"}}`

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_repos.py`:
```python
from app.repos import list_repos


def test_list_repos_finds_modules_two_levels_deep(tmp_path):
    (tmp_path / "stats").mkdir()
    (tmp_path / "stats" / "go.mod").write_text("module github.com/montanaflynn/stats\n\ngo 1.17\n")
    (tmp_path / "stats" / "mean.go").write_text("package stats\n")
    (tmp_path / "stats" / "mean_test.go").write_text("package stats\n")
    (tmp_path / "org" / "svc").mkdir(parents=True)
    (tmp_path / "org" / "svc" / "go.mod").write_text("module example.com/svc\n")
    (tmp_path / "notgo").mkdir()
    repos = list_repos(tmp_path)
    assert [(r.path, r.module, r.go_files, r.test_files) for r in repos] == [
        ("org/svc", "example.com/svc", 0, 0),
        ("stats", "github.com/montanaflynn/stats", 1, 1),
    ]


def test_list_repos_missing_dir_is_empty(tmp_path):
    assert list_repos(tmp_path / "nope") == []
```

`backend/tests/test_api.py`:
```python
import asyncio

import httpx
import pytest

from app.config import Settings
from app.jobs import JobManager
from app.main import create_app
from app.models import StopReason, Summary, TokenUsage


def summary():
    return Summary(stop_reason=StopReason.TARGET_REACHED, message="m", target=80, baseline_percent=0,
                   final_percent=80, iterations=[], test_files=["mean_test.go"], tests_added=[], suspected_bugs=[],
                   per_file=[], tokens=TokenUsage(), duration_s=0.1)


@pytest.fixture
def env(tmp_path):
    repos = tmp_path / "repos"
    (repos / "stats").mkdir(parents=True)
    (repos / "stats" / "go.mod").write_text("module github.com/montanaflynn/stats\n\ngo 1.17\n")
    work = tmp_path / "work"
    settings = Settings(groq_api_key="k", repos_dir=repos, work_dir=work, output_dir=tmp_path / "out")

    async def runner(job, emit, cancel):
        test_file = work / job.id / "repo" / "mean_test.go"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("package stats\n")
        await emit("candidate_accepted", {"index": 1, "file": "mean.go", "test_file": "mean_test.go",
                                          "tests": ["TestMean"], "percent": 80.0, "gain": 80.0})
        return summary()

    manager = JobManager(settings, runner=runner)
    app = create_app(settings, manager)
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
    return client, manager


async def test_health(env):
    client, _ = env
    body = (await client.get("/api/health")).json()
    assert body["llm_configured"] is True and body["model"] == "openai/gpt-oss-120b"
    assert "tokens_left_today" in body


async def test_repos_listing(env):
    client, _ = env
    assert (await client.get("/api/repos")).json()[0]["path"] == "stats"


async def test_job_lifecycle_events_and_files(env):
    client, manager = env
    r = await client.post("/api/jobs", json={"repo_path": "stats", "target_coverage": 80})
    assert r.status_code == 201
    job_id = r.json()["job_id"]
    await manager.get(job_id).task

    snap = (await client.get(f"/api/jobs/{job_id}")).json()
    assert snap["status"] == "completed" and snap["summary"]["final_percent"] == 80

    events = (await client.get(f"/api/jobs/{job_id}/events")).text
    assert events.count("data: ") == 3 and '"type":"job_completed"' in events.replace(" ", "")

    f = await client.get(f"/api/jobs/{job_id}/files/mean_test.go")
    assert f.status_code == 200 and f.text == "package stats\n"
    assert (await client.get(f"/api/jobs/{job_id}/files/..%2F..%2Fetc%2Fpasswd")).status_code == 404


async def test_errors_use_error_envelope(env):
    client, _ = env
    r = await client.post("/api/jobs", json={"repo_path": "/Users/me/code/stats"})
    assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_repo"
    assert "./repos" in r.json()["error"]["message"]
    r = await client.post("/api/jobs", json={"repo_path": "stats", "target_coverage": 500})
    assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_request"
    assert (await client.get("/api/jobs/nope")).status_code == 404
```

Add an autouse fixture to `backend/tests/conftest.py` (create the file). It resets sse-starlette's global exit event between event loops:
```python
import pytest


@pytest.fixture(autouse=True)
def _reset_sse_app_status():
    try:
        from sse_starlette.sse import AppStatus
    except ImportError:  # internals moved in a newer sse-starlette; nothing to reset
        yield
        return
    if hasattr(AppStatus, "should_exit_event"):
        AppStatus.should_exit_event = None
    yield
```

Run: `uv run pytest tests/test_repos.py tests/test_api.py -q` → Expected: FAIL, `ModuleNotFoundError`.

- [ ] **Step 2: Implement `backend/app/repos.py`**

```python
# AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel

from app.config import Settings
from app.gotools import read_module_info, run

_SKIP = {"vendor", "node_modules", "testdata"}


class RepoInfo(BaseModel):
    path: str
    module: str
    go_files: int
    test_files: int


def _count(root: Path) -> tuple[int, int]:
    go = tests = 0
    for p in root.rglob("*.go"):
        if any(part.startswith(".") or part in _SKIP for part in p.relative_to(root).parts[:-1]):
            continue
        if p.name.endswith("_test.go"):
            tests += 1
        else:
            go += 1
    return go, tests


def list_repos(repos_dir: Path) -> list[RepoInfo]:
    if not repos_dir.is_dir():
        return []
    candidates = [d for d in repos_dir.iterdir() if d.is_dir() and not d.name.startswith(".")]
    candidates += [g for d in list(candidates) if not (d / "go.mod").exists()
                   for g in d.iterdir() if g.is_dir() and not g.name.startswith(".")]
    found = []
    for d in candidates:
        if not (d / "go.mod").is_file():
            continue
        try:
            module, _ = read_module_info(d)
        except ValueError:
            continue
        go, tests = _count(d)
        found.append(RepoInfo(path=d.relative_to(repos_dir).as_posix(), module=module, go_files=go, test_files=tests))
    return sorted(found, key=lambda r: r.path)


async def clone_sample(settings: Settings) -> RepoInfo:
    dest = settings.repos_dir / "stats"
    if not (dest / "go.mod").exists():
        env = {"PATH": os.environ.get("PATH", ""), "HOME": os.environ.get("HOME", "/tmp"), "GIT_TERMINAL_PROMPT": "0"}
        r = await run(["git", "clone", "--depth", "1", settings.sample_repo_url, str(dest)],
                      cwd=settings.repos_dir, timeout=120, env=env)
        if r.exit_code != 0:
            raise RuntimeError(f"git clone failed: {r.combined[:500]}")
    return next(info for info in list_repos(settings.repos_dir) if info.path == "stats")
```

- [ ] **Step 3: Implement `backend/app/api.py`**

```python
# AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
from __future__ import annotations

import os

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse
from sse_starlette.sse import EventSourceResponse

from app.jobs import Job, JobConflict, JobManager, JobRejected
from app.models import JobRequest
from app.repos import clone_sample, list_repos
from app.workspace import WorkspaceError, resolve_repo

router = APIRouter(prefix="/api")


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def _manager(request: Request) -> JobManager:
    return request.app.state.manager


def _job(request: Request, job_id: str) -> Job:
    job = _manager(request).get(job_id)
    if job is None:
        raise ApiError(404, "job_not_found", f"No job with id {job_id!r}.")
    return job


@router.get("/health")
async def health(request: Request) -> dict:
    s, m = request.app.state.settings, _manager(request)
    return {"status": "ok", "go_version": request.app.state.go_version, "model": s.groq_model,
            "llm_configured": s.llm_configured, "tokens_left_today": m.ledger.remaining(),
            "storage_writable": os.access(s.output_dir, os.W_OK) and os.access(s.repos_dir, os.W_OK)}


@router.get("/repos")
async def repos(request: Request) -> list[dict]:
    return [r.model_dump() for r in list_repos(request.app.state.settings.repos_dir)]


@router.post("/repos/sample")
async def sample(request: Request) -> dict:
    try:
        return (await clone_sample(request.app.state.settings)).model_dump()
    except RuntimeError as e:
        raise ApiError(502, "clone_failed", str(e)) from e


@router.post("/jobs", status_code=201)
async def create_job(body: JobRequest, request: Request) -> dict:
    try:
        resolve_repo(request.app.state.settings.repos_dir, body.repo_path)
    except WorkspaceError as e:
        raise ApiError(400, "invalid_repo", str(e)) from e
    try:
        job = _manager(request).start(body)
    except JobConflict as e:
        raise ApiError(409, "job_running", f"Job {e.job_id} is still running.") from e
    except JobRejected as e:
        raise ApiError(e.status, e.code, e.message) from e
    return {"job_id": job.id}


@router.get("/jobs")
async def jobs(request: Request) -> list[dict]:
    return [j.snapshot() for j in _manager(request).list()]


@router.get("/jobs/{job_id}")
async def job(job_id: str, request: Request) -> dict:
    return _job(request, job_id).snapshot()


@router.get("/jobs/{job_id}/events")
async def events(job_id: str, request: Request) -> EventSourceResponse:
    job = _job(request, job_id)

    async def gen():
        async for event in job.stream():
            yield {"id": str(event.seq), "data": event.model_dump_json()}

    return EventSourceResponse(gen(), ping=15)


@router.post("/jobs/{job_id}/cancel")
async def cancel(job_id: str, request: Request) -> dict:
    _job(request, job_id)
    return _manager(request).cancel(job_id).snapshot()


@router.get("/jobs/{job_id}/files/{path:path}")
async def file(job_id: str, path: str, request: Request) -> PlainTextResponse:
    job = _job(request, job_id)
    if path not in job.accepted_test_files():
        raise ApiError(404, "file_not_found", "Not a generated test file of this job.")
    target = request.app.state.settings.work_dir / job_id / "repo" / path
    if not target.is_file():
        raise ApiError(404, "file_not_found", "File no longer exists.")
    return PlainTextResponse(target.read_text())
```

- [ ] **Step 4: Implement `backend/app/main.py`**

```python
# AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import ApiError, router
from app.config import Settings
from app.jobs import JobManager

log = logging.getLogger(__name__)


async def detect_go_version() -> str:
    try:
        proc = await asyncio.create_subprocess_exec("go", "version", stdout=asyncio.subprocess.PIPE)
        out, _ = await proc.communicate()
        return out.decode().split()[2] if proc.returncode == 0 else "unknown"
    except (FileNotFoundError, IndexError):
        return "unknown"


def create_app(settings: Settings | None = None, manager: JobManager | None = None) -> FastAPI:
    settings = settings or Settings()
    manager = manager or JobManager(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.go_version = await detect_go_version()
        for d in (settings.output_dir, settings.repos_dir):
            if not os.access(d, os.W_OK):
                log.warning("%s is not writable by this container user; on Linux run "
                            "`sudo chown -R 1000:1000 repos output` on the host.", d)
        yield

    app = FastAPI(title="Go Coverage Agent", lifespan=lifespan)
    app.state.settings, app.state.manager, app.state.go_version = settings, manager, "unknown"
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"], allow_headers=["*"])
    app.include_router(router)

    @app.exception_handler(ApiError)
    async def _api_error(_: Request, e: ApiError) -> JSONResponse:
        return JSONResponse({"error": {"code": e.code, "message": e.message}}, status_code=e.status)

    @app.exception_handler(RequestValidationError)
    async def _invalid(_: Request, e: RequestValidationError) -> JSONResponse:
        first = e.errors()[0]
        where = ".".join(str(p) for p in first.get("loc", [])[1:])
        return JSONResponse({"error": {"code": "invalid_request", "message": f"{where}: {first.get('msg')}"}},
                            status_code=400)

    return app


app = create_app()
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest -q` → Expected: all unit tests pass. If the SSE test hangs, check that the job finished before the request (it should; the test awaits `task`) and that the autouse fixture is in place.

- [ ] **Step 6: Commit**

```bash
git add backend/app backend/tests
git commit -m "feat(api): HTTP routes, SSE events, repo listing and app factory"
```

---

### Task 17: Compose (backend) and the end-to-end run on `stats` — MILESTONE

**Files:**
- Create: `docker-compose.yml`
- Modify: spec §6.7 (record measured numbers)

**Interfaces:**
- Consumes: the backend image (Task 6) and app (Task 16).
- Produces: a running backend at `http://localhost:8000` that completes a real job on `stats`. This is the go/no-go checkpoint for the day-3 milestone.

- [ ] **Step 1: Write `docker-compose.yml`** (frontend service added in Task 18)

```yaml
# AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
services:
  backend:
    build:
      context: .
      dockerfile: backend/Dockerfile
      args:
        GO_IMAGE: golang:1.27-bookworm   # keep in sync with .go-version
    env_file:
      - path: .env
        required: false
    ports:
      - "127.0.0.1:8000:8000"
    volumes:
      - ${HOST_REPOS_DIR:-./repos}:/repos
      - ./output:/output
      - gocache:/home/app/.cache
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"]
      interval: 10s
      timeout: 3s
      retries: 5

volumes:
  gocache: {}
```

- [ ] **Step 2: Start it and check health**

Run: `docker compose up --build -d backend && sleep 5 && curl -s localhost:8000/api/health`
Expected: `{"status":"ok","go_version":"go1.27…","model":"openai/gpt-oss-120b","llm_configured":true,…,"storage_writable":true}`

- [ ] **Step 3: Start a real job on `stats`**

```bash
curl -s -X POST localhost:8000/api/repos/sample
curl -s -X POST localhost:8000/api/jobs -H 'content-type: application/json' \
  -d '{"repo_path":"stats","target_coverage":80}'
# → {"job_id":"<id>"}
curl -N localhost:8000/api/jobs/<id>/events
```
Expected: events stream until `job_completed`. With free-tier limits, this takes roughly 20–45 minutes. Watch for `rate_limited` events.

- [ ] **Step 4: Independently verify the result**

```bash
VERIFY=$(mktemp -d)
git clone --depth 1 https://github.com/montanaflynn/stats "$VERIFY"
find "$VERIFY" -name '*_test.go' -delete
cp -r output/<id>/tests/. "$VERIFY"/
docker run --rm -v "$VERIFY:/src" -w /src golang:$(cat .go-version) sh -c \
  'go vet . && go test -count=1 -coverprofile=c.out . && go tool cover -func=c.out | tail -1'
```
Expected: `go vet` is clean, tests pass, and the `total:` line is ≥ 80.0% and matches `final_percent` in `output/<id>/report.json` (±0.1).

- [ ] **Step 5: Go/no-go review**

Summarize the run from `output/<id>/events.jsonl`:
```bash
python - <<'EOF'
import json, collections, sys
ev = [json.loads(l) for l in open(sys.argv[1] if len(sys.argv) > 1 else "output/<id>/events.jsonl")]
print(collections.Counter(e["type"] for e in ev))
print(collections.Counter(e["data"]["reason"] for e in ev if e["type"] == "candidate_rejected"))
done = [e for e in ev if e["type"] in ("job_completed", "job_failed")][-1]["data"]
print({k: done.get(k) for k in ("stop_reason", "final_percent", "duration_s", "tokens")})
EOF
```
- **Go:** ≥80% reached. Record duration, tokens and rejection counts in spec §6.7 under "Measured", then continue.
- **No-go:** fix the dominant rejection reason first: prompt rules (`writer.md`), `targets_per_iteration`, or `max_statements`. Re-run. If the daily cap blocks re-runs, use `GROQ_MODEL=openai/gpt-oss-20b` for iteration and confirm the final run on 120b the next day.

- [ ] **Step 6: Commit**

```bash
git add docker-compose.yml docs/
git commit -m "feat: compose backend and record end-to-end results on stats"
```

---

### Task 18: Frontend foundation — scaffold, types, API client, event reducer, container

**Files:**
- Create (scaffolded): `frontend/` via create-next-app
- Create: `frontend/vitest.config.ts`, `frontend/Dockerfile`, `frontend/.dockerignore`
- Create: `frontend/src/lib/types.ts`, `frontend/src/lib/api.ts`, `frontend/src/lib/runState.ts`, `frontend/src/lib/format.ts`, `frontend/src/lib/useJobEvents.ts`
- Modify: `frontend/next.config.ts`, `frontend/package.json` (add the `test` script), `docker-compose.yml` (add the frontend service)
- Test: `frontend/src/lib/runState.test.ts`, `frontend/src/lib/format.test.ts`

**Interfaces:**
- Consumes: the HTTP API (Task 16) and the event payload contract (Global Constraints).
- Produces:
  - Types: `JobEvent`, `CoverageReport`, `Summary`, `RepoInfo`, `Health`, `JobSnapshot`, `StartJobBody`, `StopReason`, `Scenario`, `SuspectedBug`
  - `api` object: `health`, `repos`, `cloneSample`, `startJob`, `jobs`, `job`, `cancel`, `file`, `eventsUrl`; and `ApiError(status, code, message)`
  - `reduce(state: RunState, ev: JobEvent): RunState`, `initialState`, and types `RunState`, `IterationView`, `ItemView`, `Attempt`
  - `pct`, `delta`, `duration`, `tokens`, `STOP_REASON_LABEL`, `REJECTION_LABEL`
  - `useJobEvents(jobId) -> { state, notFound, connection }`

- [ ] **Step 1: Scaffold**

```bash
npx create-next-app@latest frontend --typescript --tailwind --eslint --app --src-dir --import-alias "@/*" --use-npm --yes
cd frontend
npm install recharts shiki
npm install -D vitest
```
In `frontend/package.json` `"scripts"`, add `"test": "vitest run"`.

`frontend/next.config.ts`:
```ts
// AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
import type { NextConfig } from "next";

const nextConfig: NextConfig = { output: "standalone" };

export default nextConfig;
```

`frontend/vitest.config.ts`:
```ts
import path from "node:path";
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: { environment: "node", include: ["src/**/*.test.ts"] },
  resolve: { alias: { "@": path.resolve(__dirname, "src") } },
});
```

- [ ] **Step 2: Write `frontend/src/lib/types.ts`**

```ts
// AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
// Mirrors backend/app/models.py and the event payload contract in the implementation plan.

export type FuncKey = { file: string; receiver: string; name: string };
export type FileCoverage = { file: string; statements: number; covered: number; percent: number };
export type FuncCoverage = { key: FuncKey; statements: number; covered: number; uncovered_lines: [number, number][] };
export type CoverageReport = {
  total_statements: number;
  covered_statements: number;
  percent: number;
  files: FileCoverage[];
  functions: FuncCoverage[];
};

export type Scenario = { scenario: string; target: string };
export type SuspectedBug = { function: string; description: string };

export type StopReason =
  | "target_reached"
  | "marginal_gains"
  | "max_iterations"
  | "no_remaining_targets"
  | "budget_exhausted"
  | "cancelled";

export type Summary = {
  stop_reason: StopReason;
  message: string;
  target: number;
  baseline_percent: number;
  final_percent: number;
  iterations: { index: number; start_percent: number; end_percent: number; accepted: number; rejected: number }[];
  test_files: string[];
  tests_added: string[];
  suspected_bugs: SuspectedBug[];
  per_file: { file: string; before: number; after: number }[];
  tokens: { prompt_tokens: number; completion_tokens: number };
  duration_s: number;
};

export type JobOptions = {
  max_iterations: number;
  min_gain: number;
  patience: number;
  targets_per_iteration: number;
  max_fix_attempts: number;
  delete_existing_tests: boolean;
  max_llm_tokens: number;
  exclude_patterns: string[];
};

export type StartJobBody = { repo_path: string; target_coverage: number; options?: Partial<JobOptions> };

export type JobEvent = { seq: number; ts: number; type: string; data: Record<string, any> };

export type RepoInfo = { path: string; module: string; go_files: number; test_files: number };

export type Health = {
  status: string;
  go_version: string;
  model: string;
  llm_configured: boolean;
  tokens_left_today: number;
  storage_writable: boolean;
};

export type JobSnapshot = {
  id: string;
  status: "running" | "completed" | "failed" | "cancelled";
  request: { repo_path: string; target_coverage: number; options: JobOptions };
  created_at: number;
  percent: number | null;
  event_count: number;
  summary: Summary | null;
};
```

- [ ] **Step 3: Write `frontend/src/lib/api.ts`**

```ts
// AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
import type { Health, JobSnapshot, RepoInfo, StartJobBody } from "./types";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: { "content-type": "application/json", ...(init?.headers ?? {}) },
      cache: "no-store",
    });
  } catch {
    throw new ApiError(0, "unreachable", `Can't reach the backend at ${API_URL}. Is \`docker compose up\` running?`);
  }
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new ApiError(res.status, body?.error?.code ?? "http_error", body?.error?.message ?? res.statusText);
  }
  const type = res.headers.get("content-type") ?? "";
  return (type.includes("application/json") ? res.json() : res.text()) as Promise<T>;
}

const encodePath = (p: string) => p.split("/").map(encodeURIComponent).join("/");

export const api = {
  health: () => request<Health>("/api/health"),
  repos: () => request<RepoInfo[]>("/api/repos"),
  cloneSample: () => request<RepoInfo>("/api/repos/sample", { method: "POST" }),
  startJob: (body: StartJobBody) =>
    request<{ job_id: string }>("/api/jobs", { method: "POST", body: JSON.stringify(body) }),
  jobs: () => request<JobSnapshot[]>("/api/jobs"),
  job: (id: string) => request<JobSnapshot>(`/api/jobs/${id}`),
  cancel: (id: string) => request<JobSnapshot>(`/api/jobs/${id}/cancel`, { method: "POST" }),
  file: (id: string, path: string) => request<string>(`/api/jobs/${id}/files/${encodePath(path)}`),
  eventsUrl: (id: string) => `${API_URL}/api/jobs/${id}/events`,
};
```

- [ ] **Step 4: Write the failing reducer and format tests**

`frontend/src/lib/runState.test.ts`:
```ts
import { describe, expect, it } from "vitest";
import { initialState, reduce } from "./runState";
import type { JobEvent } from "./types";

const report = (percent: number) => ({ total_statements: 10, covered_statements: percent / 10, percent, files: [], functions: [] });
let seq = 0;
const ev = (type: string, data: Record<string, any>, ts = 1000): JobEvent => ({ seq: seq++, ts, type, data });

function run(events: JobEvent[]) {
  return events.reduce(reduce, initialState);
}

describe("reduce", () => {
  it("builds a full run view from events", () => {
    seq = 0;
    const s = run([
      ev("job_started", { repo_path: "stats", target_coverage: 80, options: {}, model: "openai/gpt-oss-120b" }),
      ev("workspace_ready", { removed_tests: ["mean_test.go"], packages: ["m"] }),
      ev("baseline_measured", { report: report(0) }),
      ev("iteration_started", { index: 1, percent: 0 }),
      ev("plan_created", { index: 1, items: [{ file: "mean.go", functions: ["Mean"], uncovered_statements: 4 }] }),
      ev("llm_call", { index: 1, file: "mean.go", role: "writer", prompt_tokens: 100, completion_tokens: 50, total_tokens: 150 }),
      ev("candidate_generated", { index: 1, file: "mean.go", test_file: "mean_test.go", test_plan: [{ scenario: "empty", target: "Mean" }], code: "func TestMean" }),
      ev("validation_result", { index: 1, file: "mean.go", kind: "test_failure", output: "--- FAIL", failed_tests: ["TestMean"] }),
      ev("fix_attempt", { index: 1, file: "mean.go", attempt: 1, kind: "test_failure" }),
      ev("validation_result", { index: 1, file: "mean.go", kind: "accepted", output: "", failed_tests: [] }),
      ev("candidate_accepted", { index: 1, file: "mean.go", test_file: "mean_test.go", tests: ["TestMean"], percent: 40, gain: 40 }),
      ev("iteration_completed", { index: 1, start_percent: 0, end_percent: 40, accepted: 1, rejected: 0 }),
    ]);
    expect(s.status).toBe("running");
    expect(s.target).toBe(80);
    expect(s.removedTests).toEqual(["mean_test.go"]);
    expect(s.percent).toBe(40);
    expect(s.tokens).toBe(150);
    expect(s.history).toEqual([{ label: "Baseline", percent: 0 }, { label: "Iter 1", percent: 40 }]);
    const item = s.iterations[0].items[0];
    expect(item.status).toBe("accepted");
    expect(item.attempts.map((a) => a.kind)).toEqual(["test_failure"]);
    expect(item.testPlan[0].scenario).toBe("empty");
    expect(item.tests).toEqual(["TestMean"]);
  });

  it("ignores events it has already seen (reconnect replay)", () => {
    seq = 0;
    const first = ev("job_started", { repo_path: "stats", target_coverage: 80, options: {}, model: "m" });
    const once = reduce(initialState, first);
    expect(reduce(once, first)).toBe(once);
  });

  it("shows rate-limit waits and terminal states", () => {
    seq = 0;
    let s = run([ev("job_started", { repo_path: "stats", target_coverage: 80, options: {}, model: "m" }),
                 ev("rate_limited", { seconds: 41, reason: "tpm" })]);
    expect(s.activity).toContain("41s");
    s = reduce(s, ev("job_failed", { reason: "repo_does_not_build", message: "nope", output: "x" }));
    expect(s.status).toBe("failed");
    expect(s.failure?.reason).toBe("repo_does_not_build");
  });
});
```

`frontend/src/lib/format.test.ts`:
```ts
import { describe, expect, it } from "vitest";
import { delta, duration, pct, tokens } from "./format";

describe("format", () => {
  it("formats numbers for humans", () => {
    expect(pct(81.234)).toBe("81.2%");
    expect(pct(undefined)).toBe("—");
    expect(delta(3.25)).toBe("+3.3 pp");
    expect(delta(-1)).toBe("−1.0 pp");
    expect(duration(42.4)).toBe("42s");
    expect(duration(1859.6)).toBe("30m 59s");
    expect(tokens(950)).toBe("950");
    expect(tokens(152_300)).toBe("152.3k");
  });
});
```

Run: `cd frontend && npm test` → Expected: FAIL (modules missing).

- [ ] **Step 5: Implement `frontend/src/lib/format.ts`**

```ts
// AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
import type { StopReason } from "./types";

export const pct = (n?: number | null) => (n == null ? "—" : `${n.toFixed(1)}%`);
export const delta = (n: number) => `${n >= 0 ? "+" : "−"}${Math.abs(n).toFixed(1)} pp`;
export const duration = (s: number) =>
  s < 60 ? `${Math.floor(s)}s` : `${Math.floor(s / 60)}m ${Math.floor(s % 60)}s`;
export const tokens = (n: number) => (n >= 1000 ? `${(n / 1000).toFixed(1)}k` : `${n}`);

export const STOP_REASON_LABEL: Record<StopReason, string> = {
  target_reached: "Target reached",
  marginal_gains: "Diminishing returns",
  max_iterations: "Iteration limit reached",
  no_remaining_targets: "Nothing left to try",
  budget_exhausted: "Token budget used up",
  cancelled: "Cancelled",
};

export const REJECTION_LABEL: Record<string, string> = {
  compile_error: "Didn't compile",
  vet_error: "go vet failed",
  test_failure: "Tests failed",
  no_gain: "No new coverage",
  guard_rejected: "Blocked by safety rules",
  llm_error: "Model error",
  too_large: "Too large for one request",
};
```

- [ ] **Step 6: Implement `frontend/src/lib/runState.ts`**

```ts
// AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
// Pure reducer: the same code handles live events and replay after a refresh or reconnect.
import type { CoverageReport, JobEvent, Scenario, Summary } from "./types";

export type ItemStatus = "writing" | "validating" | "fixing" | "accepted" | "rejected";
export type Attempt = { kind: string; output: string; failedTests: string[] };
export type ItemView = {
  file: string;
  functions: string[];
  uncovered: number;
  status: ItemStatus;
  testPlan: Scenario[];
  code?: string;
  attempts: Attempt[];
  pruned: string[];
  tests: string[];
  gain?: number;
  rejectReason?: string;
};
export type IterationView = { index: number; startPercent: number; endPercent?: number; items: ItemView[] };
export type RunState = {
  lastSeq: number;
  status: "connecting" | "running" | "completed" | "failed" | "cancelled";
  repoPath?: string;
  model?: string;
  startedAt?: number;
  target: number;
  removedTests: string[];
  baseline?: CoverageReport;
  percent: number;
  history: { label: string; percent: number }[];
  iterations: IterationView[];
  activity: string;
  tokens: number;
  summary?: Summary;
  failure?: { reason: string; message: string; output: string };
};

export const initialState: RunState = {
  lastSeq: -1,
  status: "connecting",
  target: 0,
  removedTests: [],
  percent: 0,
  history: [],
  iterations: [],
  activity: "Connecting…",
  tokens: 0,
};

function withIteration(s: RunState, index: number, fn: (it: IterationView) => IterationView): RunState {
  return { ...s, iterations: s.iterations.map((it) => (it.index === index ? fn(it) : it)) };
}

function withItem(s: RunState, index: number, file: string, fn: (item: ItemView) => ItemView): RunState {
  return withIteration(s, index, (it) => ({ ...it, items: it.items.map((i) => (i.file === file ? fn(i) : i)) }));
}

export function reduce(state: RunState, ev: JobEvent): RunState {
  if (ev.seq <= state.lastSeq) return state;
  const s: RunState = { ...state, lastSeq: ev.seq };
  const d = ev.data;
  switch (ev.type) {
    case "job_started":
      return { ...s, status: "running", repoPath: d.repo_path, model: d.model, target: d.target_coverage,
               startedAt: ev.ts, activity: "Preparing a working copy…" };
    case "workspace_ready":
      return { ...s, removedTests: d.removed_tests, activity: "Measuring baseline coverage…" };
    case "baseline_measured":
      return { ...s, baseline: d.report, percent: d.report.percent,
               history: [{ label: "Baseline", percent: d.report.percent }], activity: "Planning what to test…" };
    case "iteration_started":
      return { ...s, iterations: [...s.iterations, { index: d.index, startPercent: d.percent, items: [] }],
               activity: `Iteration ${d.index}: choosing targets…` };
    case "plan_created":
      return {
        ...withIteration(s, d.index, (it) => ({
          ...it,
          items: d.items.map((i: any) => ({ file: i.file, functions: i.functions, uncovered: i.uncovered_statements,
                                            status: "writing", testPlan: [], attempts: [], pruned: [], tests: [] })),
        })),
        activity: d.items.length ? `Writing tests for ${d.items[0].file}…` : s.activity,
      };
    case "llm_call":
      return { ...s, tokens: d.total_tokens };
    case "rate_limited":
      return { ...s, activity: `Waiting ${Math.round(d.seconds)}s for the Groq rate limit (${d.reason === "tpm" ? "tokens per minute" : "HTTP 429"})…` };
    case "candidate_generated":
      return { ...withItem(s, d.index, d.file, (i) => ({ ...i, status: "validating", testPlan: d.test_plan, code: d.code })),
               activity: `Compiling and running tests for ${d.file}…` };
    case "validation_result":
      return d.kind === "accepted" ? s : withItem(s, d.index, d.file, (i) => ({
        ...i, attempts: [...i.attempts, { kind: d.kind, output: d.output, failedTests: d.failed_tests }] }));
    case "tests_pruned":
      return withItem(s, d.index, d.file, (i) => ({ ...i, pruned: [...i.pruned, ...d.tests] }));
    case "fix_attempt":
      return { ...withItem(s, d.index, d.file, (i) => ({ ...i, status: "fixing" })),
               activity: `Fixing ${String(d.kind).replace("_", " ")} in ${d.file} (attempt ${d.attempt})…` };
    case "candidate_accepted":
      return { ...withItem(s, d.index, d.file, (i) => ({ ...i, status: "accepted", tests: d.tests, gain: d.gain })),
               percent: d.percent };
    case "candidate_rejected":
      return withItem(s, d.index, d.file, (i) => ({ ...i, status: "rejected", rejectReason: d.reason }));
    case "iteration_completed":
      return { ...withIteration(s, d.index, (it) => ({ ...it, endPercent: d.end_percent })),
               history: [...s.history, { label: `Iter ${d.index}`, percent: d.end_percent }] };
    case "job_completed":
    case "job_cancelled":
      return { ...s, status: ev.type === "job_completed" ? "completed" : "cancelled", summary: d as Summary,
               percent: d.final_percent, activity: d.message };
    case "job_failed":
      return { ...s, status: "failed", failure: { reason: d.reason, message: d.message, output: d.output },
               activity: d.message };
    default:
      return s;
  }
}
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `npm test` → Expected: 4 passed.

- [ ] **Step 8: Implement `frontend/src/lib/useJobEvents.ts`**

```ts
// AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
"use client";
import { useEffect, useReducer, useRef, useState } from "react";
import { api, ApiError } from "./api";
import { initialState, reduce } from "./runState";

const TERMINAL = new Set(["completed", "failed", "cancelled"]);

export function useJobEvents(jobId: string) {
  const [state, dispatch] = useReducer(reduce, initialState);
  const [notFound, setNotFound] = useState(false);
  const [connection, setConnection] = useState<"open" | "reconnecting">("open");
  const source = useRef<EventSource | null>(null);

  useEffect(() => {
    let cancelled = false;
    api.job(jobId).then(
      () => {
        if (cancelled) return;
        const es = new EventSource(api.eventsUrl(jobId));
        source.current = es;
        es.onopen = () => setConnection("open");
        es.onerror = () => setConnection("reconnecting");
        es.onmessage = (m) => dispatch(JSON.parse(m.data));
      },
      (e) => { if (e instanceof ApiError && e.status === 404) setNotFound(true); },
    );
    return () => {
      cancelled = true;
      source.current?.close();
    };
  }, [jobId]);

  useEffect(() => {
    if (TERMINAL.has(state.status)) source.current?.close(); // stop EventSource from reconnecting forever
  }, [state.status]);

  return { state, notFound, connection };
}
```

- [ ] **Step 9: Container and compose**

`frontend/.dockerignore`:
```
node_modules
.next
```

`frontend/Dockerfile`:
```dockerfile
# AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
# Debian (glibc) rather than Alpine: Tailwind v4 / lightningcss native binaries in a lockfile made on
# Windows may lack the musl variants, which breaks `npm run build` on Mac ARM.
FROM node:22-bookworm-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:22-bookworm-slim AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:22-bookworm-slim
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
RUN groupadd --system app && useradd --system --gid app app
COPY --from=build --chown=app:app /app/.next/standalone ./
COPY --from=build --chown=app:app /app/.next/static ./.next/static
COPY --from=build --chown=app:app /app/public ./public
USER app
EXPOSE 3000
CMD ["node", "server.js"]
```

Append to `docker-compose.yml` under `services:`:
```yaml
  frontend:
    build:
      context: ./frontend
      args:
        NEXT_PUBLIC_API_URL: http://localhost:8000
    ports:
      - "127.0.0.1:3000:3000"
    depends_on:
      backend:
        condition: service_healthy
```

Run: `docker compose build frontend` → Expected: build succeeds.

- [ ] **Step 10: Commit**

```bash
git add frontend docker-compose.yml
git commit -m "feat(frontend): scaffold, typed API client, event reducer and container"
```

---

### Task 19: Run setup page

**Files:**
- Modify: `frontend/src/app/layout.tsx`, `frontend/src/app/globals.css`, `frontend/src/app/page.tsx`
- Create: `frontend/src/components/RepoPicker.tsx`

**Interfaces:**
- Consumes: `api`, `ApiError`, types (Task 18).
- Produces: the `/` page. It starts a job and navigates to `/jobs/{id}`.

- [ ] **Step 1: Set the visual direction**

Invoke the `frontend-design` skill with this brief: "Developer tool UI for an autonomous Go test generator. Calm, precise, data-dense but readable, light and dark. One accent colour for progress/accept, one for reject. Monospace for code, file names and numbers." Record the chosen fonts and colour tokens as CSS variables in `globals.css` (`--bg`, `--surface`, `--border`, `--text`, `--muted`, `--accent`, `--danger`, `--warn`), with a `prefers-color-scheme: dark` override, and map them in Tailwind via `@theme` (Tailwind v4) so classes like `bg-surface text-muted border-border` work. The component code below uses exactly those class names.

- [ ] **Step 2: Layout** — `frontend/src/app/layout.tsx`

```tsx
// AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Go Coverage Agent",
  description: "Autonomously plans, writes and validates Go unit tests until a coverage target is met.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-bg text-text antialiased">
        <header className="border-b border-border">
          <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
            <Link href="/" className="font-mono text-sm font-semibold tracking-tight">go-coverage-agent</Link>
            <span className="text-xs text-muted">Tests written by an LLM on Groq, validated by the Go toolchain</span>
          </div>
        </header>
        <main className="mx-auto max-w-5xl px-4 py-8">{children}</main>
      </body>
    </html>
  );
}
```

- [ ] **Step 3: Repo picker** — `frontend/src/components/RepoPicker.tsx`

```tsx
// AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
"use client";
import type { RepoInfo } from "@/lib/types";

type Props = {
  repos: RepoInfo[];
  value: string;
  onChange: (path: string) => void;
  onUseSample: () => void;
  cloning: boolean;
};

export function RepoPicker({ repos, value, onChange, onUseSample, cloning }: Props) {
  return (
    <fieldset className="space-y-3">
      <legend className="text-sm font-medium">Repository</legend>
      {repos.length === 0 && (
        <p className="text-sm text-muted">
          No Go modules found in <code className="font-mono">./repos</code>. Clone one there, or use the sample.
        </p>
      )}
      <div className="grid gap-2 sm:grid-cols-2">
        {repos.map((r) => (
          <label key={r.path}
                 className={`cursor-pointer rounded-md border px-3 py-2 text-sm ${value === r.path ? "border-accent bg-surface" : "border-border"}`}>
            <input type="radio" name="repo" className="sr-only" checked={value === r.path} onChange={() => onChange(r.path)} />
            <span className="block font-mono">{r.path}</span>
            <span className="block text-xs text-muted">{r.module} · {r.go_files} source files · {r.test_files} test files</span>
          </label>
        ))}
      </div>
      <button type="button" onClick={onUseSample} disabled={cloning}
              className="text-sm text-accent underline-offset-4 hover:underline disabled:opacity-50">
        {cloning ? "Cloning montanaflynn/stats…" : "Use sample repo (montanaflynn/stats)"}
      </button>
      <label className="block space-y-1 text-sm">
        <span className="block text-muted">…or type a path inside <code className="font-mono">./repos</code></span>
        <input type="text" value={value} onChange={(e) => onChange(e.target.value)} placeholder="stats"
               className="w-full max-w-md rounded-md border border-border bg-surface px-2 py-1 font-mono" />
      </label>
    </fieldset>
  );
}
```

- [ ] **Step 4: Setup page** — `frontend/src/app/page.tsx`

```tsx
// AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { RepoPicker } from "@/components/RepoPicker";
import { api, ApiError } from "@/lib/api";
import { tokens } from "@/lib/format";
import type { Health, JobOptions, JobSnapshot, RepoInfo } from "@/lib/types";

const DEFAULTS: Pick<JobOptions, "max_iterations" | "min_gain" | "targets_per_iteration" | "max_fix_attempts"> = {
  max_iterations: 10, min_gain: 1, targets_per_iteration: 3, max_fix_attempts: 2,
};

export default function SetupPage() {
  const router = useRouter();
  const [health, setHealth] = useState<Health | null>(null);
  const [repos, setRepos] = useState<RepoInfo[]>([]);
  const [running, setRunning] = useState<JobSnapshot | null>(null);
  const [repo, setRepo] = useState("");
  const [target, setTarget] = useState(80);
  const [opts, setOpts] = useState(DEFAULTS);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [cloning, setCloning] = useState(false);

  useEffect(() => {
    Promise.all([api.health(), api.repos(), api.jobs()])
      .then(([h, r, j]) => {
        setHealth(h);
        setRepos(r);
        setRepo((cur) => cur || r[0]?.path || "");
        setRunning(j.find((x) => x.status === "running") ?? null);
      })
      .catch((e) => setError(e.message));
  }, []);

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

  return (
    <form onSubmit={start} className="space-y-8">
      <section>
        <h1 className="text-2xl font-semibold tracking-tight">Raise Go test coverage, autonomously</h1>
        <p className="mt-2 max-w-2xl text-sm text-muted">
          Pick a Go module and a target. The agent measures coverage, plans what to test, writes tests with an LLM,
          compiles and runs them, keeps only the ones that pass and add coverage, and repeats.
        </p>
      </section>

      {health && !health.llm_configured && (
        <div role="alert" className="rounded-md border border-warn px-4 py-3 text-sm">
          No Groq API key configured. Add <code className="font-mono">GROQ_API_KEY</code> to <code className="font-mono">.env</code> and restart <code className="font-mono">docker compose</code>.
        </div>
      )}
      {running && (
        <div className="rounded-md border border-border px-4 py-3 text-sm">
          A run is in progress on <span className="font-mono">{running.request.repo_path}</span>.{" "}
          <Link className="text-accent underline-offset-4 hover:underline" href={`/jobs/${running.id}`}>View it</Link>
        </div>
      )}

      <RepoPicker repos={repos} value={repo} onChange={setRepo} onUseSample={useSample} cloning={cloning} />

      <div className="space-y-2">
        <label htmlFor="target" className="text-sm font-medium">Target coverage</label>
        <div className="flex items-center gap-4">
          <input id="target" type="range" min={10} max={100} step={1} value={target}
                 onChange={(e) => setTarget(Number(e.target.value))} className="w-64 accent-[var(--accent)]" />
          <input type="number" min={1} max={100} value={target} aria-label="Target coverage percent"
                 onChange={(e) => setTarget(Number(e.target.value))}
                 className="w-20 rounded-md border border-border bg-surface px-2 py-1 font-mono text-sm" />
          <span className="text-sm text-muted">%</span>
        </div>
      </div>

      <details className="rounded-md border border-border px-4 py-3">
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
                     className="w-24 rounded-md border border-border bg-surface px-2 py-1 font-mono" />
            </label>
          ))}
        </div>
      </details>

      <ul className="space-y-1 text-xs text-muted">
        <li>Existing <code className="font-mono">_test.go</code> files are removed from a working copy. Your repository is never modified.</li>
        <li>Source code of the selected repository is sent to Groq.</li>
        {health && <li>About {tokens(health.tokens_left_today)} Groq tokens left today on this machine.</li>}
      </ul>

      {error && <p role="alert" className="text-sm text-danger">{error}</p>}

      <button type="submit" disabled={busy || !repo || !health?.llm_configured || !!running}
              className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-40">
        {busy ? "Starting…" : "Start"}
      </button>
    </form>
  );
}
```

- [ ] **Step 5: Verify in the browser**

Run: `docker compose up --build`, then open `http://localhost:3000`.
Expected:
- The repo list shows `stats`.
- Without a key, the warning banner shows and Start is disabled.
- With a key, clicking Start navigates to `/jobs/<id>` (the page is built in Task 20; a 404 is expected for now).

Use the Playwright plugin to take a screenshot of `/` and check it at a 390px viewport: no horizontal scroll.

- [ ] **Step 6: Commit**

```bash
git add frontend
git commit -m "feat(frontend): run setup page"
```

---

### Task 20: Live run and results page

**Files:**
- Create: `frontend/src/app/jobs/[id]/page.tsx`
- Create: `frontend/src/components/CoverageMeter.tsx`, `Timeline.tsx`, `CoverageChart.tsx`, `FileTable.tsx`, `TestFiles.tsx`, `SummaryCard.tsx`

**Interfaces:**
- Consumes: `useJobEvents`, `RunState`, `ItemView`, `api`, `format` helpers (Task 18).
- Produces: the `/jobs/[id]` page.

- [ ] **Step 1: `CoverageMeter.tsx`**

```tsx
// AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
import { pct } from "@/lib/format";

export function CoverageMeter({ percent, target, baseline }: { percent: number; target: number; baseline?: number }) {
  return (
    <div className="space-y-2" aria-label={`Coverage ${pct(percent)} of target ${pct(target)}`}>
      <div className="flex items-baseline justify-between">
        <span className="font-mono text-4xl font-semibold tabular-nums">{pct(percent)}</span>
        <span className="text-sm text-muted">target {pct(target)}{baseline != null && ` · baseline ${pct(baseline)}`}</span>
      </div>
      <div className="relative h-2 rounded-full bg-surface">
        <div className="h-2 rounded-full bg-accent transition-[width] duration-500" style={{ width: `${Math.min(percent, 100)}%` }} />
        <div className="absolute -top-1 h-4 w-0.5 bg-text" style={{ left: `${Math.min(target, 100)}%` }} title="Target" />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: `Timeline.tsx`**

```tsx
// AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
import { delta, pct, REJECTION_LABEL } from "@/lib/format";
import type { ItemView, IterationView } from "@/lib/runState";

const STATUS_STYLE: Record<ItemView["status"], string> = {
  writing: "text-muted", validating: "text-muted", fixing: "text-warn", accepted: "text-accent", rejected: "text-danger",
};

function Item({ item }: { item: ItemView }) {
  const label = item.status === "accepted" ? `Accepted ${item.gain != null ? delta(item.gain) : ""}`
    : item.status === "rejected" ? REJECTION_LABEL[item.rejectReason ?? ""] ?? "Rejected"
    : item.status === "fixing" ? "Fixing…" : item.status === "validating" ? "Running…" : "Writing…";
  return (
    <details className="rounded-md border border-border px-3 py-2">
      <summary className="flex cursor-pointer items-center justify-between gap-4 text-sm">
        <span className="font-mono">{item.file} <span className="text-muted">· {item.functions.join(", ")}</span></span>
        <span className={`shrink-0 ${STATUS_STYLE[item.status]}`}>{label}</span>
      </summary>
      <div className="mt-3 space-y-3 text-sm">
        {item.testPlan.length > 0 && (
          <div>
            <h4 className="text-xs font-medium uppercase tracking-wide text-muted">What it decided to test</h4>
            <ul className="mt-1 list-disc pl-5">
              {item.testPlan.map((s, i) => <li key={i}><span className="font-mono text-xs">{s.target}</span> — {s.scenario}</li>)}
            </ul>
          </div>
        )}
        {item.attempts.map((a, i) => (
          <div key={i}>
            <h4 className="text-xs font-medium uppercase tracking-wide text-muted">
              Attempt {i + 1}: {REJECTION_LABEL[a.kind] ?? a.kind}
            </h4>
            {a.output && <pre className="mt-1 max-h-48 overflow-auto rounded bg-surface p-2 font-mono text-xs">{a.output}</pre>}
          </div>
        ))}
        {item.pruned.length > 0 && <p className="text-xs text-muted">Removed failing tests: {item.pruned.join(", ")}</p>}
        {item.tests.length > 0 && <p className="text-xs">Kept: <span className="font-mono">{item.tests.join(", ")}</span></p>}
      </div>
    </details>
  );
}

export function Timeline({ iterations }: { iterations: IterationView[] }) {
  if (iterations.length === 0) return null;
  return (
    <ol className="space-y-6">
      {iterations.map((it) => (
        <li key={it.index}>
          <h3 className="mb-2 text-sm font-medium">
            Iteration {it.index}{" "}
            <span className="text-muted">{pct(it.startPercent)}{it.endPercent != null && ` → ${pct(it.endPercent)}`}</span>
          </h3>
          <div className="space-y-2">{it.items.map((item, i) => <Item key={`${item.file}-${i}`} item={item} />)}</div>
        </li>
      ))}
    </ol>
  );
}
```

- [ ] **Step 3: `CoverageChart.tsx`**

```tsx
// AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
"use client";
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export function CoverageChart({ history, target }: { history: { label: string; percent: number }[]; target: number }) {
  if (history.length < 2) return null;
  return (
    <div className="h-56 w-full" role="img" aria-label="Coverage after each iteration">
      <ResponsiveContainer>
        <LineChart data={history} margin={{ top: 8, right: 16, bottom: 0, left: -16 }}>
          <CartesianGrid stroke="var(--border)" vertical={false} />
          <XAxis dataKey="label" stroke="var(--muted)" fontSize={12} />
          <YAxis domain={[0, 100]} stroke="var(--muted)" fontSize={12} unit="%" />
          <Tooltip formatter={(v: number) => `${v.toFixed(1)}%`}
                   contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)" }} />
          <ReferenceLine y={target} stroke="var(--text)" strokeDasharray="4 4" label={{ value: "target", fill: "var(--muted)", fontSize: 11 }} />
          <Line type="monotone" dataKey="percent" stroke="var(--accent)" strokeWidth={2} dot={{ r: 3 }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
```

- [ ] **Step 4: `FileTable.tsx`, `SummaryCard.tsx`, `TestFiles.tsx`**

```tsx
// FileTable.tsx — AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
import { delta, pct } from "@/lib/format";
import type { Summary } from "@/lib/types";

export function FileTable({ rows }: { rows: Summary["per_file"] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="text-left text-xs uppercase tracking-wide text-muted">
          <tr><th className="py-2 font-medium">File</th><th className="font-medium">Before</th><th className="font-medium">After</th><th className="font-medium">Change</th></tr>
        </thead>
        <tbody className="font-mono tabular-nums">
          {rows.map((r) => (
            <tr key={r.file} className="border-t border-border">
              <td className="py-1.5">{r.file}</td><td>{pct(r.before)}</td><td>{pct(r.after)}</td>
              <td className={r.after > r.before ? "text-accent" : "text-muted"}>{delta(r.after - r.before)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

```tsx
// SummaryCard.tsx — AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
import { duration, pct, STOP_REASON_LABEL, tokens } from "@/lib/format";
import type { Summary } from "@/lib/types";

export function SummaryCard({ summary, jobId }: { summary: Summary; jobId: string }) {
  const outPath = `./output/${jobId}/tests`;
  const stats: [string, string][] = [
    ["Coverage", `${pct(summary.baseline_percent)} → ${pct(summary.final_percent)}`],
    ["Tests added", String(summary.tests_added.length)],
    ["Test files", String(summary.test_files.length)],
    ["Duration", duration(summary.duration_s)],
    ["Tokens", tokens(summary.tokens.prompt_tokens + summary.tokens.completion_tokens)],
  ];
  return (
    <section className="rounded-md border border-border p-4">
      <h2 className="text-lg font-semibold">{STOP_REASON_LABEL[summary.stop_reason]}</h2>
      <p className="mt-1 text-sm text-muted">{summary.message}</p>
      <dl className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-5">
        {stats.map(([k, v]) => (
          <div key={k}><dt className="text-xs text-muted">{k}</dt><dd className="font-mono text-sm tabular-nums">{v}</dd></div>
        ))}
      </dl>
      <div className="mt-4 flex items-center gap-2 text-sm">
        <span className="text-muted">Generated tests saved to</span>
        <code className="font-mono">{outPath}</code>
        <button type="button" className="text-accent underline-offset-4 hover:underline"
                onClick={() => navigator.clipboard.writeText(outPath)}>Copy</button>
      </div>
    </section>
  );
}
```

```tsx
// TestFiles.tsx — AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export function TestFiles({ jobId, files }: { jobId: string; files: string[] }) {
  const [active, setActive] = useState(files[0]);
  const [html, setHtml] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!active) return;
    let stale = false;
    setError(null);
    (async () => {
      try {
        const code = await api.file(jobId, active);
        const { codeToHtml } = await import("shiki");
        const out = await codeToHtml(code, { lang: "go", themes: { light: "github-light", dark: "github-dark" } });
        if (!stale) setHtml(out);
      } catch (e) {
        if (!stale) setError((e as Error).message);
      }
    })();
    return () => { stale = true; };
  }, [jobId, active]);

  if (files.length === 0) return <p className="text-sm text-muted">No tests were accepted.</p>;
  return (
    <div className="grid gap-4 md:grid-cols-[14rem_1fr]">
      <ul className="space-y-1 font-mono text-sm">
        {files.map((f) => (
          <li key={f}>
            <button type="button" onClick={() => setActive(f)}
                    className={`w-full truncate rounded px-2 py-1 text-left ${f === active ? "bg-surface" : "text-muted hover:text-text"}`}>
              {f}
            </button>
          </li>
        ))}
      </ul>
      <div className="min-w-0 overflow-auto rounded-md border border-border text-xs [&_pre]:p-4">
        {error ? <p className="p-4 text-danger">{error}</p> : <div dangerouslySetInnerHTML={{ __html: html }} />}
      </div>
    </div>
  );
}
```

Add to `globals.css` so Shiki's dual theme follows dark mode:
```css
@media (prefers-color-scheme: dark) {
  .shiki, .shiki span { color: var(--shiki-dark) !important; background-color: var(--shiki-dark-bg) !important; }
}
```

- [ ] **Step 5: The page** — `frontend/src/app/jobs/[id]/page.tsx`

```tsx
// AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { CoverageChart } from "@/components/CoverageChart";
import { CoverageMeter } from "@/components/CoverageMeter";
import { FileTable } from "@/components/FileTable";
import { SummaryCard } from "@/components/SummaryCard";
import { TestFiles } from "@/components/TestFiles";
import { Timeline } from "@/components/Timeline";
import { api } from "@/lib/api";
import { duration, tokens } from "@/lib/format";
import { useJobEvents } from "@/lib/useJobEvents";

function useElapsed(startedAt?: number, running?: boolean) {
  const [now, setNow] = useState(() => Date.now() / 1000);
  useEffect(() => {
    if (!running) return;
    const t = setInterval(() => setNow(Date.now() / 1000), 1000);
    return () => clearInterval(t);
  }, [running]);
  return startedAt ? Math.max(0, now - startedAt) : 0;
}

export default function JobPage() {
  const { id } = useParams<{ id: string }>();
  const { state, notFound, connection } = useJobEvents(id);
  const running = state.status === "running" || state.status === "connecting";
  const elapsed = useElapsed(state.startedAt, running);

  if (notFound) {
    return <p className="text-sm">This run no longer exists (the backend was restarted). <Link className="text-accent" href="/">Start a new one</Link>.</p>;
  }

  return (
    <div className="space-y-8">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="font-mono text-lg font-semibold">{state.repoPath ?? "…"}</h1>
          <p className="text-xs text-muted">
            {state.model} · {state.status}{running && ` · ${duration(state.summary?.duration_s ?? elapsed)}`} · {tokens(state.tokens)} tokens
            {connection === "reconnecting" && running && " · reconnecting…"}
          </p>
        </div>
        {running && (
          <button type="button" onClick={() => api.cancel(id)}
                  className="rounded-md border border-border px-3 py-1.5 text-sm hover:border-danger hover:text-danger">
            Cancel
          </button>
        )}
      </header>

      <CoverageMeter percent={state.percent} target={state.target} baseline={state.baseline?.percent} />
      <p className="text-sm text-muted" aria-live="polite">{state.activity}</p>
      {state.removedTests.length > 0 && (
        <p className="text-xs text-muted">Removed {state.removedTests.length} existing test files from the working copy before starting.</p>
      )}

      {state.failure && (
        <section role="alert" className="space-y-2 rounded-md border border-danger p-4">
          <h2 className="font-semibold">Run failed: {state.failure.message}</h2>
          {state.failure.output && <pre className="max-h-64 overflow-auto rounded bg-surface p-2 font-mono text-xs">{state.failure.output}</pre>}
        </section>
      )}

      {state.summary && (
        <>
          <SummaryCard summary={state.summary} jobId={id} />
          <section className="space-y-3">
            <h2 className="text-sm font-medium">Coverage by iteration</h2>
            <CoverageChart history={state.history} target={state.target} />
          </section>
          {state.summary.suspected_bugs.length > 0 && (
            <section className="space-y-2">
              <h2 className="text-sm font-medium">Possible bugs found</h2>
              <ul className="list-disc pl-5 text-sm">
                {state.summary.suspected_bugs.map((b, i) => <li key={i}><span className="font-mono">{b.function}</span>: {b.description}</li>)}
              </ul>
            </section>
          )}
          <section className="space-y-3">
            <h2 className="text-sm font-medium">Generated tests</h2>
            <TestFiles jobId={id} files={state.summary.test_files} />
          </section>
          <section className="space-y-3">
            <h2 className="text-sm font-medium">Coverage by file</h2>
            <FileTable rows={state.summary.per_file} />
          </section>
        </>
      )}

      <section className="space-y-3">
        <h2 className="text-sm font-medium">Activity</h2>
        <Timeline iterations={state.iterations} />
      </section>
    </div>
  );
}
```

- [ ] **Step 6: Verify end to end in the browser**

Run `docker compose up --build`, start a run on `stats` from `/`, and confirm:
- The meter, activity line and timeline update live.
- Rate-limit waits show as an activity message.
- Refreshing mid-run restores the full timeline with no duplicates (Review Focus #4).
- Cancel stops the run within a few seconds and shows "Cancelled".
- On completion: summary, chart, test files with highlighting, and the per-file table render.
- A 390px viewport has no horizontal page scroll.

Take screenshots with the Playwright plugin (`/` and a finished `/jobs/<id>`) and save them to `docs/screenshots/`.

- [ ] **Step 7: Commit**

```bash
git add frontend docs/screenshots
git commit -m "feat(frontend): live run and results page"
```

---

### Task 21: README, AI disclosure, fresh-clone verification

**Files:**
- Create: `README.md`
- Modify: the AI-disclosure header line in every source file (make each one accurate)
- Copy: `docs/superpowers/specs/…design.md` and `docs/superpowers/plans/…md` are already in the repo (keep them)

- [ ] **Step 1: Write `README.md`** with these sections, in this order. Fill the measured values from Task 17/20 runs.

````markdown
# go-coverage-agent

An autonomous agent that raises unit-test coverage for Go repositories. Give it a local Go module and a target
percentage. It measures coverage, plans what to test, asks an LLM to write idiomatic Go tests, compiles and runs
them, keeps only the tests that pass and add coverage, and repeats until it hits the target or gains flatten out.

![Results page](docs/screenshots/results.png)

## Quick start

Requirements: Docker (Desktop) with Compose v2.24+, and a free Groq API key from https://console.groq.com/keys.

```bash
git clone <this repo> && cd go-coverage-agent
cp .env.example .env          # then paste your key into GROQ_API_KEY
docker compose up --build
```

Open http://localhost:3000 → **Use sample repo (montanaflynn/stats)** → **Start**.

The required model is **`openai/gpt-oss-120b` on Groq** (fallback: `openai/gpt-oss-20b`, set `GROQ_MODEL` in `.env`).

### What to expect
- A run on `stats` to 80% took **<measured duration>** and **<measured tokens>** tokens in our tests.
- Groq's free tier allows about 8K tokens/minute and 200K/day. The UI shows "waiting for rate limit" when it pauses. That's normal. Plan on **one full run per key per day**. Accepted tests are always saved, even if a run stops early.

## Using your own repository
Put the Go module under `./repos/<name>` (or set `HOST_REPOS_DIR` in `.env` to an **absolute** path whose subfolders are Go modules, e.g. `/Users/you/code`), restart, and pick it in the UI. Your repository is never modified: the agent works on a copy, and the generated tests are written to `./output/<job-id>/tests/`.

## How it works
<architecture diagram from spec §3, and the loop from spec §7.1 in 6 bullet points>

## Results on montanaflynn/stats
| Target | Final coverage | Tests added | Duration | Tokens | Stop reason |
|---|---|---|---|---|---|
| 80% | <measured> | <measured> | <measured> | <measured> | <measured> |

Independent check: the generated tests were copied into a fresh clone with all `_test.go` removed; `go vet` was clean and `go test -cover` reported <measured>%.

## Configuration
<table of options from spec §7.4 and env vars from .env.example>

## Running the tests
```bash
make test            # everything (Go helper, backend unit + integration in Docker, frontend)
make test-go
make test-backend
make test-integration
make test-frontend
```

## Design decisions and trade-offs
- Deterministic loop, LLM only for writing and fixing tests (structured JSON output, no tool calls). Why: reliability, token cost, testability, safety.
- Append-only test generation through a small Go AST helper. Accepted tests can't be lost, and failing tests are pruned one by one.
- The container is the sandbox: non-root, scrubbed env (the API key is invisible to tests), import allowlist, timeouts with process-group kill, loopback-only ports. No Docker socket mount.
- Groq only: fast iterations; the cost is that reviewers need a key and free-tier limits shape run time.

## Limitations
- Expected values for floating-point code are partly characterization tests: when a generated assertion fails, the fixer may adopt the observed value if it's plausible. Real bugs are reported under "Possible bugs found" rather than silently encoded.
- Generated tests run inside the backend container and could read files there. A production version would run each job in its own sandbox (gVisor/Firecracker) with no network.
- The repository's source code is sent to Groq.
- Jobs are in memory. Restarting the backend forgets the job list, but `./output` keeps all artifacts.

## AI usage
<Write honestly: what you used Claude Code for (design discussion, spec and plan drafting, code drafts per module), what you decided and verified yourself (architecture choices, reviews, every test run, the end-to-end verification), and point to docs/superpowers/ for the full design trail. Each source file starts with a one-line comment saying how it was produced.>
````

The `<…>` markers are values you measure or write yourself. They aren't optional. Replace every one before submitting.

- [ ] **Step 2: Make the AI-disclosure headers accurate**

Run: `git grep -L "AI-assisted\|Human-written" -- '*.py' '*.go' '*.ts' '*.tsx' '*.yml' 'Dockerfile' ':!frontend/next-env.d.ts' ':!**/__init__.py' ':!backend/tests/fixtures/**'`
Expected: no output. Test files, `fakes.py`, `conftest.py`, `vitest.config.ts` and config files were shown without the header in this plan, so add the one-line header to each now (tests count as code you're disclosing too). For files you substantially wrote or rewrote yourself, change the header to `Human-written` (or `AI-assisted: … heavily modified by <author>`).

- [ ] **Step 3: Run every test suite**

Run: `make test`
Expected: Go helper ok; backend unit all pass; backend integration all pass; frontend all pass.

- [ ] **Step 4: Fresh-clone verification (what the reviewers will do)**

```bash
cd "$(mktemp -d)"
git clone <your public repo URL> app && cd app
cp .env.example .env && sed -i 's/^GROQ_API_KEY=.*/GROQ_API_KEY=<your key>/' .env
docker compose up --build
```
Then follow the README word for word in a browser. Fix the README for every place you had to deviate. Also check `docker compose up` without a `.env`: the UI must show the setup banner, not crash.

- [ ] **Step 5: Commit**

```bash
git add README.md docs
git commit -m "docs: README, results and AI usage disclosure"
```

---

### Task 22 (stretch): Continuous integration

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Write the workflow**

```yaml
# AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
name: ci
on: [push, pull_request]
jobs:
  gohelper:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-go@v5
        with: { go-version: stable }
      - run: go vet ./... && go test ./...
        working-directory: tools/gohelper
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: docker build -f backend/Dockerfile --build-arg GO_IMAGE=golang:$(cat .go-version) -t gca-backend .
      - run: docker run --rm gca-backend uv run --no-sync pytest
      - run: docker run --rm gca-backend uv run --no-sync pytest -m integration
  frontend:
    runs-on: ubuntu-latest
    defaults: { run: { working-directory: frontend } }
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 22, cache: npm, cache-dependency-path: frontend/package-lock.json }
      - run: npm ci
      - run: npm test
      - run: npm run build
```

- [ ] **Step 2: Push and confirm all three jobs pass on GitHub.** Add the CI badge to the README.

- [ ] **Step 3: Commit**

```bash
git add .github README.md
git commit -m "ci: run Go, backend and frontend test suites"
```
