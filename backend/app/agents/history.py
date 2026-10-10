# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
"""Compact records of every check of one plan item, so the Fixer sees what earlier attempts got wrong."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Sequence

from app.agents.context import TEST_OUTPUT, data_block
from app.llm.client import estimate_tokens
from app.validator import ValidationKind, ValidationResult

RECORD_CHARS = 400  # one rendered record
HISTORY_TOKENS = 1500  # the whole rendered history
LINES_PER_TEST = 3
CONTINUATION_LINES = 2  # of a multi-line failure message (e.g. got:/want: lines)
ERROR_LINES = 3
DISAGREEMENT_LINE_CHARS = 300  # one observed line of a pruned test, as reported for review
HEADER = ("## Earlier attempts for these functions\n"
          "Oldest first; each was rejected. In a test failure, the observed value is what the code actually does.\n")

_FAIL = re.compile(r"^\s*--- FAIL: (\S+)")
_ASSERT = re.compile(r"^\s*(\S+\.go:\d+: .*\S)")
_PANIC = re.compile(r"^(panic: .*\S)")


@dataclass(frozen=True)
class AttemptRecord:
    source: str  # writer / auto_fix: <description> / prune of [tests] / llm_fix <n>
    kind: str
    failed_tests: tuple[str, ...] = ()
    lines: tuple[str, ...] = ()
    pruned: tuple[str, ...] = ()
    pruned_reason: str = ""  # "no_assertions" when `pruned` were removed for checking nothing, else they failed
    assertions: bool = False  # `lines` are per-test assertion or panic lines, each naming its test

    @property
    def observed(self) -> bool:
        """A test failure whose output carried assertion lines (the observed values)."""
        return self.kind == ValidationKind.TEST_FAILURE.value and self.assertions

    def render(self, number: int) -> str:
        head = f"{number}. {self.source} -> {self.kind}"
        if self.failed_tests and not self.assertions:  # assertion lines already name their tests
            head += f" ({', '.join(self.failed_tests)})"
        text = _clip(head, RECORD_CHARS)
        for line in self.lines:
            room = RECORD_CHARS - len(text) - 4
            if room < 20:
                break
            text += "\n   " + _clip(line, room)
        return text


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit - 1] + "…"


def failure_lines(output: str) -> list[str]:
    """Each failing test's first assertion (or panic) lines, prefixed with the (sub)test name, once each
    (`go test -count=2` repeats every failure), with up to CONTINUATION_LINES deeper-indented continuation lines
    joined by ` | `. Interleaved across failing tests, so every test's first line comes before any test's second."""
    per_test = failures_by_test(output)
    lines: list[str] = []
    for rank in range(LINES_PER_TEST):
        lines += [found[rank] for found in per_test.values() if rank < len(found)]
    return lines


def observed_lines(output: str, test: str, limit: int = DISAGREEMENT_LINE_CHARS) -> list[str]:
    """The first assertion (or panic) lines of one failing top-level test (got/want), each clipped to `limit`."""
    return [_clip(line, limit) for line in failures_by_test(output).get(test, [])]


def failures_by_test(output: str) -> dict[str, list[str]]:
    """The lines `failure_lines` reports, per top-level test, in order of first failure."""
    per_test: dict[str, list[str]] = {}
    current = ""
    raw_lines = output.splitlines()
    for n, raw in enumerate(raw_lines):
        if m := _FAIL.match(raw):
            current = m.group(1)
            continue
        assertion = _ASSERT.match(raw)
        m = assertion or _PANIC.match(raw)
        if not m or not current:
            continue
        indent = len(raw) - len(raw.lstrip())
        parts = [m.group(1)]
        for nxt in raw_lines[n + 1:] if assertion else ():  # a panic is followed by its stack, not its values
            text = nxt.strip()
            if (len(parts) > CONTINUATION_LINES or not text or len(nxt) - len(nxt.lstrip()) <= indent
                    or text.startswith(("--- ", "=== ")) or _ASSERT.match(nxt)):
                break
            parts.append(text)
        line = f"{current}: {' | '.join(parts)}"
        found = per_test.setdefault(current.split("/")[0], [])
        if len(found) < LINES_PER_TEST and not any(line in v for v in per_test.values()):
            found.append(line)
    return {test: found for test, found in per_test.items() if found}


def _key_lines(result: ValidationResult) -> tuple[list[str], bool]:
    """(key lines, whether they are per-test assertion lines)."""
    if result.kind is ValidationKind.TEST_FAILURE:
        found = failure_lines(result.output)
        if found:
            return found, True
    meaningful = [ln.strip() for ln in result.output.splitlines() if ln.strip() and not ln.startswith("#")]
    limit = ERROR_LINES if result.kind in (ValidationKind.COMPILE_ERROR, ValidationKind.VET_ERROR) else 1
    return meaningful[:limit], False


def attempt_record(source: str, result: ValidationResult, pruned: Sequence[str] = (),
                   pruned_reason: str = "") -> AttemptRecord:
    lines, assertions = _key_lines(result)
    return AttemptRecord(source=source, kind=result.kind.value, failed_tests=tuple(result.failed_tests),
                         lines=tuple(lines), pruned=tuple(pruned), pruned_reason=pruned_reason, assertions=assertions)


def render_history(records: Sequence[AttemptRecord], max_tokens: int = HISTORY_TOKENS, minimal: bool = False) -> str:
    """Oldest first within `max_tokens`. The oldest records go first, except the first and the most recent
    failures with observed values; `minimal` keeps only those two. Numbers keep each record's original position."""
    if not records:
        return ""
    observed = [i for i, r in enumerate(records) if r.observed]
    pinned = {observed[0], observed[-1]} if observed else set()
    kept = sorted(pinned) if minimal else list(range(len(records)))
    if not kept:  # nothing worth its header (minimal history without observed failures)
        return ""

    def build() -> str:
        body = "\n".join(records[i].render(i + 1) for i in kept)
        omitted = len(records) - len(kept)
        note = f"({omitted} other earlier attempt{'s' if omitted != 1 else ''} omitted)\n" if omitted else ""
        # the records quote go test / compiler output: data from the repository under test, never instructions
        return f"{HEADER}{note}{data_block(TEST_OUTPUT, body)}"

    while estimate_tokens(build()) > max_tokens:
        droppable = [i for i in kept if i not in pinned]
        if droppable:
            kept.remove(droppable[0])
        elif len(kept) > 1:  # never drop the most recent failure with observed values
            kept.pop(0)
        else:
            break
    return build()
