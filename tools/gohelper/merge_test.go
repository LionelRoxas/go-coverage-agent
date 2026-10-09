// AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
package main

import (
	"go/parser"
	"go/token"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func read(t *testing.T, path string) string {
	t.Helper()
	b, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	return string(b)
}

func mustParse(t *testing.T, src string) {
	t.Helper()
	if _, err := parser.ParseFile(token.NewFileSet(), "x.go", src, 0); err != nil {
		t.Fatalf("output does not parse: %v\n%s", err, src)
	}
}

func TestMerge_CreatesFileAndDropsUnusedImports(t *testing.T) {
	dir := t.TempDir()
	writeFile(t, dir, "snip.go", "package p\n\nimport (\n\t\"math\"\n\t\"testing\"\n)\n\n// TestMean checks the zero case.\nfunc TestMean(t *testing.T) {\n\tif Mean(nil) != 0 {\n\t\tt.Fatal(\"x\")\n\t}\n}\n")
	target := filepath.Join(dir, "a_test.go")

	if err := Merge(target, filepath.Join(dir, "snip.go")); err != nil {
		t.Fatal(err)
	}
	got := read(t, target)
	mustParse(t, got)
	if !strings.HasPrefix(got, "package p\n") || !strings.Contains(got, "func TestMean(") {
		t.Fatalf("unexpected output:\n%s", got)
	}
	if strings.Contains(got, `"math"`) {
		t.Fatalf("unused import kept:\n%s", got)
	}
	if !strings.Contains(got, "// TestMean checks the zero case.") {
		t.Fatalf("doc comment lost:\n%s", got)
	}
}

func TestMerge_AppendsAndKeepsExisting(t *testing.T) {
	dir := t.TempDir()
	writeFile(t, dir, "a_test.go", "package p\n\nimport \"testing\"\n\nfunc TestA(t *testing.T) {}\n")
	writeFile(t, dir, "snip.go", "package p\n\nimport (\n\t\"errors\"\n\t\"testing\"\n)\n\nfunc TestB(t *testing.T) {\n\t_ = errors.New(\"x\")\n}\n")
	target := filepath.Join(dir, "a_test.go")

	if err := Merge(target, filepath.Join(dir, "snip.go")); err != nil {
		t.Fatal(err)
	}
	got := read(t, target)
	mustParse(t, got)
	for _, want := range []string{"func TestA(", "func TestB(", `"errors"`} {
		if !strings.Contains(got, want) {
			t.Fatalf("missing %q in:\n%s", want, got)
		}
	}
	if strings.Count(got, `"testing"`) != 1 {
		t.Fatalf("testing import not deduplicated:\n%s", got)
	}
	if strings.Index(got, "func TestA(") > strings.Index(got, "func TestB(") {
		t.Fatalf("existing tests must stay first:\n%s", got)
	}
}

func TestMerge_RejectsDuplicateInSameFile(t *testing.T) {
	dir := t.TempDir()
	orig := "package p\n\nimport \"testing\"\n\nfunc TestA(t *testing.T) {}\n"
	writeFile(t, dir, "a_test.go", orig)
	writeFile(t, dir, "snip.go", "package p\n\nimport \"testing\"\n\nfunc TestA(t *testing.T) {}\n")

	err := Merge(filepath.Join(dir, "a_test.go"), filepath.Join(dir, "snip.go"))
	if err == nil || !strings.Contains(err.Error(), "duplicate declaration: TestA") {
		t.Fatalf("want duplicate error, got %v", err)
	}
	if read(t, filepath.Join(dir, "a_test.go")) != orig {
		t.Fatal("file modified on failure")
	}
}

func TestMerge_RejectsDuplicateFromSiblingTestFile(t *testing.T) {
	dir := t.TempDir()
	writeFile(t, dir, "b_test.go", "package p\n\nfunc approxEqual(a, b float64) bool { return a == b }\n")
	writeFile(t, dir, "snip.go", "package p\n\nfunc approxEqual(a, b float64) bool { return true }\n")

	err := Merge(filepath.Join(dir, "a_test.go"), filepath.Join(dir, "snip.go"))
	if err == nil || !strings.Contains(err.Error(), "duplicate declaration: approxEqual") {
		t.Fatalf("want duplicate error, got %v", err)
	}
	if _, statErr := os.Stat(filepath.Join(dir, "a_test.go")); !os.IsNotExist(statErr) {
		t.Fatal("file created on failure")
	}
}

func TestMerge_PackageMismatch(t *testing.T) {
	dir := t.TempDir()
	writeFile(t, dir, "a_test.go", "package p\n")
	writeFile(t, dir, "snip.go", "package q\n\nfunc TestQ() {}\n")
	err := Merge(filepath.Join(dir, "a_test.go"), filepath.Join(dir, "snip.go"))
	if err == nil || !strings.Contains(err.Error(), "package mismatch") {
		t.Fatalf("want package mismatch, got %v", err)
	}
}

func TestMerge_SnippetSyntaxError(t *testing.T) {
	dir := t.TempDir()
	writeFile(t, dir, "snip.go", "package p\n\nfunc TestBroken( {\n")
	err := Merge(filepath.Join(dir, "a_test.go"), filepath.Join(dir, "snip.go"))
	if err == nil || !strings.Contains(err.Error(), "snippet") {
		t.Fatalf("want snippet parse error, got %v", err)
	}
}

func TestPrune_RemovesNamedTestsAndUnusedImports(t *testing.T) {
	dir := t.TempDir()
	writeFile(t, dir, "a_test.go", "package p\n\nimport (\n\t\"errors\"\n\t\"testing\"\n)\n\nfunc TestA(t *testing.T) {\n\t_ = errors.New(\"x\")\n}\n\nfunc TestB(t *testing.T) {}\n")
	target := filepath.Join(dir, "a_test.go")

	if err := Prune(target, []string{"TestA"}); err != nil {
		t.Fatal(err)
	}
	got := read(t, target)
	mustParse(t, got)
	if strings.Contains(got, "TestA") || strings.Contains(got, `"errors"`) || !strings.Contains(got, "func TestB(") {
		t.Fatalf("unexpected prune result:\n%s", got)
	}
}

func TestMerge_KeepsVersionedImportLocalName(t *testing.T) {
	dir := t.TempDir()
	writeFile(t, dir, "snip.go", "package p\n\nimport (\n\t\"math/rand/v2\"\n\t\"testing\"\n)\n\nfunc TestRand(t *testing.T) {\n\t_ = rand.IntN(3)\n}\n")
	target := filepath.Join(dir, "a_test.go")

	if err := Merge(target, filepath.Join(dir, "snip.go")); err != nil {
		t.Fatal(err)
	}
	got := read(t, target)
	mustParse(t, got)
	if !strings.Contains(got, `"math/rand/v2"`) {
		t.Fatalf("versioned import dropped:\n%s", got)
	}
}

func TestMerge_PreservesPreambleOfExistingFile(t *testing.T) {
	dir := t.TempDir()
	header := "//go:build integration\n\n// Header comment\n"
	writeFile(t, dir, "a_test.go", header+"package p\n\nimport \"testing\"\n\nfunc TestA(t *testing.T) {}\n")
	writeFile(t, dir, "snip.go", "package p\n\nimport \"testing\"\n\nfunc TestB(t *testing.T) {}\n")
	target := filepath.Join(dir, "a_test.go")

	if err := Merge(target, filepath.Join(dir, "snip.go")); err != nil {
		t.Fatal(err)
	}
	got := read(t, target)
	mustParse(t, got)
	if !strings.HasPrefix(got, header+"package p\n") {
		t.Fatalf("preamble lost:\n%s", got)
	}
	if !strings.Contains(got, "func TestA(") || !strings.Contains(got, "func TestB(") {
		t.Fatalf("missing tests:\n%s", got)
	}
}

func TestPrune_PreservesPreambleOfExistingFile(t *testing.T) {
	dir := t.TempDir()
	header := "//go:build integration\n\n// Header comment\n"
	writeFile(t, dir, "a_test.go", header+"package p\n\nimport \"testing\"\n\nfunc TestA(t *testing.T) {}\n\nfunc TestB(t *testing.T) {}\n")
	target := filepath.Join(dir, "a_test.go")

	if err := Prune(target, []string{"TestA"}); err != nil {
		t.Fatal(err)
	}
	got := read(t, target)
	mustParse(t, got)
	if !strings.HasPrefix(got, header+"package p\n") {
		t.Fatalf("preamble lost:\n%s", got)
	}
	if strings.Contains(got, "TestA") || !strings.Contains(got, "func TestB(") {
		t.Fatalf("unexpected prune result:\n%s", got)
	}
}
