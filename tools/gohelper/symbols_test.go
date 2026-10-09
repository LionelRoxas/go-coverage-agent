// AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
package main

import (
	"reflect"
	"testing"
)

func TestSymbols_TypesVarsConsts(t *testing.T) {
	dir := t.TempDir()
	writeFile(t, dir, "e.go", "package p\n\nimport \"errors\"\n\n// T is data.\ntype T []float64\n\nvar (\n\tErrA = errors.New(\"a\")\n\tErrB = errors.New(\"b\")\n)\n\nconst k = 1\n\nfunc F() {}\n")
	writeFile(t, dir, "e_test.go", "package p\n\nvar ignored = 1\n")

	got, err := Symbols(dir)
	if err != nil {
		t.Fatal(err)
	}
	want := []Symbol{
		{Name: "T", Kind: "type", File: "e.go", StartLine: 5, EndLine: 6},
		{Name: "ErrA", Kind: "var", File: "e.go", StartLine: 9, EndLine: 9},
		{Name: "ErrB", Kind: "var", File: "e.go", StartLine: 10, EndLine: 10},
		{Name: "k", Kind: "const", File: "e.go", StartLine: 13, EndLine: 13},
	}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("got  %+v\nwant %+v", got, want)
	}
}
