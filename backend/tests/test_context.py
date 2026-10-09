# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
import pytest

from app.agents.context import (ContextInputs, ContextProvider, ContextTooLarge, annotate_source,
                                go_version_rules, render_context, test_signatures)
from app.gotools import GoPackage, Symbol
from app.llm.client import estimate_tokens
from app.models import CoverageReport, FuncCoverage, FuncInfo, FuncKey, PlanItem
from app.workspace import Workspace


def test_go_version_rules_for_old_and_new_go():
    old = " ".join(go_version_rules("1.17"))
    assert "generics" in old and "slices" in old and "tc := tc" in old and "t.Parallel" in old
    new = " ".join(go_version_rules("1.22.1"))
    assert "generics" not in new and "slices" not in new and "tc := tc" not in new and "t.Parallel" in new


def test_annotate_source_marks_uncovered_and_keeps_doc_comment():
    lines = ["package p", "", "// Abs returns |x|.", "func Abs(x int) int {", "\tif x < 0 {", "\t\treturn -x", "\t}", "\treturn x", "}"]
    out = annotate_source(lines, 4, 9, [(5, 6)])
    assert out.splitlines()[0] == "// Abs returns |x|."
    assert "\t\treturn -x  // UNCOVERED" in out
    assert "\treturn x  // UNCOVERED" not in out


def test_test_signatures():
    src = "package p\n\nfunc TestA(t *testing.T) {\n}\n\nfunc helper() {}\n"
    assert test_signatures(src) == ["func TestA(t *testing.T)", "func helper()"]
    assert test_signatures(None) == []


def inputs(**over) -> ContextInputs:
    base = dict(module="m", package="p", go_version="1.17", source_file="a.go", test_file="a_test.go",
                targets=[("Abs", "func Abs() {}")], declared=["approxEqual"],
                referenced=["var ErrA = errors.New(\"a\")"] * 50, existing_tests=["func TestOld(t *testing.T)"])
    base.update(over)
    return ContextInputs(**base)


def test_render_context_includes_must_sections_and_trims_optional():
    full = render_context(inputs(referenced=["var ErrA = 1"]), 4000)
    for part in ("package p", "approxEqual", "func Abs() {}", "var ErrA = 1", "func TestOld"):
        assert part in full
    tight = render_context(inputs(), 400)
    assert "func Abs() {}" in tight and "approxEqual" in tight
    assert tight.count("ErrA") < 50


def test_render_context_raises_when_targets_do_not_fit():
    with pytest.raises(ContextTooLarge):
        render_context(inputs(targets=[("Huge", "x" * 10_000)]), 500)


class FakeTools:
    async def decls(self, rel_dir): return ["approxEqual"]


async def test_provider_builds_inputs(tmp_path):
    (tmp_path / "repo").mkdir()
    (tmp_path / "scratch").mkdir()
    ws = Workspace(tmp_path / "repo", tmp_path / "scratch")
    (ws.root / "a.go").write_text("package p\n\nimport \"errors\"\n\nvar ErrNeg = errors.New(\"neg\")\n\nfunc Abs(x int) (int, error) {\n\tif x < 0 {\n\t\treturn 0, ErrNeg\n\t}\n\treturn x, nil\n}\n")
    key = FuncKey(file="a.go", name="Abs")
    funcs = [FuncInfo(key=key, package="p", start_line=7, end_line=12, exported=True)]
    symbols = [Symbol(name="ErrNeg", kind="var", file="a.go", start_line=5, end_line=5)]
    report = CoverageReport(total_statements=3, covered_statements=0, percent=0, files=[], covered_block_ids=[],
                            functions=[FuncCoverage(key=key, statements=3, covered=0, uncovered_lines=[(8, 11)])])
    provider = ContextProvider(ws, FakeTools(), funcs, symbols, "m", "1.17", {".": GoPackage("m", ".", "p")})
    inp = await provider.inputs_for(PlanItem(file="a.go", functions=[key], uncovered_statements=3), report)
    assert inp.package == "p" and inp.test_file == "a_test.go" and inp.declared == ["approxEqual"]
    assert inp.targets[0][0] == "Abs" and "return 0, ErrNeg  // UNCOVERED" in inp.targets[0][1]
    assert inp.referenced == ['var ErrNeg = errors.New("neg")']


def test_existing_test_names_survive_a_tight_budget_before_related_declarations():
    tests = [f"func TestOld{i}(t *testing.T)" for i in range(5)]
    inp = inputs(existing_tests=tests)
    budget = estimate_tokens(render_context(inputs(referenced=[], existing_tests=tests), 10_000)) + 2
    tight = render_context(inp, budget)  # exactly room for the existing-tests section, none for related declarations
    assert "## Tests already in a_test.go" in tight and all(t in tight for t in tests)
    assert "ErrA" not in tight
    assert tight.index("## Tests already in") > tight.index("func Abs() {}")


def test_existing_test_names_keep_the_most_recent_when_only_some_fit():
    tests = [f"func TestOld{i}(t *testing.T)" for i in range(40)]
    base = render_context(inputs(referenced=[], existing_tests=[]), 10_000)
    tight = render_context(inputs(existing_tests=tests), estimate_tokens(base) + 40)
    assert "func TestOld39(t *testing.T)" in tight and "func TestOld0(t *testing.T)" not in tight
