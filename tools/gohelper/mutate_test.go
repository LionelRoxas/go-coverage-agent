// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
package main

import (
	"bytes"
	"encoding/json"
	"path/filepath"
	"testing"
)

func mutate(t *testing.T, name, src string) ([]Site, string) {
	t.Helper()
	dir := t.TempDir()
	writeFile(t, dir, name, src)
	file := filepath.Join(dir, name)
	got, err := Mutate(file)
	if err != nil {
		t.Fatal(err)
	}
	return got, file
}

func TestMutate_EachOperator(t *testing.T) {
	cases := []struct{ expr, original, mutated, op string }{
		{"a + b", "+", "-", "arithmetic"}, {"a - b", "-", "+", "arithmetic"},
		{"a * b", "*", "/", "arithmetic"}, {"a / b", "/", "*", "arithmetic"},
		{"a < b", "<", "<=", "boundary"}, {"a <= b", "<=", "<", "boundary"},
		{"a > b", ">", ">=", "boundary"}, {"a >= b", ">=", ">", "boundary"},
		{"a == b", "==", "!=", "equality"}, {"a != b", "!=", "==", "equality"},
		{"x && y", "&&", "||", "logical"}, {"x || y", "||", "&&", "logical"},
	}
	for _, tc := range cases {
		t.Run(tc.expr, func(t *testing.T) {
			src := "package p\n\nfunc f(a, b int, x, y bool) any {\n\treturn " + tc.expr + "\n}\n"
			got, file := mutate(t, "f.go", src)
			if len(got) != 1 {
				t.Fatalf("got %d sites, want 1: %+v", len(got), got)
			}
			s := got[0]
			want := Site{File: file, Line: 4, Col: len("\treturn a ") + 1, Offset: bytes.Index([]byte(src), []byte(tc.expr)) + 2,
				Original: tc.original, Mutated: tc.mutated, Op: tc.op}
			if s != want {
				t.Fatalf("got %+v, want %+v", s, want)
			}
			if src[s.Offset:s.Offset+len(s.Original)] != s.Original {
				t.Fatalf("offset %d does not point at %q", s.Offset, s.Original)
			}
		})
	}
}

func TestMutate_SkipsStringConcatenation(t *testing.T) {
	src := "package p\n\nfunc f(s string, n int) (string, string, int) {\n\treturn \"a\" + s, s + \"b\" + s, n + 1\n}\n"
	got, _ := mutate(t, "f.go", src)
	if len(got) != 1 || got[0].Original != "+" || src[got[0].Offset-2:got[0].Offset+3] != "n + 1" {
		t.Fatalf("want only the numeric +, got %+v", got)
	}
}

func TestMutate_SourceOrderAndNested(t *testing.T) {
	got, _ := mutate(t, "f.go", "package p\n\nfunc f(a, b int) bool {\n\treturn a+1 < b*2 && a != b\n}\n")
	var ops []string
	for _, s := range got {
		ops = append(ops, s.Original)
	}
	if want := []string{"&&", "<", "+", "*", "!="}; !equal(ops, want) {
		t.Fatalf("got %v, want %v", ops, want)
	}
}

func equal(a, b []string) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if a[i] != b[i] {
			return false
		}
	}
	return true
}

func TestMutate_SkipsTestFiles(t *testing.T) {
	got, _ := mutate(t, "f_test.go", "package p\n\nfunc f(a, b int) bool { return a < b }\n")
	if len(got) != 0 {
		t.Fatalf("want no sites in a test file, got %+v", got)
	}
}

func TestMutate_ParseErrorIsReported(t *testing.T) {
	dir := t.TempDir()
	writeFile(t, dir, "bad.go", "package p\nfunc {")
	if _, err := Mutate(filepath.Join(dir, "bad.go")); err == nil {
		t.Fatal("want a parse error")
	}
}

func TestRun_MutatePrintsJSON(t *testing.T) {
	dir := t.TempDir()
	writeFile(t, dir, "f.go", "package p\n\nfunc f(a, b int) bool { return a < b }\n")
	var out bytes.Buffer
	if err := run([]string{"mutate", filepath.Join(dir, "f.go")}, &out); err != nil {
		t.Fatal(err)
	}
	var sites []Site
	if err := json.Unmarshal(out.Bytes(), &sites); err != nil || len(sites) != 1 || sites[0].Mutated != "<=" {
		t.Fatalf("got %q (%v)", out.String(), err)
	}
}
