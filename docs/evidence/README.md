<!-- AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas. -->
# Evidence: generated tests for montanaflynn/stats

The brief's evaluation repo is [montanaflynn/stats](https://github.com/montanaflynn/stats). Each folder here holds the
test files one real run generated (exactly as exported to `output/<run>/tests`, unedited) and that run's
`report.json`, so anyone can inspect the tests and re-measure them without running the app or calling an LLM.

Both runs were produced by the submitted code (commit `28f9c5f`), with every check described in the README in place:
the guard, the assertion check, `go vet`, tests passing twice and strictly growing coverage.

| Folder | Run | Setting | Tests / test files | Reported by the app | Re-measured by `scripts/verify-evidence.sh` |
|---|---|---|---|---|---|
| [`stats-8c38d392ecaf`](stats-8c38d392ecaf) | `8c38d392ecaf` | `PARALLEL_WRITERS` on, goal 80%, default options (20 rounds, min gain 1.0, 3 targets per round, 2 fix attempts) | 134 / 28 | 0% → 81.15% (`target_reached`, 10 rounds, 146 s, 205,424 tokens; 30 targets accepted, 0 rejected) | **81.15%** (1,012 of 1,247 statements) |
| [`stats-befcbd2b6ada`](stats-befcbd2b6ada) | `befcbd2b6ada` | `PARALLEL_WRITERS` on, goal 100%, 30 rounds max, min gain 0.5, 5 targets per round, 3 fix attempts | 229 / 50 | 0% → 100.0% (`target_reached`, 17 rounds, 332 s, 480,774 tokens; 75 accepted, 1 rejected) | **100.00%** (1,247 of 1,247 statements) |

Both runs used `openai/gpt-oss-120b` on Groq (Writer and Fixer at `medium` effort) with the repo's own tests deleted
first. Re-measured on 2026-10-10 with `golang:1.27-bookworm`; `go vet ./...` was clean and every test passed in both
folders.

**Mutation score** (the app's **Run mutation test**, a seeded sample of 60 operator swaps in covered code, each re-tested with its package's tests): `8c38d392ecaf` **71.7%** (43 caught, 17 missed), `befcbd2b6ada` **75.0%** (45 caught, 15 missed). Each mutant and its result is in `report.json` under `mutation`; most missed ones are in `norm.go` and `ttest.go`, where tests check properties rather than exact values.

The 100% run reported two suspected bugs, and neither is locked in by a test: `Sigmoid`'s doc comment says the output
range is -1 to 1 while the code (correctly) returns values in (0, 1), and the tests assert the mathematical values;
`NormSample` is tested only for properties (length, and a constant output when the scale is 0).

## Re-running the check

```sh
make verify-evidence                                         # both folders
scripts/verify-evidence.sh docs/evidence/stats-befcbd2b6ada  # one folder
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
suspected bugs, prediction disagreements, token counts, duration and the mutation test result. Both files were checked before they were
committed: they hold no API keys or other secrets and no absolute host paths, so nothing was changed in them.
