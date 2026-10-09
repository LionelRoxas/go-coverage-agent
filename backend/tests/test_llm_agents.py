# AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
from app.agents.context import ContextInputs
from app.agents.llm_agents import Agents
from app.llm.client import estimate_tokens
from app.models import FuncKey, PlanItem, TestSnippet
from app.validator import ValidationKind, ValidationResult
from tests.fakes import FakeLLM, snippet

ITEM = PlanItem(file="mean.go", functions=[FuncKey(file="mean.go", name="Mean")], uncovered_statements=4)
INPUTS = ContextInputs(module="m", package="stats", go_version="1.17", source_file="mean.go", test_file="mean_test.go",
                       targets=[("Mean", "func Mean(input Float64Data) (float64, error) {\n\treturn 0, nil  // UNCOVERED\n}")],
                       declared=[], referenced=["type Float64Data []float64"] * 400, existing_tests=[])


async def test_write_sends_context_task_and_schema_within_budget():
    llm = FakeLLM([snippet("func TestMean(t *testing.T) {}")])
    out, usage = await Agents(llm, max_prompt_tokens=1500).write(ITEM, INPUTS)
    call = llm.calls[0]
    assert call["role"] == "writer" and call["schema"] is TestSnippet
    assert "mean_test.go" in call["user"] and "Mean" in call["user"] and "// UNCOVERED" in call["user"]
    assert estimate_tokens(call["system"]) + estimate_tokens(call["user"]) <= 1500
    assert out.code.startswith("func TestMean") and usage.total == 150


async def test_fix_includes_rejection_kind_output_and_previous_code():
    llm = FakeLLM([snippet("func TestMean(t *testing.T) {}")])
    bad = snippet("func TestMean(t *testing.T) { undefinedThing() }")
    result = ValidationResult(ValidationKind.COMPILE_ERROR, "./mean_test.go:3:2: undefined: undefinedThing")
    await Agents(llm, max_prompt_tokens=2000).fix(ITEM, INPUTS, bad, result)
    user = llm.calls[0]["user"]
    assert llm.calls[0]["role"] == "fixer"
    assert "compile_error" in user and "undefined: undefinedThing" in user and "undefinedThing()" in user


async def test_fix_trims_huge_tool_output():
    llm = FakeLLM([snippet("func TestMean(t *testing.T) {}")])
    result = ValidationResult(ValidationKind.TEST_FAILURE, "x" * 50_000)
    await Agents(llm, max_prompt_tokens=4500).fix(ITEM, INPUTS, snippet("func TestMean(t *testing.T) {}"), result)
    assert len(llm.calls[0]["user"]) < 4500 * 3.5
