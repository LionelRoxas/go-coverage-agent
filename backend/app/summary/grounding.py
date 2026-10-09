# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
"""Deterministic grounding check: every number, .go file and Test name the model wrote must come from the facts.
A sentence of a paragraph, or a whole list item, that fails is dropped and counted."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterator

from app.models import BusinessSummary, RunSummary, SummaryGap, TechnicalSummary
from app.summary.facts import RunFacts

# A number standing on its own: not part of a word or version (go1.27, gpt-oss-120b, v1.2.3, e2de1ca387cb),
# optionally with thousands separators and a K/M suffix.
_NUMBER = re.compile(r"(?<![\w.])(\d{1,3}(?:,\d{3})+(?!\d)|\d+(?:\.\d+)?)(?:\s?([kKmM])(?!\w))?(?![\w]|\.\d)")
_GO_FILE = re.compile(r"[\w./-]*\w\.go\b")
_TEST_NAME = re.compile(r"\bTest[A-Z0-9_]\w*")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9`\"'(*$])")
_SCALE = {"k": 1e3, "m": 1e6}


@dataclass(frozen=True)
class NumberToken:
    text: str
    value: float
    decimals: int
    scale: float


def number_tokens(text: str) -> Iterator[NumberToken]:
    for m in _NUMBER.finditer(text):
        digits, suffix = m.group(1), m.group(2)
        decimals = len(digits.split(".")[1]) if "." in digits else 0
        yield NumberToken(text=m.group(0).replace(" ", ""), value=float(digits.replace(",", "")), decimals=decimals,
                          scale=_SCALE[suffix.lower()] if suffix else 1.0)


def _fact_numbers(node: Any, out: set[float]) -> set[float]:
    if isinstance(node, bool) or node is None:
        return out
    if isinstance(node, (int, float)):
        out.add(float(node))
    elif isinstance(node, str):
        out.update(t.value * t.scale for t in number_tokens(node))
    elif isinstance(node, dict):
        for value in node.values():
            _fact_numbers(value, out)
    elif isinstance(node, list):
        for value in node:
            _fact_numbers(value, out)
    return out


class _Checker:
    def __init__(self, facts: RunFacts):
        self.numbers = _fact_numbers(facts.model_dump(mode="json"), set())
        self.files = {f.file for f in facts.per_file} | set(facts.test_files) | {f.file for f in facts.lowest_files}
        self.tests = set(facts.tests_added)

    def _number_ok(self, t: NumberToken) -> bool:
        half_step = 0.5 * 10 ** -t.decimals + 1e-9  # "81" covers 80.5..81.5, "81.1" covers 81.05..81.15
        return any(abs(f / t.scale - t.value) <= half_step for f in self.numbers)

    def _file_ok(self, path: str) -> bool:
        path = path.removeprefix("./")
        return any(path == f or path.endswith("/" + f) for f in self.files)

    def ok(self, text: str) -> bool:
        return (all(self._number_ok(t) for t in number_tokens(text))
                and all(self._file_ok(m.group(0)) for m in _GO_FILE.finditer(text))
                and all(m.group(0) in self.tests for m in _TEST_NAME.finditer(text)))


def _paragraph(text: str, check: _Checker) -> tuple[str, int]:
    sentences = [s for s in _SENTENCE_END.split(text.strip()) if s]
    kept = [s for s in sentences if check.ok(s)]
    dropped = len(sentences) - len(kept)
    return (text if dropped == 0 else " ".join(kept)), dropped


def _items(items: list[str], check: _Checker) -> tuple[list[str], int]:
    kept = [i for i in items if check.ok(i)]
    return kept, len(items) - len(kept)


def ground(summary: RunSummary, facts: RunFacts) -> tuple[RunSummary, int]:
    """The summary without the sentences and list items that state something absent from the facts, and how many
    were dropped."""
    check = _Checker(facts)
    dropped = 0

    def para(text: str) -> str:
        nonlocal dropped
        kept, n = _paragraph(text, check)
        dropped += n
        return kept

    def items(values: list[str]) -> list[str]:
        nonlocal dropped
        kept, n = _items(values, check)
        dropped += n
        return kept

    b, t = summary.business, summary.technical
    gaps = [g for g in t.gaps if check.ok(g.file) and g.file.removeprefix("./") in check.files and check.ok(g.detail)]
    dropped += len(t.gaps) - len(gaps)
    business = BusinessSummary(headline=para(b.headline), outcome=para(b.outcome), efficiency=para(b.efficiency),
                               risks=items(b.risks), recommendation=para(b.recommendation))
    technical = TechnicalSummary(
        headline=para(t.headline), what_was_tested=para(t.what_was_tested), where_tests_live=para(t.where_tests_live),
        gaps=[SummaryGap(file=g.file, detail=g.detail) for g in gaps], suspected_bugs=items(t.suspected_bugs),
        rejected_or_failed=para(t.rejected_or_failed), how_to_run=para(t.how_to_run), next_steps=items(t.next_steps))
    return RunSummary(business=business, technical=technical), dropped
