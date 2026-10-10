// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
package main

import (
	"go/ast"
	"go/parser"
	"go/token"
	"strings"
	"unicode"
	"unicode/utf8"
)

// failMethods are the *testing.T methods that make a test fail: calling one is an assertion.
var failMethods = map[string]bool{"Error": true, "Errorf": true, "Fatal": true, "Fatalf": true, "Fail": true, "FailNow": true}

// isTestName mirrors the backend guard: Test followed by an upper-case letter, a digit or '_', never TestMain.
func isTestName(name string) bool {
	rest, ok := strings.CutPrefix(name, "Test")
	if !ok || rest == "" || name == "TestMain" {
		return false
	}
	r, _ := utf8.DecodeRuneInString(rest)
	return unicode.IsUpper(r) || unicode.IsDigit(r) || r == '_'
}

// isTestingT reports whether a parameter type is *<pkg>.T (*testing.T under any import name).
func isTestingT(expr ast.Expr) bool {
	star, ok := expr.(*ast.StarExpr)
	if !ok {
		return false
	}
	sel, ok := star.X.(*ast.SelectorExpr)
	if !ok {
		return false
	}
	_, ok = sel.X.(*ast.Ident)
	return ok && sel.Sel.Name == "T"
}

func tParams(ft *ast.FuncType, into map[string]bool) {
	if ft == nil || ft.Params == nil {
		return
	}
	for _, field := range ft.Params.List {
		if !isTestingT(field.Type) {
			continue
		}
		for _, n := range field.Names {
			if n.Name != "_" {
				into[n.Name] = true
			}
		}
	}
}

// asserts reports whether a test body checks something: it calls Error/Errorf/Fatal/Fatalf/Fail/FailNow on its
// *testing.T parameter or on the *testing.T parameter of a closure inside it (t.Run subtests, whatever the
// parameter is called), or it passes one of those values to another function (a helper).
func asserts(fd *ast.FuncDecl) bool {
	names := map[string]bool{}
	tParams(fd.Type, names)
	ast.Inspect(fd.Body, func(n ast.Node) bool {
		if lit, ok := n.(*ast.FuncLit); ok {
			tParams(lit.Type, names)
		}
		return true
	})
	if len(names) == 0 {
		return false
	}
	found := false
	ast.Inspect(fd.Body, func(n ast.Node) bool {
		call, ok := n.(*ast.CallExpr)
		if !ok || found {
			return !found
		}
		if sel, ok := call.Fun.(*ast.SelectorExpr); ok && failMethods[sel.Sel.Name] {
			if id, ok := sel.X.(*ast.Ident); ok && names[id.Name] {
				found = true
				return false
			}
		}
		for _, arg := range call.Args {
			if id, ok := arg.(*ast.Ident); ok && names[id.Name] {
				found = true
				return false
			}
		}
		return true
	})
	return found
}

// AssertionFree lists, in source order, the top-level Test functions of a Go file that never check a result.
func AssertionFree(file string) ([]string, error) {
	f, err := parser.ParseFile(token.NewFileSet(), file, nil, 0)
	if err != nil {
		return nil, err
	}
	out := []string{}
	for _, decl := range f.Decls {
		fd, ok := decl.(*ast.FuncDecl)
		if !ok || fd.Recv != nil || fd.Body == nil || !isTestName(fd.Name.Name) {
			continue
		}
		if !asserts(fd) {
			out = append(out, fd.Name.Name)
		}
	}
	return out, nil
}
