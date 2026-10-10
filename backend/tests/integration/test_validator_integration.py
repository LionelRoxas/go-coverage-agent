# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
import pytest

from app.gotools import read_module_info
from app.models import TestSnippet
from app.validator import ValidationKind, Validator

pytestmark = pytest.mark.integration

GOOD = 'func TestAbs(t *testing.T) {\n\tif Abs(-3) != 3 || Abs(2) != 2 {\n\t\tt.Fatal("abs")\n\t}\n}'
WRONG = 'func TestSqrtWrong(t *testing.T) {\n\tif r, _ := Sqrt(9); r != 4 {\n\t\tt.Fatalf("got %d", r)\n\t}\n}'
BROKEN = 'func TestBroken(t *testing.T) {\n\tvar x int = "s"\n\t_ = x\n}'


def snip(code: str) -> TestSnippet:
    return TestSnippet(test_plan=[], imports=["testing"], code=code, suspected_bugs=[])


async def setup(make_ws, tools_for):
    ws = make_ws()
    tools = tools_for(ws)
    pkgs = await tools.list_packages(["examples/**"])
    ws.seed_packages([(p.rel_dir, p.name) for p in pkgs])
    module, _ = read_module_info(ws.root)
    v = Validator(ws, tools, pkgs, await tools.funcs(), module)
    baseline = (await v.measure()).report
    assert baseline is not None and baseline.percent == 0.0
    return ws, v, baseline


async def test_accepts_good_tests(make_ws, tools_for):
    _, v, baseline = await setup(make_ws, tools_for)
    r = await v.validate("calc_test.go", "calc", snip(GOOD), baseline)
    assert r.accepted, r.output
    assert r.report.percent > 0


async def test_compile_error_is_classified(make_ws, tools_for):
    _, v, baseline = await setup(make_ws, tools_for)
    r = await v.validate("calc_test.go", "calc", snip(BROKEN), baseline)
    assert r.kind is ValidationKind.COMPILE_ERROR


async def test_failure_then_prune_keeps_good_test(make_ws, tools_for):
    _, v, baseline = await setup(make_ws, tools_for)
    r = await v.validate("calc_test.go", "calc", snip(GOOD + "\n\n" + WRONG), baseline)
    assert r.kind is ValidationKind.TEST_FAILURE and r.failed_tests == ["TestSqrtWrong"]
    r = await v.prune_and_check("calc_test.go", r.failed_tests, baseline, r.new_tests)
    assert r.accepted and r.new_tests == ["TestAbs"]


async def test_duplicate_coverage_is_no_gain(make_ws, tools_for):
    _, v, baseline = await setup(make_ws, tools_for)
    first = await v.validate("calc_test.go", "calc", snip(GOOD), baseline)
    again = snip(GOOD.replace("TestAbs", "TestAbsAgain"))
    r = await v.validate("calc_test.go", "calc", again, first.report)
    assert r.kind is ValidationKind.NO_GAIN


SILENT = 'func TestSqrtSilent(t *testing.T) {\n\t_, _ = Sqrt(9)\n\tt.Run("neg", func(st *testing.T) { Sqrt(-1) })\n}'


async def test_assertion_free_test_is_reported_then_pruned(make_ws, tools_for):
    ws, v, baseline = await setup(make_ws, tools_for)
    r = await v.validate("calc_test.go", "calc", snip(GOOD + "\n\n" + SILENT), baseline)
    assert r.kind is ValidationKind.NO_ASSERTIONS and r.no_assertions == ["TestSqrtSilent"], r.output
    r = await v.prune_and_check("calc_test.go", r.no_assertions, baseline, r.new_tests)
    assert r.accepted and r.new_tests == ["TestAbs"]
    assert "TestSqrtSilent" not in (ws.read("calc_test.go") or "")


async def test_only_assertion_free_tests_are_rejected(make_ws, tools_for):
    _, v, baseline = await setup(make_ws, tools_for)
    r = await v.validate("calc_test.go", "calc", snip(SILENT), baseline)
    assert r.kind is ValidationKind.NO_ASSERTIONS and "Every Test function must check its result" in r.output
