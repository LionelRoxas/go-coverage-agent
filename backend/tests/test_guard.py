# AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
from app.guard import check_snippet, render_snippet, test_names
from app.models import TestSnippet

MOD = "github.com/montanaflynn/stats"


def snip(code="func TestX(t *testing.T) {}", imports=("testing",)) -> TestSnippet:
    return TestSnippet(test_plan=[], imports=list(imports), code=code, suspected_bugs=[])


def test_clean_snippet_passes():
    assert check_snippet(snip(), MOD) == []


def test_denied_and_third_party_imports():
    problems = check_snippet(snip(imports=["testing", "os/exec", "net/http", "github.com/stretchr/testify/assert"]), MOD)
    assert any("os/exec" in p for p in problems)
    assert any("net/http" in p for p in problems)
    assert any("testify" in p for p in problems)


def test_module_own_packages_allowed():
    assert check_snippet(snip(imports=["testing", MOD + "/sub"]), MOD) == []


def test_code_must_not_contain_package_or_imports_or_build_tags():
    assert check_snippet(snip(code="package stats\nfunc TestX(t *testing.T) {}"), MOD)
    assert check_snippet(snip(code='import "os"\nfunc TestX(t *testing.T) {}'), MOD)
    assert check_snippet(snip(code="//go:build ignore\nfunc TestX(t *testing.T) {}"), MOD)


def test_requires_a_test_function_and_size_cap():
    assert check_snippet(snip(code="func helper() {}"), MOD)
    assert check_snippet(snip(code="func TestX(t *testing.T) {}\n" + "//" + "x" * 50_000), MOD)


def test_render_and_names():
    s = snip(code="func TestA(t *testing.T) {}\n\nfunc TestB(t *testing.T) {}", imports=["testing", "testing"])
    assert render_snippet("stats", s) == 'package stats\n\nimport (\n\t"testing"\n)\n\nfunc TestA(t *testing.T) {}\n\nfunc TestB(t *testing.T) {}\n'
    assert test_names(s.code) == ["TestA", "TestB"]
