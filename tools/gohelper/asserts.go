// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
package main

import (
	"go/ast"
	"go/parser"
	"go/token"
	"maps"
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

// isTestingT reports whether a type is *<pkg>.T or <pkg>.TB (testing.T / testing.TB under any import name).
func isTestingT(expr ast.Expr) bool {
	want := "TB"
	if star, ok := expr.(*ast.StarExpr); ok {
		expr, want = star.X, "T"
	}
	sel, ok := expr.(*ast.SelectorExpr)
	if !ok {
		return false
	}
	_, ok = sel.X.(*ast.Ident)
	return ok && sel.Sel.Name == want
}

// scope returns the names visible inside a function: the enclosing ones, minus those its parameters shadow,
// plus its own testing.T / testing.TB parameters.
func scope(outer map[string]bool, ft *ast.FuncType) map[string]bool {
	names := maps.Clone(outer)
	if ft == nil || ft.Params == nil {
		return names
	}
	for _, field := range ft.Params.List {
		for _, n := range field.Names {
			delete(names, n.Name)
			if n.Name != "_" && isTestingT(field.Type) {
				names[n.Name] = true
			}
		}
	}
	return names
}

func tracked(names map[string]bool, e ast.Expr) bool {
	id, ok := e.(*ast.Ident)
	return ok && names[id.Name]
}

// bind updates names for `lhs := rhs`, `lhs = rhs` or `var lhs = rhs`: an alias of a tracked value is tracked
// (tb := t, var tb testing.TB = t), and a new declaration of anything else shadows the name (x := errors.New("x")).
func bind(names map[string]bool, lhs, rhs []ast.Expr, declares bool) {
	for i, l := range lhs {
		id, ok := l.(*ast.Ident)
		if !ok || id.Name == "_" {
			continue
		}
		if len(lhs) == len(rhs) && tracked(names, rhs[i]) {
			names[id.Name] = true
		} else if declares {
			delete(names, id.Name)
		}
	}
}

// checks walks a function body in source order with the testing.T values in scope. It reports an assertion
// when one of them has Error/Errorf/Fatal/Fatalf/Fail/FailNow selected (called, or taken as a method value such
// as `check := t.Errorf`), is passed to a function (a helper), or is stored in a composite literal (`h{t: t}`).
// A function literal is walked with its own scope, so the `*testing.T` parameter of one closure never makes an
// unrelated `x.Error()` elsewhere count.
func checks(body ast.Node, names map[string]bool) bool {
	found := false
	ast.Inspect(body, func(n ast.Node) bool {
		if found {
			return false
		}
		switch x := n.(type) {
		case *ast.FuncLit:
			found = checks(x.Body, scope(names, x.Type))
			return false
		case *ast.AssignStmt: // the right-hand side is evaluated before the names it declares exist
			found = anyChecks(names, x.Rhs) || anyChecks(names, x.Lhs)
			bind(names, x.Lhs, x.Rhs, x.Tok == token.DEFINE)
			return false
		case *ast.ValueSpec:
			found = anyChecks(names, x.Values)
			lhs := make([]ast.Expr, len(x.Names))
			for i, id := range x.Names {
				lhs[i] = id
			}
			bind(names, lhs, x.Values, true)
			return false
		case *ast.SelectorExpr:
			found = failMethods[x.Sel.Name] && tracked(names, x.X)
		case *ast.CallExpr:
			for _, arg := range x.Args {
				found = found || tracked(names, arg)
			}
		case *ast.CompositeLit:
			for _, el := range x.Elts {
				if kv, ok := el.(*ast.KeyValueExpr); ok {
					el = kv.Value
				}
				found = found || tracked(names, el)
			}
		}
		return !found
	})
	return found
}

func anyChecks(names map[string]bool, exprs []ast.Expr) bool {
	for _, e := range exprs {
		if checks(e, names) {
			return true
		}
	}
	return false
}

// asserts reports whether a test body checks something with its testing.T (see checks).
func asserts(fd *ast.FuncDecl) bool {
	return checks(fd.Body, scope(map[string]bool{}, fd.Type))
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
