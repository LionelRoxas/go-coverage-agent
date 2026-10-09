# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
"""The two LLM roles: Writer (new tests) and Fixer (repair rejected tests)."""
from __future__ import annotations

from functools import cache
from pathlib import Path

from app.agents.context import ContextInputs, render_context
from app.llm.client import LLMClient, estimate_tokens
from app.models import PlanItem, TestSnippet, TokenUsage
from app.validator import ValidationResult

_PROMPTS = Path(__file__).parent / "prompts"


@cache
def load_prompt(name: str) -> str:
    return (_PROMPTS / f"{name}.md").read_text(encoding="utf-8")


def _trim(text: str, limit: int) -> str:
    """Keep the head and the tail, since failing assertions usually sit at the end of tool output."""
    if len(text) <= limit:
        return text
    head = int(limit * 0.6)
    return f"{text[:head]}\n…[truncated]…\n{text[-(limit - head):]}"


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

    async def fix(self, item: PlanItem, inputs: ContextInputs, snippet: TestSnippet,
                  result: ValidationResult) -> tuple[TestSnippet, TokenUsage]:
        system = load_prompt("fixer")
        imports = ", ".join(snippet.imports) or "(none)"
        plan = "".join(f"- {sc.target}: {sc.scenario}\n" for sc in snippet.test_plan)
        plan_block = f"Test plan you declared:\n{plan}" if plan else ""
        task = (f"## Rejected snippet (kind: {result.kind.value})\nImports you declared: {imports}\n"
                f"{plan_block}```go\n{_trim(snippet.code, 5000)}\n```\n\n"
                f"## Validator output\n```\n{_trim(result.output, 2500)}\n```\n\n"
                f"## Task\nReturn a corrected replacement snippet for {_labels(item)}.")
        return await self.llm.complete(role="fixer", system=system, user=self._user(system, inputs, task),
                                       schema=TestSnippet)
