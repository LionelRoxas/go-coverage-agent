// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
package main

import (
	"fmt"
	"go/ast"
	"go/parser"
	"go/token"
	"io/fs"
	"path/filepath"
	"strings"
)

// Symbol locates a top-level type, var or const declaration.
type Symbol struct {
	Name      string `json:"name"`
	Kind      string `json:"kind"`
	File      string `json:"file"`
	StartLine int    `json:"start_line"`
	EndLine   int    `json:"end_line"`
}

// Symbols lists top-level type/var/const declarations in non-test files under root.
func Symbols(root string) ([]Symbol, error) {
	out := []Symbol{}
	fset := token.NewFileSet()
	err := filepath.WalkDir(root, func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if d.IsDir() {
			if skipDir(root, path, d.Name()) {
				return filepath.SkipDir
			}
			return nil
		}
		if !strings.HasSuffix(path, ".go") || strings.HasSuffix(path, "_test.go") {
			return nil
		}
		f, err := parser.ParseFile(fset, path, nil, parser.ParseComments|parser.SkipObjectResolution)
		if err != nil {
			return fmt.Errorf("parse %s: %w", path, err)
		}
		rel, err := filepath.Rel(root, path)
		if err != nil {
			return err
		}
		rel = filepath.ToSlash(rel)
		for _, decl := range f.Decls {
			gd, ok := decl.(*ast.GenDecl)
			if !ok || gd.Tok == token.IMPORT {
				continue
			}
			for _, spec := range gd.Specs {
				start, end := spec.Pos(), spec.End()
				if !gd.Lparen.IsValid() {
					start, end = gd.Pos(), gd.End()
					if gd.Doc != nil {
						start = gd.Doc.Pos()
					}
				}
				for _, name := range specNames(spec) {
					out = append(out, Symbol{Name: name, Kind: gd.Tok.String(), File: rel,
						StartLine: fset.Position(start).Line, EndLine: fset.Position(end).Line})
				}
			}
		}
		return nil
	})
	return out, err
}

func specNames(spec ast.Spec) []string {
	switch s := spec.(type) {
	case *ast.TypeSpec:
		return []string{s.Name.Name}
	case *ast.ValueSpec:
		var names []string
		for _, n := range s.Names {
			if n.Name != "_" {
				names = append(names, n.Name)
			}
		}
		return names
	}
	return nil
}
