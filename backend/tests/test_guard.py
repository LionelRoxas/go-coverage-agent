# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
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


def test_import_path_injection_rejected():
    problems = check_snippet(snip(imports=['testing"\n\t"os/exec']), MOD)
    assert any("invalid import path" in p for p in problems)


def test_comment_prefixed_import_rejected():
    assert check_snippet(snip(code='/* x */ import "os/exec"\nfunc TestX(t *testing.T) {}'), MOD)


def test_import_word_inside_raw_string_allowed():
    assert check_snippet(snip(code='var s = `\nimport x\n`\nfunc TestX(t *testing.T) {}'), MOD) == []


def test_cgo_and_directives_rejected():
    assert any("'C'" in p for p in check_snippet(snip(imports=["testing", "C"]), MOD))
    assert any("runtime/cgo" in p for p in check_snippet(snip(imports=["testing", "runtime/cgo"]), MOD))
    assert check_snippet(snip(code="//go:linkname x runtime.x\nfunc TestX(t *testing.T) {}"), MOD)
    assert check_snippet(snip(code="// #cgo LDFLAGS: -lm\nfunc TestX(t *testing.T) {}"), MOD)


def test_testmain_and_lowercase_not_test_functions():
    assert test_names("func TestMain(m *testing.M) {}\nfunc TestA(t *testing.T) {}") == ["TestA"]
    assert test_names("func Testlower(t *testing.T) {}") == []
    assert check_snippet(snip(code="func TestMain(m *testing.M) {}"), MOD)


def test_start_process_identifier_rejected_but_not_in_comments_or_strings():
    bad = snip(code="func TestX(t *testing.T) { os.StartProcess(\"x\", nil, nil) }")
    assert any("StartProcess" in p for p in check_snippet(bad, MOD))
    ok = snip(code="// os.StartProcess is banned" + chr(10) + "func TestX(t *testing.T) { _ = \"StartProcess\" }")
    assert not check_snippet(ok, MOD)


def test_proc_path_rejected_in_string_literals_but_not_comments():
    for lit in ('"/proc/self/environ"', "`/proc/1/environ`"):
        bad = snip(code=f"func TestX(t *testing.T) {{ _ = {lit} }}")
        assert any("/proc/" in p for p in check_snippet(bad, MOD)), lit
    ok = snip(code="// never read /proc/self" + chr(10) + "func TestX(t *testing.T) {}")
    assert not check_snippet(ok, MOD)
