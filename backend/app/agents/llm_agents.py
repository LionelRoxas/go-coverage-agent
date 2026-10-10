# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
"""The LLM roles: Writer (new tests), Fixer (repair rejected tests) and Summarizer (end-of-run summary)."""
from __future__ import annotations

import re
from functools import cache
from pathlib import Path
from typing import Sequence

from app.agents.context import (REJECTED_SNIPPET, TEST_OUTPUT, ContextInputs, ContextTooLarge, data_block,
                                render_context)
from app.agents.history import AttemptRecord, render_history
from app.llm.client import LLMClient, OnRequest, estimate_tokens
from app.models import PlanItem, RunSummary, TestSnippet, TokenUsage
from app.summary.facts import RunFacts
from app.validator import ValidationKind, ValidationResult

_PROMPTS = Path(__file__).parent / "prompts"
_TOP_DECL = re.compile(r"^(?:func|type|var|const)\b", re.M)
_DECL_NAME = re.compile(r"^(?:func\s+(?:\([^)]*\)\s*)?|type\s+|var\s+|const\s+)(\w+)")
_WORD = re.compile(r"\w+")
PRUNED_NO_GAIN = ("Removing the failing tests left no new coverage: the tests that reached the uncovered lines were the "
                  "ones that failed. Keep them and correct their expected values (observed values are in the history).")
PRUNED_SILENT_NO_GAIN = ("Removing the tests without assertions ({names}) left no new coverage: they were the ones that "
                         "reached the uncovered lines. Keep them and make each check its results with t.Error/t.Fatal.")


_HEADER = re.compile(r"\A<!--.*?-->\s*", re.S)


@cache
def load_prompt(name: str) -> str:
    """The prompt file without its leading <!-- --> disclosure comment, which is for readers of the repo, not the model."""
    return _HEADER.sub("", (_PROMPTS / f"{name}.md").read_text(encoding="utf-8"), count=1)


def _trim(text: str, limit: int) -> str:
    """Keep the head and the tail, since failing assertions usually sit at the end of tool output."""
    if len(text) <= limit:
        return text
    head = int(limit * 0.6)
    return f"{text[:head]}\n…[truncated]…\n{text[-(limit - head):]}"


def _first_lines(text: str, limit: int) -> str:
    """The first whole lines of tool output that fit in `limit` characters (the first error comes first)."""
    if len(text) <= limit:
        return text
    kept, size = [], 0
    for line in text.splitlines():
        if size + len(line) + 1 > limit:
            break
        kept.append(line)
        size += len(line) + 1
    return ("\n".join(kept) if kept else text[:limit]) + "\n…[truncated]…"


def _relevant_parts(snippet: TestSnippet, result: ValidationResult, limit: int,
                    extra: Sequence[str] = ()) -> str | None:
    """Whole top-level declarations only, never cut mid-function: those the validator pointed at (failed tests,
    declarations at the error lines, names in its output) that fit in `limit` characters; when it pointed at none,
    the leading declarations that fit. None when not even one whole declaration fits."""
    code = snippet.code.strip("\n")
    starts = [m.start() for m in _TOP_DECL.finditer(code)]
    if not starts:
        return code if len(code) <= limit else None
    starts[0] = 0
    chunks = [code[a:b].strip("\n") for a, b in zip(starts, starts[1:] + [len(code)], strict=True)]
    named = set(result.failed_tests) | set(result.error_decls) | set(_WORD.findall(result.output)) | set(extra)
    pointed = [c for c in chunks if (m := _DECL_NAME.match(c.lstrip())) and m.group(1) in named]
    kept: list[str] = []
    size = 0
    for chunk in pointed or chunks:
        if size + len(chunk) + 2 > limit:
            if pointed:
                continue  # another pointed-at declaration may still fit
            break
        kept.append(chunk)
        size += len(chunk) + 2
    return "\n\n".join(kept) if kept else None


_COMPACT_TESTS = 30  # test names kept when the full facts do not fit the prompt (tests_added_count stays exact)


def _labels(item: PlanItem) -> str:
    return ", ".join(f"`{k.label()}`" for k in item.functions)


def helper_prefix(file: str) -> str:
    """A Go identifier prefix from a source file's base name: `norm.go` -> `norm`, `big_int.go` -> `bigInt`."""
    words = [w for w in re.split(r"[^0-9A-Za-z]+", Path(file).stem) if w]
    prefix = "".join([words[0].lower(), *(w[:1].upper() + w[1:] for w in words[1:])]) if words else "t"
    return prefix if prefix[0].isalpha() else f"t{prefix}"


def parallel_naming_rule(item: PlanItem) -> str:
    """PARALLEL_WRITERS only: other writers fill the same package (one Go namespace) at the same time."""
    p = helper_prefix(item.file)
    return (f"Other tests for this package are being written at the same time: name every new helper function, type, "
            f"var and const with the prefix `{p}` (e.g. `{p}ApproxEqual`, `{p}Cases`), and start each Test function "
            f"name with the name of the function it tests.")


