# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
from pathlib import Path

import pytest

from app.agents import llm_agents
from app.agents.context import ContextInputs, ContextTooLarge, render_context
from app.agents.history import attempt_record
from app.agents.llm_agents import Agents, load_prompt
from app.llm.client import estimate_tokens
from app.models import FuncKey, PlanItem, TestSnippet
from app.validator import ValidationKind, ValidationResult
from tests.fakes import FakeLLM, snippet

ITEM = PlanItem(file="mean.go", functions=[FuncKey(file="mean.go", name="Mean")], uncovered_statements=4)
INPUTS = ContextInputs(module="m", package="stats", go_version="1.17", source_file="mean.go", test_file="mean_test.go",
                       targets=[("Mean", "func Mean(input Float64Data) (float64, error) {\n\treturn 0, nil  // UNCOVERED\n}")],
                       declared=[], referenced=["type Float64Data []float64"] * 400, existing_tests=[])



@pytest.mark.parametrize("name", ["writer", "fixer", "summarizer"])
def test_prompt_files_carry_the_disclosure_header_but_the_model_never_sees_it(name):
    raw = (Path(llm_agents.__file__).parent / "prompts" / f"{name}.md").read_text(encoding="utf-8")
    assert raw.startswith("<!-- AI-generated with Claude Code"), "the file itself is disclosed"
    sent = load_prompt(name)
    assert "AI-generated" not in sent and "<!--" not in sent
    assert sent == sent.lstrip() and sent.startswith("You ")

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
    user = llm.calls[0]["user"]
    assert len(user) < 4500 * 3.5 and "…[truncated]…" in user and "x" * 50_000 not in user


async def test_fix_shows_declared_imports_and_plan():
    llm = FakeLLM([snippet("func TestMean(t *testing.T) {}")])
    bad = snippet("func TestMean(t *testing.T) { math.Abs(1) }", imports=("testing", "math"),
                  plan=[("empty input", "Mean")])
    await Agents(llm, max_prompt_tokens=2000).fix(ITEM, INPUTS, bad, ValidationResult(ValidationKind.VET_ERROR, "boom"))
    user = llm.calls[0]["user"]
    assert "Imports you declared: testing, math" in user and "- Mean: empty input" in user


BIG_TARGET = "func Mean(input Float64Data) (float64, error) {\n" + "\tx := 1  // UNCOVERED\n" * 150 + "}"
BIG_INPUTS = ContextInputs(module="m", package="stats", go_version="1.17", source_file="mean.go", test_file="mean_test.go",
                           targets=[("Mean", BIG_TARGET)], declared=[], referenced=["type Float64Data []float64"] * 50,
                           existing_tests=["func TestOld(t *testing.T)"])


def _two_tests() -> TestSnippet:
    failing = "func TestFail(t *testing.T) {\n" + "\tt.Log(\"fail\")\n" * 60 + "}\n"
    passing = "func TestOther(t *testing.T) {\n" + "\tt.Log(\"other\")\n" * 200 + "}\n"
    return snippet(failing + "\n" + passing)


async def test_fix_degrades_to_failing_parts_and_first_error_lines_instead_of_failing():
    llm = FakeLLM([snippet("func TestFail(t *testing.T) {}")])
    output = "--- FAIL: TestFail (0.00s)\n    mean_test.go:3: got 1 want 2\n" + "noise line\n" * 400
    result = ValidationResult(ValidationKind.TEST_FAILURE, output, failed_tests=["TestFail"])
    budget = 2180  # fits the full context but not the full task (fixer.md grew ~80 tokens in Task 32)
    await Agents(llm, max_prompt_tokens=budget).fix(ITEM, BIG_INPUTS, _two_tests(), result)
    call = llm.calls[0]
    user = call["user"]
    assert estimate_tokens(call["system"]) + estimate_tokens(user) <= budget
    assert "x := 1  // UNCOVERED" in user and "func TestOld(t *testing.T)" in user
    assert "--- FAIL: TestFail" in user and "got 1 want 2" in user
    assert "func TestFail" in user and "TestOther" not in user


