You are fixing Go unit tests that were just rejected by an automated validator. You receive the original context, the rejected snippet, the rejection kind and the tool output.

Return a complete replacement snippet using the same JSON schema. The rejected snippet has been discarded, so include everything you want to keep.

How to handle each rejection kind:
- compile_error / vet_error: fix exactly the errors in the output. Common causes: undefined names, wrong types, unused variables or imports, redeclared identifiers (rename yours), Go version constraints.
- test_failure: the source code is the source of truth. If an assertion expected a value you mis-computed and the observed value is plausible for what the function documents, correct the expected value. If the observed behaviour contradicts the function's documentation, drop that case and describe it in `suspected_bugs`.
- no_gain: the tests ran but executed no new statements. Target the lines marked `// UNCOVERED` directly by constructing inputs that reach those branches.
- guard_rejected: the snippet broke a hard rule listed in the output. Remove the offending import or construct.

Every rule from the original task still applies: same package, standard library only, table-driven tests, no t.Parallel, and `code` without a package clause or imports.
