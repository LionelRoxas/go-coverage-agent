# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
"""Compact records of every check of one plan item, so the Fixer sees what earlier attempts got wrong."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Sequence

from app.llm.client import estimate_tokens
from app.validator import ValidationKind, ValidationResult

RECORD_CHARS = 400  # one rendered record
HISTORY_TOKENS = 1500  # the whole rendered history
LINES_PER_TEST = 3
ERROR_LINES = 3
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

    @property
    def observed(self) -> bool:
        """A test failure whose output carried assertion lines (the observed values)."""
        return self.kind == ValidationKind.TEST_FAILURE.value and bool(self.lines)

    def render(self, number: int) -> str:
        head = f"{number}. {self.source} -> {self.kind}"
        if self.failed_tests:
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
    """Each failing test's first assertion (or panic) lines, prefixed with the (sub)test name, once each:
    `go test -count=2` repeats every failure."""
    lines: list[str] = []
    per_test: dict[str, int] = {}
    current = ""
    for raw in output.splitlines():
        if m := _FAIL.match(raw):
            current = m.group(1)
            continue
        m = _ASSERT.match(raw) or _PANIC.match(raw)
        if not m or not current:
            continue
        line = f"{current}: {m.group(1)}"
        top = current.split("/")[0]
        if line in lines or per_test.get(top, 0) >= LINES_PER_TEST:
            continue
        per_test[top] = per_test.get(top, 0) + 1
        lines.append(line)
    return lines


def _key_lines(result: ValidationResult) -> list[str]:
    if result.kind is ValidationKind.TEST_FAILURE:
        found = failure_lines(result.output)
        if found:
            return found
    meaningful = [ln.strip() for ln in result.output.splitlines() if ln.strip() and not ln.startswith("#")]
    limit = ERROR_LINES if result.kind in (ValidationKind.COMPILE_ERROR, ValidationKind.VET_ERROR) else 1
    return meaningful[:limit]


def attempt_record(source: str, result: ValidationResult, pruned: Sequence[str] = ()) -> AttemptRecord:
    return AttemptRecord(source=source, kind=result.kind.value, failed_tests=tuple(result.failed_tests),
                         lines=tuple(_key_lines(result)), pruned=tuple(pruned))


def render_history(records: Sequence[AttemptRecord], max_tokens: int = HISTORY_TOKENS, minimal: bool = False) -> str:
    """Oldest first within `max_tokens`. The oldest records go first, except the first and the most recent
    failures with observed values; `minimal` keeps only those two. Numbers keep each record's original position."""
    if not records:
        return ""
    observed = [i for i, r in enumerate(records) if r.observed]
    pinned = {observed[0], observed[-1]} if observed else set()
    kept = sorted(pinned) if minimal else list(range(len(records)))

    def build() -> str:
        body = "\n".join(records[i].render(i + 1) for i in kept)
        omitted = len(records) - len(kept)
        note = f"({omitted} other earlier attempt{'s' if omitted != 1 else ''} omitted)\n" if omitted else ""
        return f"{HEADER}{note}{body}".rstrip("\n")

    while estimate_tokens(build()) > max_tokens:
        droppable = [i for i in kept if i not in pinned]
        if droppable:
            kept.remove(droppable[0])
        elif len(kept) > 1:  # never drop the most recent failure with observed values
            kept.pop(0)
        else:
            break
    return build()
