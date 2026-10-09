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
