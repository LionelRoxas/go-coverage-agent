// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
package main

import (
	"go/ast"
	"go/parser"
	"go/token"
	"strings"
)

// Site is one place a mutation test can swap an operator: the operator token at byte Offset becomes Mutated.
type Site struct {
	File     string `json:"file"`
	Line     int    `json:"line"`
	Col      int    `json:"col"`
	Offset   int    `json:"offset"`
	Original string `json:"original"`
	Mutated  string `json:"mutated"`
	Op       string `json:"op"`
}

// swaps holds the only mutations made: the replacement operator and the operator class.
var swaps = map[token.Token]struct {
	to token.Token
	op string
}{
	token.ADD: {token.SUB, "arithmetic"}, token.SUB: {token.ADD, "arithmetic"},
	token.MUL: {token.QUO, "arithmetic"}, token.QUO: {token.MUL, "arithmetic"},
	token.LSS: {token.LEQ, "boundary"}, token.LEQ: {token.LSS, "boundary"},
	token.GTR: {token.GEQ, "boundary"}, token.GEQ: {token.GTR, "boundary"},
	token.EQL: {token.NEQ, "equality"}, token.NEQ: {token.EQL, "equality"},
	token.LAND: {token.LOR, "logical"}, token.LOR: {token.LAND, "logical"},
}

// isString reports a string literal, or a `+` chain that contains one ("a" + b + c): no type checking beyond that.
func isString(e ast.Expr) bool {
	switch x := e.(type) {
	case *ast.BasicLit:
		return x.Kind == token.STRING
	case *ast.ParenExpr:
		return isString(x.X)
	case *ast.BinaryExpr:
		return x.Op == token.ADD && (isString(x.X) || isString(x.Y))
	}
	return false
}

// Mutate lists the mutation sites of a non-test Go file, in AST pre-order (none for a _test.go file).
func Mutate(file string) ([]Site, error) {
	out := []Site{}
	if strings.HasSuffix(file, "_test.go") {
		return out, nil
	}
	fset := token.NewFileSet()
	f, err := parser.ParseFile(fset, file, nil, 0)
	if err != nil {
		return nil, err
	}
	ast.Inspect(f, func(n ast.Node) bool {
		b, ok := n.(*ast.BinaryExpr)
		if !ok {
			return true
		}
		s, ok := swaps[b.Op]
		if !ok || (b.Op == token.ADD && (isString(b.X) || isString(b.Y))) {
			return true
		}
		pos := fset.Position(b.OpPos)
		out = append(out, Site{File: file, Line: pos.Line, Col: pos.Column, Offset: pos.Offset,
			Original: b.Op.String(), Mutated: s.to.String(), Op: s.op})
		return true
	})
	return out, nil
}