async def test_fix_omits_the_code_as_a_last_resort():
    llm = FakeLLM([snippet("func TestFail(t *testing.T) {}")])
    result = ValidationResult(ValidationKind.COMPILE_ERROR, "./mean_test.go:3:2: undefined: foo\n" * 50)
    target_only = estimate_tokens(load_prompt("fixer")) + 20 + estimate_tokens(
        render_context(BIG_INPUTS, 10_000).split("## Tests already")[0])
    await Agents(llm, max_prompt_tokens=target_only + 200).fix(ITEM, BIG_INPUTS, _two_tests(), result)
    user = llm.calls[0]["user"]
    assert "undefined: foo" in user and "TestFail" not in user and "omitted" in user


async def test_fix_raises_context_too_large_only_when_targets_plus_minimal_task_do_not_fit():
    llm = FakeLLM([])
    result = ValidationResult(ValidationKind.COMPILE_ERROR, "undefined: foo")
    with pytest.raises(ContextTooLarge, match="targets need .*the targets plus the Fixer's minimal task"):
        await Agents(llm, max_prompt_tokens=900).fix(ITEM, BIG_INPUTS, _two_tests(), result)
    assert llm.calls == []


def _three_tests() -> TestSnippet:
    def fn(name: str) -> str:
        return f"func {name}(t *testing.T) {{\n" + f"\tt.Log(\"{name.lower()}\")\n" * 30 + "\tt.Log(\"end\")\n}\n"
    return snippet("\n".join(fn(n) for n in ("TestOne", "TestTwo", "TestThree")))


def _code_block(user: str) -> str:
    return user.split("```go\n")[-1].split("\n```")[0]


async def test_fix_shrinks_compile_errors_to_whole_declarations_the_error_lines_point_at():
    llm = FakeLLM([snippet("func TestTwo(t *testing.T) {}")])
    output = "# stats\n./mean_test.go:52:2: undefined: foo\n" + "note: more context\n" * 100
    result = ValidationResult(ValidationKind.COMPILE_ERROR, output, error_decls=["TestTwo"])
    await Agents(llm, max_prompt_tokens=2100).fix(ITEM, BIG_INPUTS, _three_tests(), result)
    code = _code_block(llm.calls[0]["user"])  # the rejected snippet is the last Go block in the prompt
    assert code.startswith("func TestTwo(t *testing.T) {") and code.endswith("\tt.Log(\"end\")\n}")
    assert "TestOne" not in code and "TestThree" not in code and "…[truncated]…" not in code


async def test_fix_keeps_whole_leading_declarations_when_no_line_points_anywhere():
    llm = FakeLLM([snippet("func TestOne(t *testing.T) {}")])
    output = "vet: something odd happened\n" * 100
    result = ValidationResult(ValidationKind.VET_ERROR, output)
    await Agents(llm, max_prompt_tokens=2000).fix(ITEM, BIG_INPUTS, _three_tests(), result)
    code = _code_block(llm.calls[0]["user"])
    assert code.startswith("func TestOne(t *testing.T) {") and code.endswith("\tt.Log(\"end\")\n}")
    assert "TestTwo" not in code and "…[truncated]…" not in code


FAILURE_OUT = ("--- FAIL: TestFail (0.00s)\n    --- FAIL: TestFail/x (0.00s)\n        mean_test.go:3: minorDirty = true, want false\n"
               "--- FAIL: TestFail (0.00s)\n    --- FAIL: TestFail/x (0.00s)\n        mean_test.go:3: minorDirty = true, want false\n")
NO_GAIN = ValidationResult(ValidationKind.NO_GAIN, "the new tests executed no previously uncovered statements")


def _evidence_history():
    """writer -> test_failure, then pruning the failing test left no_gain (output/7ef641efb870, iteration 7)."""
    return [attempt_record("writer", ValidationResult(ValidationKind.TEST_FAILURE, FAILURE_OUT, failed_tests=["TestFail"])),
            attempt_record("prune of [TestFail]", NO_GAIN, pruned=["TestFail"])]


