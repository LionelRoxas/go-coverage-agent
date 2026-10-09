# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
"""Static checks on LLM-written test code before anything is compiled or executed."""
from __future__ import annotations

import re

from app.models import TestSnippet

DENIED_IMPORTS = {"C", "os/exec", "net", "runtime/cgo", "syscall", "unsafe", "plugin", "runtime/debug"}
_IMPORT_PATH = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_./-]*")
_TEST_FUNC = re.compile(r"^func (Test(?!Main\()[A-Z0-9_]\w*)\(", re.M)
_KEYWORD = re.compile(r"\b(import|package)\b")
_DIRECTIVE = re.compile(r"^\s*//go:", re.M)
_START_PROCESS = re.compile(r"\bStartProcess\b")
_BUILD_TAG = re.compile(r"^\s*//\s*(go:build|\+build)", re.M)


def _is_stdlib(path: str) -> bool:
    return "." not in path.split("/")[0]


def go_segments(code: str) -> list[tuple[str, str | None]]:
    """Split Go source into (text, blank) pieces. `blank` is None for code and the stand-in for comments/literals."""
    out: list[tuple[str, str | None]] = []
    i, n, start = 0, len(code), 0

    def flush(upto: int) -> None:
        if upto > start:
            out.append((code[start:upto], None))

    while i < n:
        if code.startswith("//", i):
            end = code.find(chr(10), i)
            j, blank = (n if end == -1 else end), " "
        elif code.startswith("/*", i):
            end = code.find("*/", i + 2)
            j, blank = (n if end == -1 else end + 2), " "
        elif code[i] in "\"'":
            quote, j = code[i], i + 1
            while j < n and code[j] not in (quote, chr(10)):
                j += 2 if code[j] == "\\" else 1
            blank = quote * 2
            j = j + 1 if j < n and code[j] == quote else j
        elif code[i] == "`":
            end = code.find("`", i + 1)
            j, blank = (n if end == -1 else end + 1), "``"
        else:
            i += 1
            continue
        flush(i)
        out.append((code[i:j], blank))
        i = start = j
    flush(n)
    return out


def _strip_go(code: str) -> str:
    """Blank out comments and literal contents so keyword checks only see code tokens."""
    return "".join(text if blank is None else blank for text, blank in go_segments(code))


def check_snippet(snippet: TestSnippet, module: str, max_bytes: int = 40_000) -> list[str]:
    problems: list[str] = []
    for imp in snippet.imports:
        if not _IMPORT_PATH.fullmatch(imp):
            problems.append(f"invalid import path {imp!r}")
        elif imp in DENIED_IMPORTS or imp.startswith("net/"):
            problems.append(f"import {imp!r} is not allowed in generated tests")
        elif not _is_stdlib(imp) and imp != module and not imp.startswith(module + "/"):
            problems.append(f"import {imp!r} is not in the standard library or this module")
    code = snippet.code
    if _KEYWORD.search(_strip_go(code)):
        problems.append("`code` must not contain a package clause or import declarations; list import paths in `imports`")
    if _START_PROCESS.search(_strip_go(code)):
        problems.append("`StartProcess` is not allowed in generated tests (tests must not start processes)")
    if any("/proc/" in text for text, blank in go_segments(code) if blank is None or not text.startswith(("//", "/*"))):
        problems.append("the path `/proc/` is not allowed in generated tests (tests must not read process state)")
    if _BUILD_TAG.search(code):
        problems.append("build constraints are not allowed")
    if _DIRECTIVE.search(code):
        problems.append("compiler directives (//go:...) are not allowed")
    if "#cgo" in code:
        problems.append("cgo directives are not allowed")
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
