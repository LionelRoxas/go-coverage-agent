# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
from pathlib import Path

from app.gotools import CommandResult, GoPackage
from app.models import CoverageReport, FuncInfo, FuncKey, TestSnippet
from app.validator import ValidationKind, Validator, parse_failed_tests
from app.workspace import Workspace

MOD = "example.com/m"
PKG = [GoPackage(import_path=MOD, rel_dir=".", name="m")]
FUNCS = [FuncInfo(key=FuncKey(file="a.go", name="F"), package="m", start_line=1, end_line=20, exported=True)]


def ok(out: str = "") -> CommandResult:
    return CommandResult(argv=[], exit_code=0, stdout=out, stderr="", duration_ms=1)


def fail(out: str) -> CommandResult:
    return CommandResult(argv=[], exit_code=1, stdout=out, stderr="", duration_ms=1)


class FakeTools:
    def __init__(self, compile_r=None, vet_r=None, test_r=None, profile="mode: set\n", merge_r=None):
        self.compile_r, self.vet_r, self.test_r = compile_r or ok(), vet_r or ok(), test_r or ok()
        self.merge_r, self.profile = merge_r or ok(), profile
        self.pruned: list[str] = []

    async def merge(self, test_file, snippet): return self.merge_r
    async def prune(self, test_file, names):
        self.pruned = names
        return ok()
    async def compile(self, pkgs): return self.compile_r
    async def vet(self, pkgs): return self.vet_r

    async def test(self, pkgs, profile: Path):
        profile.write_text(self.profile)
        return self.test_r


def make(tmp_path, tools) -> Validator:
    (tmp_path / "repo").mkdir(parents=True)
    (tmp_path / "scratch").mkdir(parents=True)
    return Validator(Workspace(tmp_path / "repo", tmp_path / "scratch"), tools, PKG, FUNCS, MOD)


def prev(ids=()) -> CoverageReport:
    return CoverageReport(total_statements=4, covered_statements=len(ids), percent=0, files=[], functions=[],
                          covered_block_ids=list(ids))


SNIP = TestSnippet(test_plan=[], imports=["testing"], code="func TestA(t *testing.T) {}\nfunc TestB(t *testing.T) {}", suspected_bugs=[])


def test_parse_failed_tests_top_level_unique():
    out = "--- FAIL: TestA (0.00s)\n    --- FAIL: TestA/neg (0.00s)\n--- FAIL: TestB (0.00s)\n--- FAIL: TestA (0.00s)\n"
    assert parse_failed_tests(out) == ["TestA", "TestB"]


async def test_guard_rejection_short_circuits(tmp_path):
    bad = SNIP.model_copy(update={"imports": ["os/exec"]})
    r = await make(tmp_path, FakeTools()).validate("a_test.go", "m", bad, prev())
    assert r.kind is ValidationKind.GUARD_REJECTED


async def test_merge_failure_is_compile_error(tmp_path):
    r = await make(tmp_path, FakeTools(merge_r=fail("duplicate declaration: TestA"))).validate("a_test.go", "m", SNIP, prev())
    assert r.kind is ValidationKind.COMPILE_ERROR and "duplicate" in r.output


async def test_compile_then_vet_classification(tmp_path):
    r = await make(tmp_path, FakeTools(compile_r=fail("undefined: Foo"))).validate("a_test.go", "m", SNIP, prev())
    assert r.kind is ValidationKind.COMPILE_ERROR
    r = await make(tmp_path / "2", FakeTools(vet_r=fail("printf: bad verb"))).validate("a_test.go", "m", SNIP, prev())
    assert r.kind is ValidationKind.VET_ERROR


async def test_test_failure_lists_failed_tests(tmp_path):
    tools = FakeTools(test_r=fail("--- FAIL: TestB (0.00s)\nFAIL"))
    r = await make(tmp_path, tools).validate("a_test.go", "m", SNIP, prev())
    assert r.kind is ValidationKind.TEST_FAILURE
    assert r.failed_tests == ["TestB"] and r.new_tests == ["TestA", "TestB"]


async def test_no_gain_when_nothing_new_or_regression(tmp_path):
    profile = "mode: set\nexample.com/m/a.go:1.1,2.2 1 1\n"
    r = await make(tmp_path, FakeTools(profile=profile)).validate("a_test.go", "m", SNIP, prev(["a.go:1.1,2.2"]))
    assert r.kind is ValidationKind.NO_GAIN
    r = await make(tmp_path / "2", FakeTools(profile=profile)).validate("a_test.go", "m", SNIP, prev(["a.go:5.1,6.2"]))
    assert r.kind is ValidationKind.NO_GAIN  # lost a previously covered block


async def test_accepted_returns_new_report(tmp_path):
    profile = "mode: set\nexample.com/m/a.go:1.1,2.2 1 1\nexample.com/m/a.go:3.1,4.2 1 0\n"
    r = await make(tmp_path, FakeTools(profile=profile)).validate("a_test.go", "m", SNIP, prev())
    assert r.accepted and r.report.percent == 50.0


async def test_prune_and_check_drops_failed_names(tmp_path):
    profile = "mode: set\nexample.com/m/a.go:1.1,2.2 1 1\n"
    tools = FakeTools(profile=profile)
    r = await make(tmp_path, tools).prune_and_check("a_test.go", ["TestB"], prev(), ["TestA", "TestB"])
    assert tools.pruned == ["TestB"] and r.accepted and r.new_tests == ["TestA"]


async def test_no_gain_messages_distinguish_loss_from_equal(tmp_path):
    profile = "mode: set\nexample.com/m/a.go:1.1,2.2 1 1\n"
    r = await make(tmp_path, FakeTools(profile=profile)).validate("a_test.go", "m", SNIP, prev(["a.go:5.1,6.2"]))
    assert r.output == "the new tests made previously covered statements uncovered"
    r = await make(tmp_path / "2", FakeTools(profile=profile)).validate("a_test.go", "m", SNIP, prev(["a.go:1.1,2.2"]))
    assert r.output == "the new tests executed no previously uncovered statements"


async def test_compile_and_vet_errors_name_the_declarations_their_lines_point_at(tmp_path):
    merged = ("package m\n\nimport \"testing\"\n\nfunc TestOld(t *testing.T) {}\n\n"
              "func TestA(t *testing.T) {\n\tx := 1\n}\n\nfunc TestB(t *testing.T) {\n\tFoo()\n}\n")
    tools = FakeTools(compile_r=fail("# m\n./a_test.go:12:2: undefined: Foo\n./a_test.go:8:2: declared and not used: x"))
    v = make(tmp_path, tools)
    v.ws.write_test("a_test.go", merged)
    r = await v.validate("a_test.go", "m", SNIP, prev())
    assert r.kind is ValidationKind.COMPILE_ERROR and r.error_decls == ["TestB", "TestA"]
    v2 = make(tmp_path / "2", FakeTools(vet_r=fail("vet: other_test.go:12:2: x")))
    v2.ws.write_test("a_test.go", merged)
    assert (await v2.validate("a_test.go", "m", SNIP, prev())).error_decls == []


async def test_snippet_parse_errors_name_the_snippet_declaration(tmp_path):
    tools = FakeTools(merge_r=fail("gohelper: snippet: snippet.go:8:30: expected ';', found 'EOF'"))
    r = await make(tmp_path, tools).validate("a_test.go", "m", SNIP, prev())
    assert r.kind is ValidationKind.COMPILE_ERROR and r.error_decls == ["TestB"]
