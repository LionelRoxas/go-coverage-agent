# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
"""Decides whether a candidate test snippet is kept: guard → merge → assertion scan → compile → vet → assertion
verdict → test (-count=2) → strict coverage gain."""
from __future__ import annotations

import json
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
# The test binary was cut short: `go test -timeout` ended it, or the kernel killed it (the OOM killer under mem_limit).
_CUT_SHORT = re.compile(r"^panic: test timed out|signal: killed", re.M)
# A write under /work (the repo copy, scratch, Go's $WORK) that hit the tmpfs size cap. The path keeps a test
# that merely prints this error text (e.g. one about ENOSPC handling) from ending the job.
_NO_SPACE = re.compile(r"(?:/work/|\$WORK/)\S*: no space left on device")
_TOP_DECL = re.compile(r"^(?:func\s+(?:\([^)]*\)\s*)?|type\s+|var\s+|const\s+)(\w+)")


class WorkspaceFull(Exception):
    """Go ran out of disk space in /work (a tmpfs shared by the repo copy, the scratch and Go's temp dirs). Every later
    check would fail the same way and the Fixer cannot repair it, so it ends the job (run_job: `workspace_full`)."""

    def __init__(self, stage: str, output: str):
        super().__init__(f"Go ran out of disk space during {stage}: the /work tmpfs is full. Raise its size (tmpfs /work "
                         "in docker-compose.yml, with mem_limit, whose memory it uses) or run a smaller module.")
        self.output = output


def check_space(r: CommandResult, stage: str) -> None:
    if _NO_SPACE.search(r.combined):
        raise WorkspaceFull(stage, r.combined)


class ValidationKind(StrEnum):
    ACCEPTED = "accepted"
    COMPILE_ERROR = "compile_error"
    VET_ERROR = "vet_error"
    TEST_FAILURE = "test_failure"
    NO_GAIN = "no_gain"
    GUARD_REJECTED = "guard_rejected"
    NO_ASSERTIONS = "no_assertions"  # new Test functions that call no t.Error*/t.Fatal* and pass t to no helper
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
    no_assertions: list[str] = field(default_factory=list)  # new Test functions that check nothing (NO_ASSERTIONS)
    # TEST_FAILURE only: the run was cut short (a timeout or a killed process) or Go named no failing test, so
    # `failed_tests` is a guess (every new test), not the tests Go reported as failing. Nothing is pruned and no
    # prediction disagreement is recorded for such a result.
    cut_short: bool = False

    @property
    def accepted(self) -> bool:
        return self.kind is ValidationKind.ACCEPTED

    def event(self) -> dict[str, Any]:
        event: dict[str, Any] = {"kind": self.kind.value, "output": self.output[:4000], "failed_tests": self.failed_tests}
        if self.no_assertions:
            event["no_assertions"] = self.no_assertions
        return event


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


ASSERTION_RULE = ("Every Test function must check its result with t.Error/t.Errorf/t.Fatal/t.Fatalf (or pass t to a "
                  "helper that does); an input tested only for \"does not panic\" goes in a test that also asserts "
                  "something, such as the returned error or a property of the result.")


def no_assertions_message(free: list[str], total: int) -> str:
    """What the trace and the Fixer are told about new Test functions (`free` of `total`) that check nothing."""
    what = f"{', '.join(free)}: no t.Error*/t.Fatal* call and t passed to no helper"
    if len(free) < total:
        return f"tests that check nothing ({what}); they are removed and the remaining tests are checked again"
    return f"no new Test function checks its result ({what}). {ASSERTION_RULE}"


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
            check_space(r, "merge")
            return ValidationResult(ValidationKind.COMPILE_ERROR, r.combined, new_tests=new_tests,
                                    error_decls=decls_at(rendered, error_lines(r.combined, "snippet.go")))
        r = await self.tools.asserts(snippet_path)
        if r.exit_code != 0:
            return ValidationResult(ValidationKind.COMPILE_ERROR, r.combined, new_tests=new_tests)
        try:
            free = set(json.loads(r.stdout))
        except ValueError:  # cut, empty or mixed with a warning: reject this candidate, never the job
            return ValidationResult(ValidationKind.COMPILE_ERROR,
                                    f"gohelper asserts: unreadable output (expected a JSON list of test names): "
                                    f"{r.combined[:500]!r}", new_tests=new_tests)
        result = await self.check(prev, new_tests, [n for n in new_tests if n in free])
        if result.kind in (ValidationKind.COMPILE_ERROR, ValidationKind.VET_ERROR):
            merged = self.ws.read(test_file) or ""
            result.error_decls = decls_at(merged, error_lines(result.output, posixpath.basename(test_file)))
        return result

    async def prune_and_check(self, test_file: str, names: list[str], prev: CoverageReport,
                              new_tests: list[str]) -> ValidationResult:
        r = await self.tools.prune(test_file, names)
        if r.exit_code != 0:
            check_space(r, "prune")
            return ValidationResult(ValidationKind.COMPILE_ERROR, r.combined, new_tests=new_tests)
        return await self.check(prev, [n for n in new_tests if n not in names])

    def _output(self, r: CommandResult, stage: str) -> str:
        """The command's output, after a line naming the stage when it was killed at its timeout. Raises WorkspaceFull
        when the command ran out of disk space."""
        check_space(r, stage)
        return f"{timeout_message(self.tools.settings, stage)}\n{r.combined}" if r.timed_out else r.combined

    async def check(self, prev: CoverageReport, new_tests: list[str],
                    no_assertions: list[str] | None = None) -> ValidationResult:
        """`no_assertions`: new tests that check nothing; once the code compiles and vets, they reject it before it
        runs (the orchestrator prunes them when other new tests remain, else hands the result to the Fixer)."""
        r = await self.tools.compile(self.packages)
        if r.exit_code != 0:
            return ValidationResult(ValidationKind.COMPILE_ERROR, self._output(r, "compile"), new_tests=new_tests)
        r = await self.tools.vet(self.packages)
        if r.exit_code != 0:
            return ValidationResult(ValidationKind.VET_ERROR, self._output(r, "vet"), new_tests=new_tests)
        if no_assertions:
            return ValidationResult(ValidationKind.NO_ASSERTIONS, no_assertions_message(no_assertions, len(new_tests)),
                                    new_tests=new_tests, no_assertions=list(no_assertions))
        m = await self.measure()
        if m.report is None:
            output = self._output(m.result, "test")
            named = parse_failed_tests(m.result.combined)
            cut_short = m.result.timed_out or not named or bool(_CUT_SHORT.search(m.result.combined))
            return ValidationResult(ValidationKind.TEST_FAILURE, output, failed_tests=named or list(new_tests),
                                    new_tests=new_tests, cut_short=cut_short)
        before, after = prev.covered_set(), m.report.covered_set()
        if not before <= after:
            return ValidationResult(ValidationKind.NO_GAIN, "the new tests made previously covered statements uncovered",
                                    report=m.report, new_tests=new_tests)
        if after == before:
            return ValidationResult(ValidationKind.NO_GAIN, "the new tests executed no previously uncovered statements",
                                    report=m.report, new_tests=new_tests)
        return ValidationResult(ValidationKind.ACCEPTED, report=m.report, new_tests=new_tests)
