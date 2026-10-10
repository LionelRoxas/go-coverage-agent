// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
package main

import (
	"bytes"
	"path/filepath"
	"reflect"
	"strings"
	"testing"
)

func assertionFree(t *testing.T, src string) []string {
	t.Helper()
	dir := t.TempDir()
	writeFile(t, dir, "snip.go", "package p\n\nimport \"testing\"\n\n"+src)
	got, err := AssertionFree(filepath.Join(dir, "snip.go"))
	if err != nil {
		t.Fatal(err)
	}
	return got
}

func TestAssertionFree(t *testing.T) {
	cases := []struct {
		name string
		src  string
		want []string
	}{
		{"direct Errorf", "func TestA(t *testing.T) {\n\tif Mean(nil) != 0 {\n\t\tt.Errorf(\"bad\")\n\t}\n}\n", []string{}},
		{"if got != want Fatalf", "func TestA(t *testing.T) {\n\tgot, want := Mean(nil), 0.0\n\tif got != want {\n\t\tt.Fatalf(\"got %v want %v\", got, want)\n\t}\n}\n", []string{}},
		{"t.Run closure with renamed param", "func TestA(t *testing.T) {\n\tt.Run(\"x\", func(st *testing.T) {\n\t\tif Mean(nil) != 0 {\n\t\t\tst.Fatal(\"bad\")\n\t\t}\n\t})\n}\n", []string{}},
		{"Fail and FailNow count", "func TestA(t *testing.T) {\n\tt.Fail()\n}\nfunc TestB(tt *testing.T) {\n\ttt.FailNow()\n}\n", []string{}},
		{"helper receives t", "func check(t *testing.T, ok bool) {\n\tif !ok {\n\t\tt.Error(\"bad\")\n\t}\n}\nfunc TestA(t *testing.T) {\n\tcheck(t, Mean(nil) == 0)\n}\n", []string{}},
		{"helper receives the subtest t", "func TestA(t *testing.T) {\n\tt.Run(\"x\", func(sub *testing.T) {\n\t\tcheck(sub, true)\n\t})\n}\n", []string{}},
		{"no assertion", "func TestA(t *testing.T) {\n\t_ = Mean([]float64{1})\n\tt.Log(\"ran\")\n}\n", []string{"TestA"}},
		{"t.Run without assertions", "func TestA(t *testing.T) {\n\tt.Run(\"x\", func(t *testing.T) {\n\t\tMean(nil)\n\t})\n}\n", []string{"TestA"}},
		{"Error on another value is not an assertion", "func TestA(t *testing.T) {\n\terr := Do()\n\t_ = err.Error()\n}\n", []string{"TestA"}},
		{"empty body", "func TestA(t *testing.T) {}\n", []string{"TestA"}},
		{"only tests are checked, in source order", "func helper() {}\nfunc TestB(t *testing.T) {}\nfunc BenchmarkX(b *testing.B) {}\nfunc TestA(t *testing.T) {}\n", []string{"TestB", "TestA"}},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			if got := assertionFree(t, tc.src); !reflect.DeepEqual(got, tc.want) {
				t.Fatalf("got %v, want %v", got, tc.want)
			}
		})
	}
}

func TestAssertionFree_ParseErrorIsReported(t *testing.T) {
	dir := t.TempDir()
	writeFile(t, dir, "snip.go", "package p\n\nfunc TestA(t *testing.T) {\n")
	if _, err := AssertionFree(filepath.Join(dir, "snip.go")); err == nil {
		t.Fatal("expected a parse error")
	}
}

func TestRun_AssertsPrintsJSON(t *testing.T) {
	dir := t.TempDir()
	writeFile(t, dir, "snip.go", "package p\n\nimport \"testing\"\n\nfunc TestA(t *testing.T) {}\n")
	var out bytes.Buffer
	if err := run([]string{"asserts", filepath.Join(dir, "snip.go")}, &out); err != nil {
		t.Fatal(err)
	}
	if got := strings.TrimSpace(out.String()); got != `["TestA"]` {
		t.Fatalf("got %s", got)
	}
}