async def test_fix_renders_earlier_attempts_before_the_rejected_snippet():
    llm = FakeLLM([snippet("func TestFail(t *testing.T) {}")])
    await Agents(llm, max_prompt_tokens=4000).fix(ITEM, INPUTS, _two_tests(), NO_GAIN, _evidence_history())
    user = llm.calls[0]["user"]
    assert "## Earlier attempts for these functions" in user
    assert user.index("## Earlier attempts") < user.index("## Rejected snippet")
    assert "1. writer -> test_failure\n" in user  # each assertion line names its test
    assert user.count("TestFail/x: mean_test.go:3: minorDirty = true, want false") == 1
    assert "2. prune" not in user, "the latest check is the validator output, not an earlier attempt"


async def test_fix_after_pruned_failures_says_to_keep_and_correct_them():
    llm = FakeLLM([snippet("func TestFail(t *testing.T) {}")])
    await Agents(llm, max_prompt_tokens=4000).fix(ITEM, INPUTS, _two_tests(), NO_GAIN, _evidence_history())
    assert ("Removing the failing tests left no new coverage: the tests that reached the uncovered lines were the ones "
            "that failed. Keep them and correct their expected values (observed values are in the history).") \
        in llm.calls[0]["user"]


async def test_fix_without_pruned_failures_has_no_keep_them_line():
    llm = FakeLLM([snippet("func TestFail(t *testing.T) {}")])
    history = [attempt_record("writer", NO_GAIN)]
    await Agents(llm, max_prompt_tokens=4000).fix(ITEM, INPUTS, _two_tests(), NO_GAIN, history)
    assert "Removing the failing tests" not in llm.calls[0]["user"]


async def test_fix_history_is_trimmed_before_the_code_but_keeps_the_latest_observed_failure():
    noise = [attempt_record(f"llm_fix {i}", ValidationResult(ValidationKind.VET_ERROR, f"vet: {'n' * 300} {i}"))
             for i in range(1, 12)]
    history = [*_evidence_history()[:1], *noise, *_evidence_history()[1:]]
    full = Agents(FakeLLM([]), 100_000)._fix_tasks(ITEM, _two_tests(), NO_GAIN, history)[0]
    llm = FakeLLM([snippet("func TestFail(t *testing.T) {}")])
    budget = estimate_tokens(load_prompt("fixer")) + 20 + estimate_tokens(
        render_context(BIG_INPUTS, 10_000).split("## Related")[0]) + estimate_tokens(full) - 600
    await Agents(llm, max_prompt_tokens=budget).fix(ITEM, BIG_INPUTS, _two_tests(), NO_GAIN, history)
    user = llm.calls[0]["user"]
    assert "llm_fix 3" not in user, "the history is trimmed"
    assert "minorDirty = true, want false" in user, "the latest failure with observed values survives"
    assert "func TestFail(t *testing.T) {" in user, "the code is not dropped while history can still shrink"


async def test_fix_with_no_history_has_no_history_section():
    llm = FakeLLM([snippet("func TestMean(t *testing.T) {}")])
    await Agents(llm, max_prompt_tokens=2000).fix(ITEM, INPUTS, snippet("func TestMean(t *testing.T) {}"), NO_GAIN)
    assert "Earlier attempts" not in llm.calls[0]["user"]


async def test_summarize_sends_the_facts_as_json_with_the_summary_schema():
    from app.models import RunSummary
    from tests.fakes import run_summary
    from tests.test_summary_facts import facts

    llm = FakeLLM([run_summary()])
    seen = []

    async def on_request(effort):
        seen.append(effort)

    f = facts()
    out, usage = await Agents(llm, max_prompt_tokens=12000).summarize(f, on_request=on_request)
    call = llm.calls[0]
    assert call["role"] == "summarizer" and call["schema"] is RunSummary and seen == ["medium"]
    assert call["system"] == load_prompt("summarizer")
    assert f.model_dump_json() in call["user"]
    assert out == run_summary() and usage.total == 150


async def test_summarize_compacts_the_facts_to_fit_a_small_prompt_budget():
    from tests.fakes import run_summary
    from tests.test_summary_facts import facts

    llm = FakeLLM([run_summary()])
    f = facts()
    budget = 4500
    await Agents(llm, max_prompt_tokens=budget).summarize(f.model_copy(update={"tests_added": f.tests_added * 8}))
    call = llm.calls[0]
    assert estimate_tokens(call["system"]) + estimate_tokens(call["user"]) <= budget
    assert '"tests_added_count":109' in call["user"] and '"file":"clip.go"' in call["user"]
