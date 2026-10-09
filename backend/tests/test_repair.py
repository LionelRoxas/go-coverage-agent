# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
from app.agents.repair import mechanical_repair
from tests.fakes import snippet


def test_adds_missing_stdlib_imports():
    s = snippet("func TestA(t *testing.T) { _ = math.Abs(1); sort.Ints(nil) }")
    out = "./a_test.go:3:1: undefined: math" + chr(10) + "./a_test.go:3:2: undefined: sort"
    fixed, description = mechanical_repair(s, out, "stats")
    assert fixed.imports == ["testing", "math", "sort"] and fixed.code == s.code
    assert description == "added imports math, sort"


def test_single_import_description():
    _, description = mechanical_repair(snippet("x"), "undefined: strings", "p")
    assert description == "added import strings"


def test_maps_rand_to_math_rand_and_keeps_existing_imports():
    fixed, _ = mechanical_repair(snippet("x", imports=("testing", "math")), "undefined: rand" + chr(10) + "undefined: math", "p")
    assert fixed.imports == ["testing", "math", "math/rand"]


def test_strips_self_package_qualifier_only_where_it_qualifies():
    s = snippet("func TestA(t *testing.T) { stats.Mean(nil); x.stats.y = 1; mystats.Z() }")
    fixed, description = mechanical_repair(s, "./a_test.go:3:1: undefined: stats", "stats")
    assert fixed.code == "func TestA(t *testing.T) { Mean(nil); x.stats.y = 1; mystats.Z() }"
    assert fixed.imports == ["testing"]
    assert description == "removed the `stats.` qualifier"


def test_combined_description():
    s = snippet("func TestA(t *testing.T) { stats.Mean(nil); _ = math.Abs(1) }")
    _, description = mechanical_repair(s, "undefined: stats" + chr(10) + "undefined: math", "stats")
    assert description == "added import math; removed the `stats.` qualifier"


def test_returns_none_when_nothing_is_mechanical():
    assert mechanical_repair(snippet("x"), "./a_test.go:3:1: undefined: RegIncBeta", "stats") is None
    assert mechanical_repair(snippet("x", imports=("testing", "errors")), "undefined: errors", "p") is None
    assert mechanical_repair(snippet("x"), "declared and not used: v", "p") is None


def test_qualifier_stripping_preserves_comments_and_literals():
    code = """func TestA(t *testing.T) {
	s := "stats.Mean"
	// stats.Mean here
	r := 's'
	_ = stats.Mean(x) /* stats.Mean */
	_ = `stats.Mean`
}"""
    fixed, _ = mechanical_repair(snippet(code), "undefined: stats", "stats")
    assert fixed.code == code.replace("_ = stats.Mean(x)", "_ = Mean(x)")


DUP = "gohelper: duplicate declaration: TestCaret_Uncovered"


def test_renames_a_duplicate_test_declaration_to_the_first_free_suffix():
    code = "// TestCaret_Uncovered covers the caret.\nfunc TestCaret_Uncovered(t *testing.T) {\n\tt.Log(\"TestCaret_Uncovered\")\n}\n"
    fixed, description = mechanical_repair(snippet(code), DUP, "semver", taken=["TestCaret_Uncovered", "TestCaret_Uncovered_2"])
    assert fixed.code == code.replace("func TestCaret_Uncovered(", "func TestCaret_Uncovered_3(")
    assert description == "renamed duplicate test TestCaret_Uncovered to TestCaret_Uncovered_3"


def test_rename_skips_names_used_elsewhere_in_the_snippet_and_is_word_bounded():
    code = ("func TestCaret_Uncovered(t *testing.T) {}\n\nfunc TestCaret_Uncovered_2(t *testing.T) {}\n\n"
            "func TestCaret_UncoveredMore(t *testing.T) {}\n")
    fixed, description = mechanical_repair(snippet(code), DUP, "semver", taken=["TestCaret_Uncovered"])
    assert fixed.code == code.replace("func TestCaret_Uncovered(", "func TestCaret_Uncovered_3(")
    assert description == "renamed duplicate test TestCaret_Uncovered to TestCaret_Uncovered_3"


def test_renames_benchmark_fuzz_and_example_duplicates():
    for name, sig in (("BenchmarkX", "(b *testing.B)"), ("FuzzX", "(f *testing.F)"), ("ExampleX", "()")):
        fixed, description = mechanical_repair(snippet(f"func {name}{sig} {{}}"), f"duplicate declaration: {name}", "p",
                                               taken=[name])
        assert fixed.code == f"func {name}_2{sig} {{}}" and description == f"renamed duplicate test {name} to {name}_2"


def test_duplicate_is_left_to_the_fixer_when_not_renameable():
    helper = "func approxEqual(a, b float64) bool { return a == b }"
    assert mechanical_repair(snippet(helper), "duplicate declaration: approxEqual", "p", taken=["approxEqual"]) is None
    referenced = "func TestA(t *testing.T) {}\n\nfunc TestB(t *testing.T) { TestA(t) }"
    assert mechanical_repair(snippet(referenced), "duplicate declaration: TestA", "p", taken=["TestA"]) is None
    absent = "func TestB(t *testing.T) {}"
    assert mechanical_repair(snippet(absent), "duplicate declaration: TestA", "p", taken=["TestA"]) is None
