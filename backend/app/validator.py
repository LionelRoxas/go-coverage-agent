# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
"""Decides whether a candidate test snippet is kept: guard → merge → compile → vet → test → coverage."""
from __future__ import annotations

import posixpath
import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.coverage import parse_profile, summarize
from app.gotools import CommandResult, GoPackage, timeout_message
from app.guard import check_snippet, render_snippet, test_names
from app.models import CoverageReport, FuncInfo, TestSnippet
from app.workspace import Workspace

_FAIL = re.compile(r"^\s*--- FAIL: (\S+)", re.M)
_TOP_DECL = re.compile(r"^(?:func\s+(?:\([^)]*\)\s*)?|type\s+|var\s+|const\s+)(\w+)")


class ValidationKind(StrEnum):
    ACCEPTED = "accepted"
    COMPILE_ERROR = "compile_error"
    VET_ERROR = "vet_error"
    TEST_FAILURE = "test_failure"
    NO_GAIN = "no_gain"
    GUARD_REJECTED = "guard_rejected"
    LLM_ERROR = "llm_error"
    LLM_TIMEOUT = "llm_timeout"  # Groq did not answer within GROQ_TIMEOUT_S
    LLM_UNAVAILABLE = "llm_unavailable"  # Groq unreachable (connection errors / 5xx) after the network retries
    PROMPT_TOO_LARGE = "prompt_too_large"  # the prompt could not fit MAX_PROMPT_TOKENS; no model call was made


@dataclass
class ValidationResult:
    kind: ValidationKind
    output: str = ""
    failed_tests: list[str] = field(default_factory=list)
    report: CoverageReport | None = None
    new_tests: list[str] = field(default_factory=list)
    error_decls: list[str] = field(default_factory=list)  # top-level declarations that compile/vet error lines point at

    @property
    def accepted(self) -> bool:
        return self.kind is ValidationKind.ACCEPTED

    def event(self) -> dict[str, Any]:
        return {"kind": self.kind.value, "output": self.output[:4000], "failed_tests": self.failed_tests}


@dataclass
class Measurement:
    result: CommandResult
    report: CoverageReport | None


def parse_failed_tests(output: str) -> list[str]:
    names: list[str] = []
    for m in _FAIL.finditer(output):
        top = m.group(1).split("/")[0]
        if top not in names:
            names.append(top)
    return names


def error_lines(output: str, filename: str) -> list[int]:
    """Line numbers of `<filename>:<line>:` positions in tool output (any directory prefix, not a longer file name)."""
    return [int(n) for n in re.findall(rf"(?:^|[\s/(]){re.escape(filename)}:(\d+):", output, re.M)]


def decls_at(src: str, lines: list[int]) -> list[str]:
    """Names of the top-level declarations enclosing the given 1-based lines of `src`, in first-mention order."""
    starts = [(n, m.group(1)) for n, text in enumerate(src.split("\n"), 1) if (m := _TOP_DECL.match(text))]  # Go counts only \n
    names: list[str] = []
    for line in lines:
        enclosing = [name for start, name in starts if start <= line]
        if enclosing and enclosing[-1] not in names:
            names.append(enclosing[-1])
    return names


class Validator:
    def __init__(self, ws: Workspace, tools: Any, packages: list[GoPackage], funcs: list[FuncInfo], module: str):
        self.ws, self.tools, self.packages, self.funcs, self.module = ws, tools, packages, funcs, module

    async def measure(self) -> Measurement:
        profile = self.ws.scratch / "cover.out"
        profile.unlink(missing_ok=True)
        r = await self.tools.test(self.packages, profile)
        if r.exit_code != 0 or r.timed_out or not profile.exists():
            return Measurement(r, None)
        return Measurement(r, summarize(parse_profile(profile.read_text(encoding="utf-8"), self.module), self.funcs))

    async def validate(self, test_file: str, package: str, snippet: TestSnippet,
                       prev: CoverageReport) -> ValidationResult:
        new_tests = test_names(snippet.code)
        problems = check_snippet(snippet, self.module)
        if problems:
            return ValidationResult(ValidationKind.GUARD_REJECTED, "\n".join(problems), new_tests=new_tests)
        snippet_path = self.ws.scratch / "snippet.go"
        rendered = render_snippet(package, snippet)
        snippet_path.write_text(rendered, encoding="utf-8")
        r = await self.tools.merge(test_file, snippet_path)
        if r.exit_code != 0:
            return ValidationResult(ValidationKind.COMPILE_ERROR, r.combined, new_tests=new_tests,
                                    error_decls=decls_at(rendered, error_lines(r.combined, "snippet.go")))
        result = await self.check(prev, new_tests)
        if result.kind in (ValidationKind.COMPILE_ERROR, ValidationKind.VET_ERROR):
            merged = self.ws.read(test_file) or ""
            result.error_decls = decls_at(merged, error_lines(result.output, posixpath.basename(test_file)))
        return result

    async def prune_and_check(self, test_file: str, names: list[str], prev: CoverageReport,
                              new_tests: list[str]) -> ValidationResult:
        r = await self.tools.prune(test_file, names)
        if r.exit_code != 0:
            return ValidationResult(ValidationKind.COMPILE_ERROR, r.combined, new_tests=new_tests)
        return await self.check(prev, [n for n in new_tests if n not in names])

    def _output(self, r: CommandResult, stage: str) -> str:
        """The command's output, after a line naming the stage when it was killed at its timeout."""
        return f"{timeout_message(self.tools.settings, stage)}\n{r.combined}" if r.timed_out else r.combined

    async def check(self, prev: CoverageReport, new_tests: list[str]) -> ValidationResult:
        r = await self.tools.compile(self.packages)
        if r.exit_code != 0:
            return ValidationResult(ValidationKind.COMPILE_ERROR, self._output(r, "compile"), new_tests=new_tests)
        r = await self.tools.vet(self.packages)
        if r.exit_code != 0:
            return ValidationResult(ValidationKind.VET_ERROR, self._output(r, "vet"), new_tests=new_tests)
        m = await self.measure()
        if m.report is None:
            output = self._output(m.result, "test")
            failed = parse_failed_tests(m.result.combined) or list(new_tests)
            return ValidationResult(ValidationKind.TEST_FAILURE, output, failed_tests=failed, new_tests=new_tests)
        before, after = prev.covered_set(), m.report.covered_set()
        if not before <= after:
            return ValidationResult(ValidationKind.NO_GAIN, "the new tests made previously covered statements uncovered",
                                    report=m.report, new_tests=new_tests)
        if after == before:
            return ValidationResult(ValidationKind.NO_GAIN, "the new tests executed no previously uncovered statements",
                                    report=m.report, new_tests=new_tests)
        return ValidationResult(ValidationKind.ACCEPTED, report=m.report, new_tests=new_tests)
