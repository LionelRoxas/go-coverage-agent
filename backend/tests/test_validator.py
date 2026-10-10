# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
import json
from pathlib import Path

import pytest

from app.config import Settings
from app.gotools import CommandResult, GoPackage
from app.models import CoverageReport, FuncInfo, FuncKey, TestSnippet
from app.validator import ValidationKind, ValidationResult, Validator, WorkspaceFull, parse_failed_tests
from app.workspace import Workspace

MOD = "example.com/m"
PKG = [GoPackage(import_path=MOD, rel_dir=".", name="m")]
FUNCS = [FuncInfo(key=FuncKey(file="a.go", name="F"), package="m", start_line=1, end_line=20, exported=True)]


def ok(out: str = "") -> CommandResult:
    return CommandResult(argv=[], exit_code=0, stdout=out, stderr="", duration_ms=1)


def fail(out: str) -> CommandResult:
    return CommandResult(argv=[], exit_code=1, stdout=out, stderr="", duration_ms=1)


class FakeTools:
    def __init__(self, compile_r=None, vet_r=None, test_r=None, profile="mode: set\n", merge_r=None, free=()):
        self.compile_r, self.vet_r, self.test_r = compile_r or ok(), vet_r or ok(), test_r or ok()
        self.merge_r, self.profile = merge_r or ok(), profile
        self.asserts_r = ok(json.dumps(list(free)))  # gohelper asserts: the assertion-free test names
        self.pruned: list[str] = []
        self.ran_tests = False

    async def merge(self, test_file, snippet): return self.merge_r
    async def asserts(self, go_file): return self.asserts_r
    async def prune(self, test_file, names):
        self.pruned = names
        return ok()
    async def compile(self, pkgs): return self.compile_r
    async def vet(self, pkgs): return self.vet_r

    async def test(self, pkgs, profile: Path):
        self.ran_tests = True
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


async def test_assertion_free_tests_are_reported_after_vet_and_before_running(tmp_path):
    tools = FakeTools(free=["TestB"])
    r = await make(tmp_path, tools).validate("a_test.go", "m", SNIP, prev())
    assert r.kind is ValidationKind.NO_ASSERTIONS and r.no_assertions == ["TestB"] and r.new_tests == ["TestA", "TestB"]
    assert not tools.ran_tests and "they are removed" in r.output
    assert r.event()["no_assertions"] == ["TestB"]
    assert "no_assertions" not in ValidationResult(ValidationKind.ACCEPTED).event()  # older events stay unchanged


async def test_all_assertion_free_tells_the_fixer_to_assert(tmp_path):
    r = await make(tmp_path, FakeTools(free=["TestA", "TestB"])).validate("a_test.go", "m", SNIP, prev())
    assert r.kind is ValidationKind.NO_ASSERTIONS and r.no_assertions == ["TestA", "TestB"]
    assert "Every Test function must check its result with t.Error" in r.output and "does not panic" in r.output


async def test_compile_errors_come_before_the_assertion_check(tmp_path):
    tools = FakeTools(compile_r=fail("undefined: Foo"), free=["TestA", "TestB"])
    r = await make(tmp_path, tools).validate("a_test.go", "m", SNIP, prev())
    assert r.kind is ValidationKind.COMPILE_ERROR and r.no_assertions == []


async def test_pruning_the_assertion_free_tests_checks_the_rest(tmp_path):
    profile = "mode: set\nexample.com/m/a.go:1.1,2.2 1 1\n"
    tools = FakeTools(profile=profile, free=["TestB"])
    v = make(tmp_path, tools)
    first = await v.validate("a_test.go", "m", SNIP, prev())
    r = await v.prune_and_check("a_test.go", first.no_assertions, prev(), first.new_tests)
    assert tools.pruned == ["TestB"] and r.accepted and r.new_tests == ["TestA"]


async def test_a_genuine_test_failure_is_not_cut_short(tmp_path):
    tools = FakeTools(test_r=fail("--- FAIL: TestB (0.00s)\n    a_test.go:3: got 1, want 2\nFAIL"))
    r = await make(tmp_path, tools).validate("a_test.go", "m", SNIP, prev())
    assert r.kind is ValidationKind.TEST_FAILURE and r.failed_tests == ["TestB"] and not r.cut_short


async def test_a_failure_message_that_mentions_a_kill_is_not_cut_short(tmp_path):
    tools = FakeTools(test_r=fail("--- FAIL: TestB (0.00s)\n    a_test.go:3: err = signal: killed, want nil\nFAIL"))
    r = await make(tmp_path, tools).validate("a_test.go", "m", SNIP, prev())
    assert r.kind is ValidationKind.TEST_FAILURE and r.failed_tests == ["TestB"] and not r.cut_short


@pytest.mark.parametrize("out,timed_out", [
    ("--- FAIL: TestB (0.00s)\npanic: test timed out after 30s\nrunning tests:\n\tTestA (30s)\nFAIL\n", False),
    ("--- FAIL: TestB (0.00s)\nsignal: killed\nFAIL\n", False),  # the OOM killer under mem_limit
    ("ok so far\n", True),  # TEST_TIMEOUT_S ended `go test` itself
    ("exit status 2\nFAIL\n", False),  # no test named as failing
], ids=["go-timeout", "killed", "stage-timeout", "unnamed"])
async def test_a_timed_out_or_killed_test_run_is_cut_short(tmp_path, out, timed_out):
    test_r = CommandResult(argv=[], exit_code=1, stdout=out, stderr="", duration_ms=1, timed_out=timed_out)
    tools = FakeTools(test_r=test_r)
    tools.settings = Settings(test_timeout_s=30)  # names the stage's timeout in the output
    r = await make(tmp_path, tools).validate("a_test.go", "m", SNIP, prev())
    assert r.kind is ValidationKind.TEST_FAILURE and r.cut_short


@pytest.mark.parametrize("stdout", ["", '["TestA"', "warning: something\n[]"], ids=["empty", "cut", "mixed"])
async def test_unreadable_asserts_output_rejects_only_the_candidate(tmp_path, stdout):
    tools = FakeTools()
    tools.asserts_r = ok(stdout)
    r = await make(tmp_path, tools).validate("a_test.go", "m", SNIP, prev())
    assert r.kind is ValidationKind.COMPILE_ERROR and "gohelper asserts: unreadable output" in r.output
    assert not tools.ran_tests


@pytest.mark.parametrize("stage", ["compile", "vet", "test"])
async def test_no_space_left_on_device_ends_the_job_instead_of_going_to_the_fixer(tmp_path, stage):
    full = fail("go: writing output: write /work/abc/scratch/go-build1/b001/x.a: no space left on device")
    tools = FakeTools(**{f"{stage}_r": full})
    with pytest.raises(WorkspaceFull) as e:
        await make(tmp_path, tools).validate("a_test.go", "m", SNIP, prev())
    assert "/work tmpfs is full" in str(e.value) and "no space left" in e.value.output


async def test_a_test_that_only_prints_the_enospc_text_is_an_ordinary_failure(tmp_path):
    out = "--- FAIL: TestB (0.00s)\n    a_test.go:3: got \"write x: no space left on device\", want nil\nFAIL\n"
    r = await make(tmp_path, FakeTools(test_r=fail(out))).validate("a_test.go", "m", SNIP, prev())
    assert r.kind is ValidationKind.TEST_FAILURE and r.failed_tests == ["TestB"]
