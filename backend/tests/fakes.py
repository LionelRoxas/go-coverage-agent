# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
from app.models import SuspectedBug, TestScenario, TestSnippet, TokenUsage


def snippet(code: str, imports=("testing",), plan=(), bugs=()) -> TestSnippet:
    return TestSnippet(test_plan=[TestScenario(scenario=s, target=t) for s, t in plan], imports=list(imports),
                       code=code, suspected_bugs=[SuspectedBug(function=f, description=d) for f, d in bugs])


class FakeLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls: list[dict] = []
        self.last_effort: str | None = None

    async def complete(self, *, role, system, user, schema):
        self.calls.append({"role": role, "system": system, "user": user, "schema": schema})
        self.last_effort = {"writer": "medium", "fixer": "high"}.get(role)
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item, TokenUsage(prompt_tokens=100, completion_tokens=50)
