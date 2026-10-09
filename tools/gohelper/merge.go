// AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
package main

import (
	"bytes"
	"errors"
	"fmt"
	"go/ast"
	"go/format"
	"go/parser"
	"go/token"
	"io/fs"
	"os"
	"path"
	"path/filepath"
	"regexp"
	"strconv"
)

type importSpec struct{ Name, Path string }

var majorVersionElem = regexp.MustCompile(`^v[0-9]+$`)

// localName is the identifier the package is referenced by. For major-version
// paths such as "math/rand/v2" that is the preceding element ("rand").
func (s importSpec) localName() string {
	if s.Name != "" {
		return s.Name
	}
	dir, base := path.Split(s.Path)
	if majorVersionElem.MatchString(base) {
		if parent := path.Base(path.Clean(dir)); parent != "." && parent != "/" {
			return parent
		}
	}
	return base
}

// Merge appends the snippet's declarations and imports to testFile (creating it if needed).
// It never modifies existing declarations and fails on any identifier collision in the package's tests.
func Merge(testFile, snippetFile string) error {
	snipSrc, err := os.ReadFile(snippetFile)
	if err != nil {
		return err
	}
	fset := token.NewFileSet()
	snip, err := parser.ParseFile(fset, "snippet.go", snipSrc, parser.ParseComments)
	if err != nil {
		return fmt.Errorf("snippet: %w", err)
	}

	var base *ast.File
	var header []byte
	baseSrc, err := os.ReadFile(testFile)
	switch {
	case err == nil:
		base, err = parser.ParseFile(fset, testFile, baseSrc, parser.ParseComments)
		if err != nil {
			return fmt.Errorf("existing test file: %w", err)
		}
		if base.Name.Name != snip.Name.Name {
			return fmt.Errorf("package mismatch: %s has %q, snippet has %q", filepath.Base(testFile), base.Name.Name, snip.Name.Name)
		}
		header = preamble(fset, base, baseSrc)
	case errors.Is(err, fs.ErrNotExist):
		baseSrc = nil
	default:
		return err
	}

	existing, err := Decls(filepath.Dir(testFile))
	if err != nil && !errors.Is(err, fs.ErrNotExist) {
		return err
	}
	taken := map[string]bool{}
	for _, n := range existing {
		taken[n] = true
	}
	for _, n := range declNames(snip) {
		if taken[n] {
			return fmt.Errorf("duplicate declaration: %s", n)
		}
	}

	var imports []importSpec
	var body bytes.Buffer
	if base != nil {
		imports = append(imports, importsOf(base)...)
		writeDecls(&body, fset, base, baseSrc, nil)
	}
	imports = append(imports, importsOf(snip)...)
	writeDecls(&body, fset, snip, snipSrc, nil)

	out, err := tidy(render(header, snip.Name.Name, imports, body.Bytes()))
	if err != nil {
		return fmt.Errorf("merged result: %w", err)
	}
	return writeAtomic(testFile, out)
}

// Prune removes the named top-level functions from testFile and drops unused imports.
func Prune(testFile string, names []string) error {
	src, err := os.ReadFile(testFile)
	if err != nil {
		return err
	}
	fset := token.NewFileSet()
	f, err := parser.ParseFile(fset, testFile, src, parser.ParseComments)
	if err != nil {
		return err
	}
	drop := map[string]bool{}
	for _, n := range names {
		drop[n] = true
	}
	var body bytes.Buffer
	writeDecls(&body, fset, f, src, func(d ast.Decl) bool {
		fd, ok := d.(*ast.FuncDecl)
		return ok && fd.Recv == nil && drop[fd.Name.Name]
	})
	out, err := tidy(render(preamble(fset, f, src), f.Name.Name, importsOf(f), body.Bytes()))
	if err != nil {
		return err
	}
	return writeAtomic(testFile, out)
}

// preamble returns the source bytes before the package clause (build constraints, header comments).
func preamble(fset *token.FileSet, f *ast.File, src []byte) []byte {
	return src[:fset.Position(f.Package).Offset]
}

func importsOf(f *ast.File) []importSpec {
	var out []importSpec
	for _, s := range f.Imports {
		p, _ := strconv.Unquote(s.Path.Value)
		spec := importSpec{Path: p}
		if s.Name != nil {
			spec.Name = s.Name.Name
		}
		out = append(out, spec)
	}
	return out
}

// writeDecls copies each non-import declaration's source text (including its doc comment).
func writeDecls(buf *bytes.Buffer, fset *token.FileSet, f *ast.File, src []byte, skip func(ast.Decl) bool) {
	for _, decl := range f.Decls {
		if gd, ok := decl.(*ast.GenDecl); ok && gd.Tok == token.IMPORT {
			continue
		}
		if skip != nil && skip(decl) {
			continue
		}
		start := decl.Pos()
		switch d := decl.(type) {
		case *ast.FuncDecl:
			if d.Doc != nil {
				start = d.Doc.Pos()
			}
		case *ast.GenDecl:
			if d.Doc != nil {
				start = d.Doc.Pos()
			}
		}
		buf.Write(src[fset.Position(start).Offset:fset.Position(decl.End()).Offset])
		buf.WriteString("\n\n")
	}
}

func render(header []byte, pkg string, imports []importSpec, body []byte) []byte {
	var buf bytes.Buffer
	buf.Write(header)
	fmt.Fprintf(&buf, "package %s\n\n", pkg)
	seen := map[importSpec]bool{}
	var uniq []importSpec
	for _, s := range imports {
		if !seen[s] {
			seen[s] = true
			uniq = append(uniq, s)
		}
	}
	if len(uniq) > 0 {
		buf.WriteString("import (\n")
		for _, s := range uniq {
			if s.Name != "" {
				fmt.Fprintf(&buf, "\t%s %q\n", s.Name, s.Path)
			} else {
				fmt.Fprintf(&buf, "\t%q\n", s.Path)
			}
		}
		buf.WriteString(")\n\n")
	}
	buf.Write(body)
	return buf.Bytes()
}

// tidy drops imports whose package name is never referenced, then gofmts.
func tidy(src []byte) ([]byte, error) {
	fset := token.NewFileSet()
	f, err := parser.ParseFile(fset, "", src, parser.ParseComments)
	if err != nil {
		return nil, err
	}
	used := map[string]bool{}
	ast.Inspect(f, func(n ast.Node) bool {
		if sel, ok := n.(*ast.SelectorExpr); ok {
			if id, ok := sel.X.(*ast.Ident); ok {
				used[id.Name] = true
			}
		}
		return true
	})
	var keep []importSpec
	for _, s := range importsOf(f) {
		if s.Name == "_" || s.Name == "." || used[s.localName()] {
			keep = append(keep, s)
		}
	}
	var body bytes.Buffer
	writeDecls(&body, fset, f, src, nil)
	return format.Source(render(preamble(fset, f, src), f.Name.Name, keep, body.Bytes()))
}

func writeAtomic(dst string, data []byte) error {
	tmp, err := os.CreateTemp(filepath.Dir(dst), ".gohelper-*")
	if err != nil {
		return err
	}
	defer os.Remove(tmp.Name())
	if _, err := tmp.Write(data); err != nil {
		tmp.Close()
		return err
	}
	if err := tmp.Close(); err != nil {
		return err
	}
	if err := os.Chmod(tmp.Name(), 0o644); err != nil {
		return err
	}
	return os.Rename(tmp.Name(), dst)
}
