# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
"""Free, deterministic repairs for the compile errors LLMs make most often. Costs no tokens.

Run 1 on `stats`: 10 of the 13 fixer calls (about 46K tokens) answered `undefined: errors|math|sort|...`
(a forgotten import) or `undefined: stats` (the package qualified its own identifiers in an internal test).
Run on `semver` (job acab3e3c7570): the Writer reused test names accepted in an earlier iteration
(`gohelper: duplicate declaration: TestConstraintCaret_Uncovered`); such a test is renamed to the first free `_2`, `_3`, ...
The repaired snippet is validated exactly like any other candidate, so no guarantee is relaxed.
"""
from __future__ import annotations

import re
from collections.abc import Iterable

from app.guard import go_segments
from app.models import TestSnippet

STD_IMPORTS = {
    "bufio": "bufio", "bytes": "bytes", "cmplx": "math/cmplx", "bits": "math/bits", "errors": "errors", "fmt": "fmt",
    "io": "io", "math": "math", "rand": "math/rand", "reflect": "reflect", "sort": "sort", "strconv": "strconv",
    "strings": "strings", "time": "time", "unicode": "unicode", "utf8": "unicode/utf8",
}
_UNDEFINED = re.compile(r"undefined: (\w+)")
_DUPLICATE = re.compile(r"duplicate declaration: (\w+)")
# Names `go test` runs as tests: the prefix alone, or followed by a non-lowercase character (so not `Testable`).
# Examples are left to the Fixer: `ExampleX_2` is a malformed example name for go vet, and an Example without
# `// Output:` is never run, so it adds no coverage.
_TEST_FUNC = re.compile(r"(?:Test|Benchmark|Fuzz)(?:[A-Z0-9_]\w*)?")
_WORD = re.compile(r"\w+")


def _rename_duplicate_test(code: str, name: str, taken: Iterable[str]) -> tuple[str, str] | None:
    """Rename the snippet's own `func <name>(` to the first free `<name>_N`, or None when that is not safe to do mechanically."""
    decl = re.compile(rf"^func {re.escape(name)}(?=\()", re.M)
    if not _TEST_FUNC.fullmatch(name) or len(decl.findall(code)) != 1:
        return None
    code_only = "".join(text if blank is None else blank for text, blank in go_segments(code))
    if len(re.findall(rf"\b{re.escape(name)}\b", code_only)) != 1:  # referenced elsewhere: leave it to the Fixer
        return None
    used = set(taken) | set(_WORD.findall(code))
    n = 2
    while f"{name}_{n}" in used:
        n += 1
    return decl.sub(f"func {name}_{n}", code), f"{name}_{n}"


_COSMETIC = " \t\r\n\"'`\\"  # whitespace, quotes and backslashes the model leaves around an import path


def clean_imports(snippet: TestSnippet) -> tuple[TestSnippet, str] | None:
    """Strip whitespace, quotes and backslashes from both ends of each import path, or None when none had any.

    Job 86b6d88b558c: the Writer's `imports` held `testing\\` (a stray backslash from JSON escaping) and the guard
    rejected the candidate. Only the ends are touched, so a path's identity never changes and an invalid path
    is still rejected by the guard; a path made only of such characters is left for the guard to reject."""
    imports, notes = [], []
    for imp in snippet.imports:
        cleaned = imp.strip(_COSMETIC) or imp
        if cleaned != imp:
            notes.append(f"cleaned import path '{imp}' → '{cleaned}'")
        imports.append(cleaned)
    if not notes:
        return None
    return snippet.model_copy(update={"imports": imports}), "; ".join(notes)


def mechanical_repair(snippet: TestSnippet, output: str, package: str,
                      taken: Iterable[str] = ()) -> tuple[TestSnippet, str] | None:
    """Return (corrected snippet, human description), or None when nothing in the compiler output is mechanically fixable.

    `taken` are the names already declared in the package's test files (a renamed test must not collide with them)."""
    for name in _DUPLICATE.findall(output):
        renamed = _rename_duplicate_test(snippet.code, name, taken)
        if renamed is not None:
            return snippet.model_copy(update={"code": renamed[0]}), f"renamed duplicate test {name} to {renamed[1]}"
    names = set(_UNDEFINED.findall(output))
    imports, code = list(snippet.imports), snippet.code
    notes: list[str] = []
    for name in sorted(names):
        path = STD_IMPORTS.get(name)
        if path and path not in imports and name != package:
            imports.append(path)
    added = imports[len(snippet.imports):]
    if added:
        notes.append(f"added import{'s' if len(added) > 1 else ''} {', '.join(added)}")
    if package in names:
        qualifier = re.compile(rf"(?<![\w.]){re.escape(package)}\.(?=[A-Za-z_])")
        # only code tokens: comments and string/rune literals are left untouched
        code = "".join(qualifier.sub("", text) if blank is None else text for text, blank in go_segments(code))
        if code != snippet.code:
            notes.append(f"removed the `{package}.` qualifier")
    if imports == snippet.imports and code == snippet.code:
        return None
    return snippet.model_copy(update={"imports": imports, "code": code}), "; ".join(notes)
