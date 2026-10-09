# AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
"""Free, deterministic repairs for the compile errors LLMs make most often. Costs no tokens.

Run 1 on `stats`: 10 of the 13 fixer calls (about 46K tokens) answered `undefined: errors|math|sort|...`
(a forgotten import) or `undefined: stats` (the package qualified its own identifiers in an internal test).
The repaired snippet is validated exactly like any other candidate, so no guarantee is relaxed.
"""
from __future__ import annotations

import re

from app.models import TestSnippet

STD_IMPORTS = {
    "bufio": "bufio", "bytes": "bytes", "cmplx": "math/cmplx", "bits": "math/bits", "errors": "errors", "fmt": "fmt",
    "io": "io", "math": "math", "rand": "math/rand", "reflect": "reflect", "sort": "sort", "strconv": "strconv",
    "strings": "strings", "time": "time", "unicode": "unicode", "utf8": "unicode/utf8",
}
_UNDEFINED = re.compile(r"undefined: (\w+)")


def mechanical_repair(snippet: TestSnippet, output: str, package: str) -> TestSnippet | None:
    """Return a corrected snippet, or None when the compiler output has no mechanically fixable error."""
    names = set(_UNDEFINED.findall(output))
    imports, code = list(snippet.imports), snippet.code
    for name in sorted(names):
        path = STD_IMPORTS.get(name)
        if path and path not in imports and name != package:
            imports.append(path)
    if package in names:
        code = re.sub(rf"(?<![\w.]){re.escape(package)}\.(?=[A-Za-z_])", "", code)
    if imports == snippet.imports and code == snippet.code:
        return None
    return snippet.model_copy(update={"imports": imports, "code": code})
