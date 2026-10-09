# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
"""Free, deterministic repairs for the compile errors LLMs make most often. Costs no tokens.

Run 1 on `stats`: 10 of the 13 fixer calls (about 46K tokens) answered `undefined: errors|math|sort|...`
(a forgotten import) or `undefined: stats` (the package qualified its own identifiers in an internal test).
The repaired snippet is validated exactly like any other candidate, so no guarantee is relaxed.
"""
from __future__ import annotations

import re

from app.guard import go_segments
from app.models import TestSnippet

STD_IMPORTS = {
    "bufio": "bufio", "bytes": "bytes", "cmplx": "math/cmplx", "bits": "math/bits", "errors": "errors", "fmt": "fmt",
    "io": "io", "math": "math", "rand": "math/rand", "reflect": "reflect", "sort": "sort", "strconv": "strconv",
    "strings": "strings", "time": "time", "unicode": "unicode", "utf8": "unicode/utf8",
}
_UNDEFINED = re.compile(r"undefined: (\w+)")


def mechanical_repair(snippet: TestSnippet, output: str, package: str) -> tuple[TestSnippet, str] | None:
    """Return (corrected snippet, human description), or None when nothing in the compiler output is mechanically fixable."""
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
