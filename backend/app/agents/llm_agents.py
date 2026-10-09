# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
"""The two LLM roles: Writer (new tests) and Fixer (repair rejected tests)."""
from __future__ import annotations

import re
from functools import cache
from pathlib import Path

from app.agents.context import ContextInputs, ContextTooLarge, render_context
from app.llm.client import LLMClient, estimate_tokens
from app.models import PlanItem, TestSnippet, TokenUsage
from app.validator import ValidationResult

_PROMPTS = Path(__file__).parent / "prompts"
_TOP_DECL = re.compile(r"^(?:func|type|var|const)\b", re.M)
_DECL_NAME = re.compile(r"^(?:func\s+(?:\([^)]*\)\s*)?|type\s+|var\s+|const\s+)(\w+)")
_WORD = re.compile(r"\w+")


@cache
def load_prompt(name: str) -> str:
    return (_PROMPTS / f"{name}.md").read_text(encoding="utf-8")


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


def _failing_parts(snippet: TestSnippet, result: ValidationResult) -> str:
    """Only the top-level declarations the validator named (failed tests, or names in its output); else all the code."""
    code = snippet.code
    starts = [m.start() for m in _TOP_DECL.finditer(code)]
    if not starts:
        return code
    starts[0] = 0
    chunks = [code[a:b] for a, b in zip(starts, starts[1:] + [len(code)])]
    named = set(result.failed_tests) | set(_WORD.findall(result.output))
    kept = [c for c in chunks if (m := _DECL_NAME.match(c.lstrip())) and m.group(1) in named]
    return "\n".join(c.strip("\n") for c in kept) if kept else code


def _labels(item: PlanItem) -> str:
    return ", ".join(f"`{k.label()}`" for k in item.functions)


class Agents:
    def __init__(self, llm: LLMClient, max_prompt_tokens: int):
        self.llm = llm
        self.max_prompt_tokens = max_prompt_tokens

    def _user(self, system: str, inputs: ContextInputs, task: str) -> str:
        budget = self.max_prompt_tokens - estimate_tokens(system) - estimate_tokens(task) - 20
        return f"{render_context(inputs, budget)}\n\n{task}"

    async def write(self, item: PlanItem, inputs: ContextInputs) -> tuple[TestSnippet, TokenUsage]:
        system = load_prompt("writer")
        task = (f"## Task\nWrite new tests for {_labels(item)} that will be appended to `{inputs.test_file}`. "
                "Focus on executing the lines marked `// UNCOVERED`.")
        return await self.llm.complete(role="writer", system=system, user=self._user(system, inputs, task),
                                       schema=TestSnippet)

    def _fix_tasks(self, item: PlanItem, snippet: TestSnippet, result: ValidationResult) -> list[str]:
        """Fixer tasks from fullest to smallest. Related declarations are already optional inside render_context;
        after that the validator output is cut to its first lines, then the code to the failing parts, then the code is omitted."""
        imports = ", ".join(snippet.imports) or "(none)"
        plan = "".join(f"- {sc.target}: {sc.scenario}\n" for sc in snippet.test_plan)
        plan_block = f"Test plan you declared:\n{plan}" if plan else ""
        failing = _failing_parts(snippet, result)
        out = result.output

        def task(code: str | None, output: str, with_plan: bool = True) -> str:
            shown = (f"```go\n{code}\n```" if code is not None
                     else "(the rejected code is omitted to fit the prompt; write a fresh replacement)")
            return (f"## Rejected snippet (kind: {result.kind.value})\nImports you declared: {imports}\n"
                    f"{plan_block if with_plan else ''}{shown}\n\n"
                    f"## Validator output\n```\n{output}\n```\n\n"
                    f"## Task\nReturn a corrected replacement snippet for {_labels(item)}.")

        return [
            task(_trim(snippet.code, 5000), _trim(out, 2500)),
            task(_trim(snippet.code, 5000), _first_lines(out, 800)),
            task(_trim(failing, 2500), _first_lines(out, 800)),
            task(_trim(failing, 1000), _first_lines(out, 300), with_plan=False),
            task(None, _first_lines(out, 300), with_plan=False),
        ]

    async def fix(self, item: PlanItem, inputs: ContextInputs, snippet: TestSnippet,
                  result: ValidationResult) -> tuple[TestSnippet, TokenUsage]:
        system = load_prompt("fixer")
        error: ContextTooLarge | None = None
        for task in self._fix_tasks(item, snippet, result):
            try:
                user = self._user(system, inputs, task)
            except ContextTooLarge as e:  # degrade instead of failing; only the last (targets alone) is fatal
                error = e
                continue
            return await self.llm.complete(role="fixer", system=system, user=user, schema=TestSnippet)
        assert error is not None
        raise error
