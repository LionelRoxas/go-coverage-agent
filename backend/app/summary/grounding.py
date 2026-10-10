# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
"""Deterministic grounding check: every number, .go file and Test name the model wrote must come from the facts.
A sentence of a paragraph, or a whole list item, that fails is dropped and counted.

Numbers are matched by what they measure: dollar amounts only against the cost facts (none without prices),
percentages ("81%", "81 percent", "81 points", "81 pp") only against percentage facts, durations ("5 minutes",
"310s", "two hours", "an hour") only against the run's durations, K/M amounts only against token facts, and other
numbers (digits, number words such as "eleven", ordinals such as "11th") against the remaining facts. Multipliers
("3x", "x3", "3-fold", "twice", "doubled", "half") have no facts to match, so they always fail."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterator, Literal

from app.models import BusinessSummary, RunSummary, SummaryGap, TechnicalSummary
from app.summary.facts import RunFacts
from app.summary.report import usd

Kind = Literal["currency", "percent", "duration", "multiplier", "tokens", "count"]

# A number standing on its own: not part of a word or version (go1.27, gpt-oss-120b, v1.2.3, e2de1ca387cb),
# optionally with a leading $, thousands separators, a K/M suffix, and a multiplier (3x, 3-fold), an ordinal (11th)
# or a unit (310s, 5min) glued to it.
_DIGITS = re.compile(
    r"(?:(?P<cur>\$)\s?|(?<![\w.$]))(?P<num>\d{1,3}(?:,\d{3})+(?!\d)|\d+(?:\.\d+)?)"
    r"(?:\s?(?P<suf>[kKmM])(?!\w))?"
    r"(?P<tail>\s?[x×](?!\w)|-fold\b|(?:st|nd|rd|th)\b|(?:s|secs?|mins?|h|hrs?)\b)?(?!\w|\.\d)")
_PREFIX_MULT = re.compile(r"(?<![\w.])[x×](?P<num>\d+(?:\.\d+)?)(?!\w|\.\d)")
_UNITS = {"zero": 0, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
          "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
          "seventeen": 17, "eighteen": 18, "nineteen": 19, "dozen": 12}
_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
_ONES = {"one": 1, **{k: v for k, v in _UNITS.items() if 2 <= v <= 9}}
_SCALES = {"hundred": 100, "thousand": 1000, "million": 1_000_000}
# "one" on its own is left out ("each one passes" is not a claim); "one hour" is still caught as a duration.
_WORDS = re.compile(
    rf"\b(?:(?P<tens>{'|'.join(_TENS)})(?:[-\s](?P<ones>{'|'.join(_ONES)}))?|(?P<unit>{'|'.join(_UNITS)})"
    rf"|(?P<scale>{'|'.join(_SCALES)}))(?:\s+(?P<times>{'|'.join(_SCALES)}))?\b", re.IGNORECASE)
_MULT_WORDS = {"twice": 2, "double": 2, "doubled": 2, "triple": 3, "tripled": 3, "quadrupled": 4, "half": 0.5,
               "halved": 0.5}
_MULT = re.compile(rf"\b(?P<word>{'|'.join(_MULT_WORDS)})\b(?!-)", re.IGNORECASE)  # not "double-check"
_ARTICLE_DURATION = re.compile(r"\b(?P<half>half\s+)?(?:an?|one)\s+(?P<unit>hour|minute|day|week)\b", re.IGNORECASE)
_PERCENT_AFTER = re.compile(r"\s?%|\s+(?:percent|per\s+cent|percentage\s+points?|points?|pp)\b", re.IGNORECASE)
# the first number of a range that ends in a percentage: "0 to 81%", "zero to 81%", "1.4-83.3%"
_RANGE_TO_PERCENT = re.compile(r"\s*(?:to|-|–|—)\s*\d[\d.,]*\s?(?:%|percent\b)", re.IGNORECASE)
_DURATION_AFTER = re.compile(r"[\s-]+(?P<unit>seconds?|secs?|s|minutes?|mins?|hours?|hrs?|h|days?|weeks?)\b",
                             re.IGNORECASE)
_SCALE_AFTER = re.compile(r"\s+(?P<scale>thousand|million)\b", re.IGNORECASE)  # "175 thousand"
_SPACED_PERCENT = re.compile(r"(\d)[ \u00a0\u202f]+%")
_SECONDS = {"s": 1, "sec": 1, "second": 1, "min": 60, "minute": 60, "h": 3600, "hr": 3600, "hour": 3600,
            "day": 86400, "week": 604800}

_GO_FILE = re.compile(r"[\w./-]*\w\.go\b")
_TEST_NAME = re.compile(r"\bTest[A-Z0-9_]\w*")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9`\"'(*$])")


@dataclass(frozen=True)
class NumberToken:
    text: str
    value: float  # as written: minutes for "5 minutes", thousands for "175K"
    decimals: int  # shown precision; 0 for words
    kind: Kind
    scale: float = 1.0  # 1e3 / 1e6 for K / M, or seconds per unit for a duration


def _seconds(unit: str) -> float:
    u = unit.lower()
    return _SECONDS.get(u) or _SECONDS.get(u.rstrip("s")) or _SECONDS.get(u[:3]) or 1.0


def _after(text: str, end: int) -> tuple[Kind, float] | None:
    """percent, or duration with seconds per unit, from the words right after a number."""
    if _PERCENT_AFTER.match(text, end) or _RANGE_TO_PERCENT.match(text, end):
        return "percent", 1.0
    if m := _DURATION_AFTER.match(text, end):
        return "duration", _seconds(m["unit"])
    return None


def number_tokens(text: str) -> Iterator[NumberToken]:
    found: list[tuple[int, NumberToken]] = []
    for m in _DIGITS.finditer(text):
        digits, suffix, tail = m["num"], m["suf"], (m["tail"] or "").strip().lower()
        kind: Kind = "count"
        scale = 1.0
        if m["cur"]:
            kind = "currency"
        elif tail in ("x", "×", "-fold"):
            kind = "multiplier"
        elif tail and tail not in ("st", "nd", "rd", "th"):
            kind, scale = "duration", _seconds(tail)
        elif suffix:
            kind, scale = "tokens", 1e3 if suffix.lower() == "k" else 1e6
        elif big := _SCALE_AFTER.match(text, m.end()):
            scale = _SCALES[big["scale"].lower()]  # a count in thousands or millions
        elif after := _after(text, m.end()):
            kind, scale = after
        if "." in digits:
            decimals = len(digits.split(".")[1])
        else:  # "175,000" is rounded to the thousand, "2,200" to the hundred (at most 3 places)
            whole = digits.replace(",", "")
            zeros = len(whole) - len(whole.rstrip("0")) if len(whole) >= 4 else 0
            decimals = -min(zeros, 3)
        found.append((m.start(), NumberToken(m.group(0).strip(), float(digits.replace(",", "")), decimals, kind, scale)))
    for m in _PREFIX_MULT.finditer(text):
        found.append((m.start(), NumberToken(m.group(0), float(m["num"]), 0, "multiplier")))
    for m in _WORDS.finditer(text):
        if m["tens"]:
            value = _TENS[m["tens"].lower()] + (_ONES[m["ones"].lower()] if m["ones"] else 0)
        elif m["unit"]:
            value = _UNITS[m["unit"].lower()]
        else:
            if re.search(r"\d\s+$", text[:m.start()]):
                continue  # "175 thousand": read with its digits above
            value = _SCALES[m["scale"].lower()]
        if m["times"] and not m["scale"]:
            value *= _SCALES[m["times"].lower()]
        kind, scale = _after(text, m.end()) or ("count", 1.0)
        found.append((m.start(), NumberToken(m.group(0), float(value), 0, kind, scale)))
    for m in _MULT.finditer(text):
        if m["word"].lower() == "half" and _ARTICLE_DURATION.match(text, m.start()):
            continue  # "half an hour" is a duration, below
        found.append((m.start(), NumberToken(m.group(0), _MULT_WORDS[m["word"].lower()], 0, "multiplier")))
    for m in _ARTICLE_DURATION.finditer(text):
        found.append((m.start(), NumberToken(m.group(0), 0.5 if m["half"] else 1.0, 1 if m["half"] else 0,
                                             "duration", _seconds(m["unit"]))))
    for _, token in sorted(found, key=lambda t: t[0]):
        yield token


def _numbers(node: Any, out: set[float]) -> set[float]:
    """Every number in a fact value, including those written inside fact strings (e.g. "the 80% target")."""
    if isinstance(node, bool) or node is None:
        return out
    if isinstance(node, (int, float)):
        out.add(float(node))
    elif isinstance(node, str):
        out.update(t.value * (t.scale if t.kind == "tokens" else 1) for t in number_tokens(node))
    elif isinstance(node, dict):
        for value in node.values():
            _numbers(value, out)
    elif isinstance(node, list):
        for value in node:
            _numbers(value, out)
    return out


class _Checker:
    def __init__(self, facts: RunFacts):
        f = facts
        # numbers inside fact strings ("Reached the 80% coverage target.") count for their own kind only
        in_text: dict[str, set[float]] = {}
        for t in (t for text in (f.repo, f.module or "", f.model, f.stop_message) for t in number_tokens(text)):
            in_text.setdefault(t.kind, set()).add(t.value * t.scale)
        tokens = _numbers(f.tokens.model_dump(), set()) | ({float(f.tokens_per_point)} if f.tokens_per_point else set())
        # the share still untested and the margin over the goal are exact, so they may be stated too
        derived = {round(100 - f.final_percent, 2)} | (
            {round(f.final_percent - f.goal_percent, 2)} if f.final_percent >= f.goal_percent else set())
        percents = ({f.goal_percent, f.baseline_percent, f.final_percent, f.gain_points} | derived
                    | {x for p in f.per_file for x in (p.before, p.after, round(p.after - p.before, 2))}
                    | {p.percent for p in f.lowest_files})
        # counts: the count fields themselves (never a percentage or a dollar amount), plus the token facts
        counts = {float(n) for n in (
            f.rounds, f.targets_accepted, f.targets_rejected, f.targets_deferred, f.failed_llm_calls, f.first_check_passes, f.llm_fixes, f.mechanical_repairs,
            f.duplicate_test_renames, f.helper_collision_fixes, f.no_gain_rejections,
            f.pruned_tests, f.pruned_no_assertions, f.prediction_disagreements, f.llm_timeouts, f.rate_limit_waits, f.tests_added_count, f.test_files_count,
            len(f.lowest_files), *f.rejected_reasons.values(), *(c.calls for c in f.llm_calls),
            *(low.uncovered_statements for low in f.lowest_files))} | tokens
        self.pools: dict[Kind, set[float]] = {
            "currency": set() if f.cost_usd is None else _numbers(f.cost_usd.model_dump(), set()),
            "percent": percents | in_text.get("percent", set()),
            "duration": {f.duration_s, f.rate_limit_wait_s},  # seconds
            "multiplier": set(),
            "tokens": tokens,
            "count": counts | in_text.get("count", set()),
        }
        self.files = {p.file for p in f.per_file} | set(f.test_files) | {p.file for p in f.lowest_files}
        self.exported = {f"{f.tests_dir}/{t}" for t in f.test_files}
        self.tests = set(f.tests_added)

    def _number_ok(self, t: NumberToken) -> bool:
        half_step = 0.5 * 10 ** -t.decimals + 1e-9  # "81" covers 80.5..81.5, "81.1" covers 81.05..81.15
        return any(abs(f / t.scale - t.value) <= half_step for f in self.pools[t.kind])

    def file_ok(self, path: str) -> bool:
        """A source or test file of the run, or a test file in the export folder; no invented directories."""
        path = path.removeprefix("./")
        return path in self.files or path in self.exported

    def ok(self, text: str) -> bool:
        # "each _test.go file" and "*_test.go" name no file, so they are not checked
        named = [m.group(0) for m in _GO_FILE.finditer(text)
                 if m.group(0).rsplit("/", 1)[-1] not in ("_test.go", ".go") and text[max(0, m.start() - 1)] != "*"]
        return (all(self._number_ok(t) for t in number_tokens(text))
                and all(self.file_ok(name) for name in named)
                and all(m.group(0) in self.tests for m in _TEST_NAME.finditer(text)))


def _paragraph(text: str, check: _Checker) -> tuple[str, int]:
    sentences = [s for s in _SENTENCE_END.split(text.strip()) if s]
    kept = [s for s in sentences if check.ok(s)]
    dropped = len(sentences) - len(kept)
    return (text if dropped == 0 else " ".join(kept)), dropped


def _items(items: list[str], check: _Checker) -> tuple[list[str], int]:
    kept = [i for i in items if check.ok(i)]
    return kept, len(items) - len(kept)


def tidy(text: str) -> str:
    """Writes "83.33 %" (also with a no-break space) as "83.33%"."""
    return _SPACED_PERCENT.sub(r"\1%", text)


def ground(summary: RunSummary, facts: RunFacts) -> tuple[RunSummary, int]:
    """The summary without the sentences and list items that state something absent from the facts, and how many
    were dropped. Suspected bugs are not the model's: they are the facts' own, as "Function: description"."""
    check = _Checker(facts)
    dropped = 0

    def para(text: str) -> str:
        nonlocal dropped
        kept, n = _paragraph(tidy(text), check)
        dropped += n
        return kept

    def items(values: list[str]) -> list[str]:
        nonlocal dropped
        kept, n = _items([tidy(v) for v in values], check)
        dropped += n
        return kept

    b, t = summary.business, summary.technical
    gaps = [SummaryGap(file=g.file, detail=tidy(g.detail)) for g in t.gaps]
    gaps = [g for g in gaps if check.file_ok(g.file) and check.ok(g.detail)]
    dropped += len(t.gaps) - len(gaps)
    business = BusinessSummary(headline=para(b.headline), outcome=para(b.outcome), efficiency=para(b.efficiency),
                               risks=items(b.risks), recommendation=para(b.recommendation))
    technical = TechnicalSummary(
        headline=para(t.headline), what_was_tested=para(t.what_was_tested), where_tests_live=para(t.where_tests_live),
        gaps=[SummaryGap(file=g.file, detail=g.detail) for g in gaps],
        suspected_bugs=[f"{bug.function}: {bug.description}" for bug in facts.suspected_bugs],
        rejected_or_failed=para(t.rejected_or_failed), how_to_run=para(t.how_to_run), next_steps=items(t.next_steps))
    return RunSummary(business=business, technical=technical), dropped


# Deterministic text for a required paragraph the model left empty or grounding emptied; built only from the facts.
FALLBACK_NOTE = "(Written from the run's data, because the AI text for this part was empty or could not be verified.)"


def _pct(value: float) -> str:
    return f"{value:g}%"


def _fallbacks(f: RunFacts) -> dict[str, dict[str, str]]:
    change = f"Coverage went from {_pct(f.baseline_percent)} to {_pct(f.final_percent)}"
    cost = f" Its estimated cost was {usd(f.cost_usd.total_usd)}." if f.cost_usd is not None else ""
    improved = [d.file for d in sorted(f.per_file, key=lambda d: (d.before - d.after, d.file)) if d.after > d.before]
    tested = (f"The new tests raise coverage in {', '.join(improved[:5])}{' and other files' if improved[5:] else ''}."
              if improved else "No source file gained coverage.")
    copy = (f"Copy the contents of {f.tests_dir} into the module root of {f.repo}, keeping sub-folders, so each test "
            "file sits next to its source file.")
    return {
        "business": {
            "headline": f"{change} against a goal of {_pct(f.goal_percent)}.",
            "outcome": f"The run stopped after {f.rounds} rounds: {f.stop_message}",
            "efficiency": f"The run took {f.duration_min} minutes and used {f.tokens.total:,} tokens.{cost}",
            "recommendation": ("Have a person review the generated tests before relying on them: they record what "
                               "the code does today."),
        },
        "technical": {
            "headline": f"{change}, with {f.tests_added_count} new tests in {f.test_files_count} test files.",
            "what_was_tested": tested,
            "where_tests_live": f"The generated tests are saved in {f.tests_dir}. {copy}",
            "rejected_or_failed": (
                f"Targets accepted: {f.targets_accepted}; rejected: {f.targets_rejected}. Fixer calls: {f.llm_fixes}; "
                f"mechanical repairs: {f.mechanical_repairs}; failing tests pruned: {f.pruned_tests}; tests removed "
                f"for checking nothing: {f.pruned_no_assertions}; prediction disagreements: "
                f"{f.prediction_disagreements}."),
            "how_to_run": f"{copy} Then run `go test ./...` and `go test -cover ./...` there.",
        },
    }


def fill_empty(summary: RunSummary, facts: RunFacts) -> tuple[RunSummary, list[str]]:
    """The summary with every empty required paragraph filled with deterministic text from the facts, ending in
    FALLBACK_NOTE so a reader can tell it apart, and the filled fields ("technical.where_tests_live")."""
    filled: list[str] = []
    parts: dict[str, Any] = {}
    for part, texts in _fallbacks(facts).items():
        model = getattr(summary, part)
        updates = {}
        for name, text in texts.items():
            if not getattr(model, name).strip():
                updates[name] = f"{text} {FALLBACK_NOTE}"
                filled.append(f"{part}.{name}")
        parts[part] = model.model_copy(update=updates)
    return RunSummary(**parts), filled
