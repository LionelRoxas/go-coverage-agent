// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
package main

import (
	"os"
	"path/filepath"
	"reflect"
	"testing"
)

func writeFile(t *testing.T, dir, name, src string) {
	t.Helper()
	path := filepath.Join(dir, name)
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte(src), 0o644); err != nil {
		t.Fatal(err)
	}
}

func TestFuncs_FunctionsAndMethods(t *testing.T) {
	dir := t.TempDir()
	writeFile(t, dir, "a.go", "package p\n\ntype T []float64\n\nfunc Mean(x []float64) float64 {\n\treturn 0\n}\n\nfunc (t T) Mean() float64 {\n\treturn Mean(t)\n}\n\nfunc (t *T) reset() {}\n")
	writeFile(t, dir, "a_test.go", "package p\n\nfunc helper() {}\n")

	got, err := Funcs(dir)
	if err != nil {
		t.Fatal(err)
	}
	want := []FuncInfo{
		{File: "a.go", Package: "p", Receiver: "", Name: "Mean", StartLine: 5, EndLine: 7, Exported: true},
		{File: "a.go", Package: "p", Receiver: "T", Name: "Mean", StartLine: 9, EndLine: 11, Exported: true},
		{File: "a.go", Package: "p", Receiver: "T", Name: "reset", StartLine: 13, EndLine: 13, Exported: false},
	}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("got  %+v\nwant %+v", got, want)
	}
}

func TestFuncs_WalksSubdirsSkipsVendorTestdataHidden(t *testing.T) {
	dir := t.TempDir()
	writeFile(t, dir, "sub/b.go", "package sub\n\nfunc B() {}\n")
	writeFile(t, dir, "vendor/v/v.go", "package v\n\nfunc V() {}\n")
	writeFile(t, dir, "testdata/x.go", "package x\n\nfunc X() {}\n")
	writeFile(t, dir, ".hidden/h.go", "package h\n\nfunc H() {}\n")

	got, err := Funcs(dir)
	if err != nil {
		t.Fatal(err)
	}
	if len(got) != 1 || got[0].File != "sub/b.go" || got[0].Name != "B" {
		t.Fatalf("unexpected result: %+v", got)
	}
}

func TestFuncs_EmptyDirReturnsEmptySlice(t *testing.T) {
	got, err := Funcs(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	if got == nil || len(got) != 0 {
		t.Fatalf("want empty non-nil slice, got %#v", got)
	}
}

func TestDecls_TopLevelTestIdentifiers(t *testing.T) {
	dir := t.TempDir()
	writeFile(t, dir, "a_test.go", "package p\n\nimport \"testing\"\n\nvar tol = 1e-9\n\ntype tc struct{}\n\nconst k = 1\n\nvar _ = k\n\nfunc approxEqual(a, b float64) bool { return true }\n\nfunc TestX(t *testing.T) {}\n\nfunc (tc) m() {}\n")
	writeFile(t, dir, "b.go", "package p\n\nfunc Real() {}\n")
	writeFile(t, dir, "sub/c_test.go", "package sub\n\nfunc TestNested() {}\n")

	got, err := Decls(dir)
	if err != nil {
		t.Fatal(err)
	}
	want := []string{"TestX", "approxEqual", "k", "tc", "tol"}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("got %v want %v", got, want)
	}
}
