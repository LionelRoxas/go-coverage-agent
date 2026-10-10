<!-- AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas. -->
# Detailed results

Every measured run behind the [README](../README.md): the comparisons that set the defaults, and the issues I found in testing and fixed. For the two runs you can re-measure yourself, see [evidence](evidence).

All on a Developer-plan Groq key, each repo's own tests deleted first. Default options (20 rounds, min gain 1.0, 3 targets per round) unless noted.

## montanaflynn/stats

| Run | Goal | Coverage | Rounds / time | Targets kept / rejected | Tokens | Stop reason |
|---|---|---|---|---|---|---|
| `89eb53b5907e` | 80% | 0.0% → 80.51% (1,247 statements) | 15 / 287 s | 41 / 4 | 184,926 | `target_reached` |
| `26598ee5c57b` (after the fixes below) | 80% | 0.0% → 80.75% | 12 / 248 s | 34 / 1 | 182,494 | `target_reached` |
| `f910d155f3cd` | 100% | 0.0% → 97.83% | 20 / 474 s | 60 / 0 | 337,689 | `max_iterations` |
| `0e1f8bf7442a` (up to 30 rounds, min gain 0.5) | 100% | 0.0% → 100.0% | 22 / 612 s | 64 / 1 | 403,322 | `target_reached` |

Independent check: the tests of `89eb53b5907e` were copied into a fresh clone with every `_test.go` removed; `go vet` was clean, all tests passed and plain Go measured **80.5%** (the same check on `ca1beb9a1fdb` gave 80.1%).

## Masterminds/semver

Goal 80%. It starts at 1.4%, not 0%, because its two `init()` functions run when the package loads.

| Run | Setup | Coverage | Rounds / time | Targets kept / rejected | Tokens |
|---|---|---|---|---|---|
| `acab3e3c7570` | before the prompt-budget and duplicate-name fixes | 1.4% → 64.2% (`marginal_gains`) | 8 / 130 s | 12 / 5 | 115.9K |
| `f9f3edcd9bfc` | after those fixes, one `low` effort for both roles | 1.4% → 80.1% | 4 / 75 s | 9 / 0 | 59.0K |
| `736baa413b5d` | after the Fixer-history fixes, Fixer `medium` | 1.4% → **84.6%** | 4 / 114 s | 8 / 0 | 82.6K |
| `d247037efdb2` | same, Fixer `low` | 1.4% → **84.4%** | 3 / 88 s | 7 / 0 | 69.2K |

The last two runs needed one LLM fix each (12.8 s at `medium`, 9.6 s at `low`), too close to rank the Fixer's effort. A `high` Fixer call was still waiting after about 114 s, so both roles default to `medium`.

## Cap of 5 functions per target

(same settings, only the planner's cap changed from 8 to 5):

| | semver, cap 8 | semver, cap 5 | stats, cap 8 | stats, cap 5 |
|---|---|---|---|---|
| Run | `736baa413b5d` | `7a8c53c08bce` | `459dfe48a57f` | `e2de1ca387cb` |
| Coverage | 1.4% → 84.6% | 1.4% → 83.5% | 0% → 80.3% | 0% → 81.1% |
| Rounds / time | 4 / 114 s | 3 / 83 s | 10 / 276 s | 11 / 310 s |
| Passed on the first check | 2 of 8 (25%) | 4 of 7 (57%) | 23 of 28 (82%) | 27 of 31 (87%) |
| LLM fixes | 1 | 0 | 3 | 1 |
| Tokens | 82.6K | 54.5K | 172K | 175K |

With the cap of 5 more targets passed on the first check and fewer LLM fixes were needed; semver used 34% fewer tokens, stats about the same. Single runs: a few seconds or a point is within normal variation.

## Parallel writers

(stats, cap of 5; within each comparison only `PARALLEL_WRITERS` changed).

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

## Issues I found in testing and fixed

I had the system run end to end (Claude ran the live runs I approved), read the results, spotted these problems and decided the fixes. Claude Code implemented them under review.

| Symptom | Root cause | Fix | Evidence |
|---|---|---|---|
| Malformed-JSON errors from Groq (400 `json_validate_failed`) | The output cap left too little room after hidden reasoning tokens | Output allowance is the model maximum (65,536), clamped to the key's tokens/min limit | No JSON errors in later runs |
| A run took about 28 minutes and stopped at 69% | A free-trial key (8K tokens/min, 200K/day) | Developer-plan key; free-tier settings documented in `.env.example` | `a46c5a902f70`: 1,678 s, 68.97%, 46 rate-limit events; `89eb53b5907e`: 287 s, 80.51% |
| Model errors, `norm.go` stuck at 32.7% | Targets of 12 to 37 functions asked for answers too large to finish | Cap targets at 5 functions / 100 statements; split an over-size answer and retry | `ca1beb9a1fdb` → `26598ee5c57b`: 4 model errors → 0, `norm.go` 32.74% → 90.27% |
| `make test` failed in PowerShell | The Makefile used `cat` and `VAR=x cmd` | Shell-independent Makefile | Passes in PowerShell, Git Bash and CI |
| No theme switch, no way back to the start page, a one-line running banner, no explanation of the loop | UI gaps | Theme toggle, Run history panel, "← All runs", How it works page | Screenshots in the README |
| semver stalled at 64.2% (prompt too large for the Fixer, duplicate test names) | A prompt cap from the free-trial era; existing test names crowded out | `MAX_PROMPT_TOKENS` 4,500 → 12,000; Fixer prompts shrink instead of failing; reused names renamed without an LLM call | `acab3e3c7570` 64.2% → `f9f3edcd9bfc` 80.1% |
| The Fixer kept repeating a wrong assertion (semver `constraints.go`, rejected after 6 attempts) | The Fixer saw only the latest check; effort was at its minimum | Five changes, listed under [AI usage](../README.md#decisions-i-made-during-the-build) | `736baa413b5d`: 84.6%, 0 rejected |
| A generated test asserted NaN/Inf-to-int results that differ between x86 and ARM, so it would fail on Apple Silicon | Go leaves out-of-range float-to-int conversion implementation-defined; the same test also locked in a behaviour the model had flagged as a suspected bug | Writer and Fixer prompt rules (no platform-dependent or suspected-bug assertions) plus a guard check that rejects `int(math.Inf(`, `int64(math.NaN())` and similar | Run `7e5223daa8e2`, `util_test.go`; re-run `73d630a6dd05` (same settings, goal 100%): 0% → 99.68%; NaN/Inf are now tested only for "does not panic", and the guard never had to fire |
