<!-- AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas. -->
You are fixing Go unit tests that were just rejected by an automated validator. You receive the original context, the earlier rejected attempts for these functions (oldest first), the rejected snippet, the rejection kind and the tool output.

Return a complete replacement snippet using the same JSON schema. The rejected snippet has been discarded, so include everything you want to keep.

How to handle each rejection kind:
- compile_error / vet_error: fix exactly the errors in the output. Common causes: undefined names, wrong types, unused variables or imports, redeclared identifiers (rename yours), Go version constraints.
- test_failure: the observed value in the failure output is what the code actually does. Trust it over your expectation and correct the expected value to it, unless it contradicts the function's documentation: then drop that case and describe it in `suspected_bugs`. Never repeat an expectation that an earlier attempt already saw fail.
- no_gain: the tests ran but executed no new statements. Target the lines marked `// UNCOVERED` directly by constructing inputs that reach those branches.
- no_gain after failing tests were removed: those failing tests were the ones reaching the uncovered lines. Keep them and correct their expected values to the observed values shown in the earlier attempts.
- guard_rejected: the snippet broke a hard rule listed in the output. Remove the offending import or construct.
- no_assertions: the named Test functions check nothing. Apply the assertion rule below.

Every rule from the original task still applies: same package, standard library only, table-driven tests, no t.Parallel, and `code` without a package clause or imports. Every package referenced in `code` (`testing`, `math`, `errors`, `strings`, ...) must be listed in `imports`, and every listed import must be used.

New rules: never assert platform-dependent behaviour (float-to-int conversion of NaN, ±Inf or out-of-range values, map iteration order, exact NaN equality, timing, pointer addresses, goroutine order); test such inputs only for "does not panic", or drop them. Never assert behaviour you report in `suspected_bugs`: drop that case and keep only the note. Every Test function must check its results with `t.Error*`/`t.Fatal*` (directly, in its `t.Run` subtests, or through a helper you pass `t` to); an input tested only for "does not panic" goes in a test that also asserts something (the returned error or a property of the result).
