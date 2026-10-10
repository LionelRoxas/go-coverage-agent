<!-- AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas. -->
# Evidence: generated tests for montanaflynn/stats

The brief's evaluation repo is [montanaflynn/stats](https://github.com/montanaflynn/stats). Each folder here holds the
test files one real run generated (exactly as exported to `output/<run>/tests`, unedited) and that run's
`report.json`, so anyone can inspect the tests and re-measure them without running the app or calling an LLM.

| Folder | Run | Setting | Tests / test files | Reported by the app | Re-measured by `scripts/verify-evidence.sh` |
|---|---|---|---|---|---|
| [`stats-e2de1ca387cb`](stats-e2de1ca387cb) | `e2de1ca387cb` | sequential writers, goal 80%, default options (20 rounds, min gain 1.0, 3 targets per round, 2 fix attempts) | 109 / 29 | 0% → 81.07% (`target_reached`, 11 rounds, 310 s, 175,023 tokens) | **81.07%** (1,011 of 1,247 statements) |
| [`stats-73d630a6dd05`](stats-73d630a6dd05) | `73d630a6dd05` | `PARALLEL_WRITERS` on, goal 100%, 30 rounds max, min gain 0.5, 5 targets per round, 3 fix attempts | 224 / 50 | 0% → 99.68% (`marginal_gains`, 17 rounds, 377 s, 505,848 tokens) | **99.68%** (1,243 of 1,247 statements) |

Both runs used `openai/gpt-oss-120b` on Groq with the repo's own tests deleted first. `e2de1ca387cb` is also the
committed backend test fixture (`backend/tests/fixtures/run_e2de1ca387cb`). Re-measured on 2026-10-10 with
`golang:1.27-bookworm`; `go vet ./...` was clean and every test passed in both folders.

## Re-running the check

```sh
make verify-evidence                                         # both folders
scripts/verify-evidence.sh docs/evidence/stats-73d630a6dd05  # one folder
```

Needs Docker and network access; works from Git Bash on Windows and on macOS / Linux. In a plain
`golang:<.go-version>` container (no app code) the script clones montanaflynn/stats at commit
`c2cb6881295ee9249914cce7bcb80dc96ee2f4b2` (the commit the runs used), deletes every `_test.go`, copies the folder's
tests in, runs `go vet ./...` and `go test -count=1 -covermode=set -coverprofile`, and prints the total coverage
(Go's own one-decimal total, then two decimals as the app reports it). Like the app, it measures the module's
packages minus the default exclude patterns (`examples/**`, `testdata/**`); the two `examples/` programs have no
tests.

## What `report.json` contains

The app's final report of the run: per-file coverage before and after, each round, the tests and test files added,
suspected bugs, token counts and duration (`73d630a6dd05` also has its AI summary). Both files were checked before
they were committed: they hold no API keys or other secrets and no absolute host paths (files are named relative to the
module root, and the AI summary names the tests folder as `output/<run>/tests`), so nothing was changed in them.