class Agents:
    def __init__(self, llm: LLMClient, max_prompt_tokens: int):
        self.llm = llm
        self.max_prompt_tokens = max_prompt_tokens

    @property
    def last_effort(self) -> str | None:
        """The reasoning effort the last successful call actually used (lowered after a truncated answer)."""
        return self.llm.last_effort

    def _user(self, system: str, inputs: ContextInputs, task: str) -> str:
        budget = self.max_prompt_tokens - estimate_tokens(system) - estimate_tokens(task) - 20
        return f"{render_context(inputs, budget)}\n\n{task}"

    async def write(self, item: PlanItem, inputs: ContextInputs, on_request: OnRequest | None = None,
                    parallel: bool = False) -> tuple[TestSnippet, TokenUsage]:
        system = load_prompt("writer")
        task = (f"## Task\nWrite new tests for {_labels(item)} that will be appended to `{inputs.test_file}`. "
                "Focus on executing the lines marked `// UNCOVERED`.")
        if parallel:  # off: the prompt stays exactly as it was
            task += f"\n{parallel_naming_rule(item)}"
        return await self.llm.complete(role="writer", system=system, user=self._user(system, inputs, task),
                                       schema=TestSnippet, on_request=on_request)

    def _fix_tasks(self, item: PlanItem, snippet: TestSnippet, result: ValidationResult,
                   history: Sequence[AttemptRecord] = ()) -> list[str]:
        """Fixer tasks from fullest to smallest. Related declarations are already optional inside render_context;
        after that the earlier-attempts history is cut to its first and latest failures with observed values, then
        the validator output to its first lines, then the code to whole relevant declarations, then the code is omitted."""
        imports = ", ".join(snippet.imports) or "(none)"
        plan = "".join(f"- {sc.target}: {sc.scenario}\n" for sc in snippet.test_plan)
        plan_block = f"Test plan you declared:\n{plan}" if plan else ""
        out = result.output
        earlier, current = list(history[:-1]), (history[-1] if history else None)
        pruned = current.pruned if current is not None else ()
        goal = f"Return a corrected replacement snippet for {_labels(item)}."
        if result.kind is ValidationKind.NO_GAIN and pruned and any(
                r.kind == ValidationKind.TEST_FAILURE.value and set(r.failed_tests) & set(pruned) for r in earlier):
            goal += f" {PRUNED_NO_GAIN}"
        elif result.kind is ValidationKind.NO_GAIN and pruned and current is not None \
                and current.pruned_reason == ValidationKind.NO_ASSERTIONS.value:
            goal += f" {PRUNED_SILENT_NO_GAIN.format(names=', '.join(pruned))}"
        full_history, short_history = render_history(earlier), render_history(earlier, minimal=True)

        def task(code: str | None, output: str, past: str, with_plan: bool = True) -> str:
            shown = (data_block(REJECTED_SNIPPET, f"```go\n{code}\n```") if code is not None
                     else "(the rejected code is omitted to fit the prompt; write a fresh replacement)")
            checked = data_block(TEST_OUTPUT, f"```\n{output}\n```")  # go test / compiler output: data only
            return (f"{past + chr(10) * 2 if past else ''}"
                    f"## Rejected snippet (kind: {result.kind.value})\nImports you declared: {imports}\n"
                    f"{plan_block if with_plan else ''}{shown}\n\n"
                    f"## Validator output\n{checked}\n\n"
                    f"## Task\n{goal}")

        return [
            task(_trim(snippet.code, 5000), _trim(out, 2500), full_history),
            task(_trim(snippet.code, 5000), _trim(out, 2500), short_history),
            task(_trim(snippet.code, 5000), _first_lines(out, 800), short_history),
            task(_relevant_parts(snippet, result, 2500, pruned), _first_lines(out, 800), short_history),
            task(_relevant_parts(snippet, result, 1000, pruned), _first_lines(out, 300), short_history, with_plan=False),
            task(None, _first_lines(out, 300), short_history, with_plan=False),
        ]

    async def fix(self, item: PlanItem, inputs: ContextInputs, snippet: TestSnippet, result: ValidationResult,
                  history: Sequence[AttemptRecord] = (),
                  on_request: OnRequest | None = None) -> tuple[TestSnippet, TokenUsage]:
        """`history`: this item's checks so far, oldest first, ending with the one that produced `result`."""
        system = load_prompt("fixer")
        error: ContextTooLarge | None = None
        for task in self._fix_tasks(item, snippet, result, history):
            try:
                user = self._user(system, inputs, task)
            except ContextTooLarge as e:  # degrade instead of failing; only the targets plus the minimal task are fatal
                error = e
                continue
            return await self.llm.complete(role="fixer", system=system, user=user, schema=TestSnippet,
                                           on_request=on_request)
        assert error is not None
        raise ContextTooLarge(f"{error}; the targets plus the Fixer's minimal task (first error lines, no code) "
                              "do not fit") from error

    async def summarize(self, facts: RunFacts,
                        on_request: OnRequest | None = None) -> tuple[RunSummary, TokenUsage]:
        """The business and technical summary of a finished run, written from its measured facts only. When the
        facts do not fit the prompt, unchanged files and most test names are left out (their counts stay)."""
        system = load_prompt("summarizer")

        def user(f: RunFacts) -> str:
            return (f"## Facts (JSON)\n```json\n{f.model_dump_json()}\n```\n\n"
                    "## Task\nWrite the business and the technical summary of this run from these facts only.")

        text = user(facts)
        if estimate_tokens(system) + estimate_tokens(text) > self.max_prompt_tokens:
            text = user(facts.model_copy(update={
                "per_file": [f for f in facts.per_file if f.after != f.before],
                "tests_added": facts.tests_added[:_COMPACT_TESTS]}))
        return await self.llm.complete(role="summarizer", system=system, user=text, schema=RunSummary,
                                       on_request=on_request)
