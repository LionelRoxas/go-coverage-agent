# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
from app.models import (BusinessSummary, RunSummary, SummaryGap, SuspectedBug, TechnicalSummary, TestScenario,
                        TestSnippet, TokenUsage)

EFFORT = {"writer": "medium", "fixer": "medium", "summarizer": "medium"}


def snippet(code: str, imports=("testing",), plan=(), bugs=()) -> TestSnippet:
    return TestSnippet(test_plan=[TestScenario(scenario=s, target=t) for s, t in plan], imports=list(imports),
                       code=code, suspected_bugs=[SuspectedBug(function=f, description=d) for f, d in bugs])


class FakeLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls: list[dict] = []
        self.last_effort: str | None = None

    async def complete(self, *, role, system, user, schema, on_request=None):
        if on_request is not None:
            await on_request(EFFORT.get(role))
        self.calls.append({"role": role, "system": system, "user": user, "schema": schema})
        self.last_effort = EFFORT.get(role)
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item, TokenUsage(prompt_tokens=100, completion_tokens=50)


def run_summary(headline: str = "Coverage rose from 0% to 80%.") -> RunSummary:
    """A summary whose every number and file is grounded in tests' usual Summary (0% -> 80%, mean_test.go)."""
    return RunSummary(
        business=BusinessSummary(headline=headline, outcome="The goal was reached.", efficiency="It was quick.",
                                 risks=[], recommendation="Keep the tests."),
        technical=TechnicalSummary(headline="Coverage is now 80%.", what_was_tested="The new tests cover the package.",
                                   where_tests_live="See the tests folder.", gaps=[], suspected_bugs=[],
                                   rejected_or_failed="Nothing was rejected.", how_to_run="Run `go test ./...`.",
                                   next_steps=["Keep the tests in CI."]))


def fake_llm(emit=None) -> FakeLLM:
    """JobManager llm_factory for tests: one grounded summary per summary call, never Groq."""
    return FakeLLM([run_summary()])
