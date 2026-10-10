# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
"""Builds the compact, budgeted prompt context for one plan item. Deterministic and LLM-free."""
from __future__ import annotations

import posixpath
import re
from dataclasses import dataclass
from typing import Any

from app.gotools import GoPackage, Symbol
from app.llm.client import estimate_tokens
from app.models import CoverageReport, FuncInfo, FuncKey, PlanItem
from app.workspace import Workspace, test_path_for

_IDENT = re.compile(r"\b[A-Za-z_]\w*\b")
_SIGNATURE = re.compile(r"^(func \w+\([^)]*\)[^{\n]*)", re.M)
# Delimiters around repository-derived text in prompts: it is data from the repository under test, and the prompts
# tell the model never to follow instructions found inside it (code comments included).
REPO_SOURCE, TEST_OUTPUT = "repository_source", "test_output"


def defuse(tag: str, text: str) -> str:
    """`text` with any `</tag>` of its own made harmless (`<\\/tag>`), so the data cannot end its block early."""
    return re.sub(rf"</(\s*{tag}\s*)>", r"<\\/\1>", text, flags=re.I)


def data_block(tag: str, text: str) -> str:
    """Repository-derived `text` between a `<tag>` line and a `</tag>` line."""
    return f"<{tag}>\n{defuse(tag, text)}\n</{tag}>"


class ContextTooLarge(Exception):
    pass


@dataclass
class ContextInputs:
    module: str
    package: str
    go_version: str
    source_file: str
    test_file: str
    targets: list[tuple[str, str]]
    declared: list[str]
    referenced: list[str]
    existing_tests: list[str]


def go_version_rules(version: str) -> list[str]:
    parts = (version.split(".") + ["0"])[:2]
    minor = int(re.sub(r"\D.*", "", parts[1]) or 0)
    rules = ["Use only the Go standard library; never change go.mod."]
    if minor < 18:
        rules.append("No generics (type parameters) and no `any` alias; use interface{} if needed.")
    if minor < 21:
        rules.append("Do not use the `slices`, `maps` or `cmp` packages or the `min`/`max`/`clear` builtins.")
    if minor < 22:
        rules.append("Range loop variables are shared across iterations: copy them first (`tc := tc`) before using them in a closure.")
    rules.append("Do not call t.Parallel().")
    return rules


def annotate_source(lines: list[str], start: int, end: int, uncovered: list[tuple[int, int]]) -> str:
    first = start
    while first > 1 and lines[first - 2].lstrip().startswith("//"):
        first -= 1
    out = []
    for n in range(first, end + 1):
        text = lines[n - 1]
        if n >= start and any(a <= n <= b for a, b in uncovered):
            text += "  // UNCOVERED"
        out.append(text)
    return "\n".join(out)


def test_signatures(src: str | None) -> list[str]:
    return [m.group(1).strip() for m in _SIGNATURE.finditer(src or "")]


test_signatures.__test__ = False


def _header(inp: ContextInputs) -> str:
    rules = "\n".join(f"- {r}" for r in go_version_rules(inp.go_version))
    return (f"## Module\nmodule: {inp.module}\npackage: {inp.package} (write tests in `package {inp.package}`)\n"
            f"test file: {inp.test_file}\nGo language version: {inp.go_version}\nConstraints:\n{rules}")


def _declared(inp: ContextInputs) -> str:
    names = ", ".join(inp.declared) if inp.declared else "(none)"
    return f"## Names already declared in this package's tests (never redeclare these)\n{names}"


def _targets(inp: ContextInputs) -> str:
    blocks = [f"### {label} ({inp.source_file})\n```go\n{src}\n```" for label, src in inp.targets]
    return ("## Functions to test (lines ending in `// UNCOVERED` are not executed by any test yet)\n"
            + data_block(REPO_SOURCE, "\n\n".join(blocks)))


def _fit(text: str, title: str, items: list[str], budget: int, prefix: str = "", suffix: str = "") -> str:
    kept: list[str] = []
    for item in items:
        candidate = f"{text}\n\n{title}\n{prefix}" + "\n".join(kept + [item]) + suffix
        if estimate_tokens(candidate) > budget:
            break
        kept.append(item)
    if not kept:
        return text
    return f"{text}\n\n{title}\n{prefix}" + "\n".join(kept) + suffix


def render_context(inp: ContextInputs, budget_tokens: int) -> str:
    text = "\n\n".join([_header(inp), _declared(inp), _targets(inp)])
    if estimate_tokens(text) > budget_tokens:
        raise ContextTooLarge(f"targets need ~{estimate_tokens(text)} tokens; budget is {budget_tokens}")
    # Existing test names go before the optional related declarations so they are not crowded out;
    # when only some fit, the most recent (last in the file) are kept.
    # Repository-derived sections sit in <repository_source> blocks; _fit counts the delimiters toward the budget.
    text = _fit(text, f"## Tests already in {inp.test_file} (signatures only; do not duplicate)",
                [defuse(REPO_SOURCE, f"- {s}") for s in reversed(inp.existing_tests)], budget_tokens,
                f"<{REPO_SOURCE}>\n", f"\n</{REPO_SOURCE}>")
    text = _fit(text, "## Related declarations in this package", [defuse(REPO_SOURCE, r) for r in inp.referenced],
                budget_tokens, f"<{REPO_SOURCE}>\n```go\n", f"\n```\n</{REPO_SOURCE}>")
    return text


class ContextProvider:
    def __init__(self, ws: Workspace, tools: Any, funcs: list[FuncInfo], symbols: list[Symbol],
                 module: str, go_version: str, packages: dict[str, GoPackage]):
        self.ws, self.tools, self.module, self.go_version, self.packages = ws, tools, module, go_version, packages
        self.funcs: dict[FuncKey, FuncInfo] = {f.key: f for f in funcs}
        self.symbols = symbols
        self._lines: dict[str, list[str]] = {}

    def _file_lines(self, rel: str) -> list[str]:
        if rel not in self._lines:
            self._lines[rel] = (self.ws.read(rel) or "").splitlines()
        return self._lines[rel]

    async def inputs_for(self, item: PlanItem, report: CoverageReport) -> ContextInputs:
        rel_dir = posixpath.dirname(item.file) or "."
        coverage = {fc.key: fc for fc in report.functions}
        lines = self._file_lines(item.file)
        targets = []
        for key in item.functions:
            info = self.funcs[key]
            uncovered = coverage[key].uncovered_lines if key in coverage else []
            targets.append((key.label(), annotate_source(lines, info.start_line, info.end_line, uncovered)))
        target_text = "\n".join(src for _, src in targets)
        idents = set(_IDENT.findall(target_text)) - {k.name for k in item.functions}
        referenced, seen = [], set()
        for sym in self.symbols:
            if sym.name in idents and (posixpath.dirname(sym.file) or ".") == rel_dir and (sym.file, sym.start_line) not in seen:
                seen.add((sym.file, sym.start_line))
                referenced.append("\n".join(self._file_lines(sym.file)[sym.start_line - 1:sym.end_line]).strip())
        test_file = test_path_for(item.file)
        return ContextInputs(
            module=self.module, package=self.packages[rel_dir].name, go_version=self.go_version,
            source_file=item.file, test_file=test_file, targets=targets,
            declared=await self.tools.decls(rel_dir), referenced=referenced,
            existing_tests=test_signatures(self.ws.read(test_file)),
        )
