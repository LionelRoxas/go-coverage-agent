# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
from app.agents.repair import mechanical_repair
from tests.fakes import snippet


def test_adds_missing_stdlib_imports():
    s = snippet("func TestA(t *testing.T) { _ = math.Abs(1); sort.Ints(nil) }")
    out = "./a_test.go:3:1: undefined: math" + chr(10) + "./a_test.go:3:2: undefined: sort"
    fixed = mechanical_repair(s, out, "stats")
    assert fixed.imports == ["testing", "math", "sort"] and fixed.code == s.code


def test_maps_rand_to_math_rand_and_keeps_existing_imports():
    fixed = mechanical_repair(snippet("x", imports=("testing", "math")), "undefined: rand" + chr(10) + "undefined: math", "p")
    assert fixed.imports == ["testing", "math", "math/rand"]


def test_strips_self_package_qualifier_only_where_it_qualifies():
    s = snippet("func TestA(t *testing.T) { stats.Mean(nil); x.stats.y = 1; mystats.Z() }")
    fixed = mechanical_repair(s, "./a_test.go:3:1: undefined: stats", "stats")
    assert fixed.code == "func TestA(t *testing.T) { Mean(nil); x.stats.y = 1; mystats.Z() }"
    assert fixed.imports == ["testing"]


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
    fixed = mechanical_repair(snippet(code), "undefined: stats", "stats")
    assert fixed.code == code.replace("_ = stats.Mean(x)", "_ = Mean(x)")
