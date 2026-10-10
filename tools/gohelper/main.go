// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
// Command gohelper gives the Python backend reliable Go source analysis and editing.
package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
)

const usage = `usage:
  gohelper funcs <dir>
  gohelper decls <dir>
  gohelper symbols <dir>
  gohelper asserts <go_file>
  gohelper mutate <go_file>
  gohelper merge <test_file> <snippet_file>
  gohelper prune <test_file> <TestName>...`

func main() {
	if err := run(os.Args[1:], os.Stdout); err != nil {
		fmt.Fprintln(os.Stderr, "gohelper:", err)
		os.Exit(1)
	}
}

func run(args []string, stdout io.Writer) error {
	if len(args) < 2 {
		return errors.New(usage)
	}
	switch args[0] {
	case "funcs":
		out, err := Funcs(args[1])
		if err != nil {
			return err
		}
		return json.NewEncoder(stdout).Encode(out)
	case "decls":
		out, err := Decls(args[1])
		if err != nil {
			return err
		}
		return json.NewEncoder(stdout).Encode(out)
	case "symbols":
		out, err := Symbols(args[1])
		if err != nil {
			return err
		}
		return json.NewEncoder(stdout).Encode(out)
	case "asserts":
		out, err := AssertionFree(args[1])
		if err != nil {
			return err
		}
		return json.NewEncoder(stdout).Encode(out)
	case "mutate":
		out, err := Mutate(args[1])
		if err != nil {
			return err
		}
		return json.NewEncoder(stdout).Encode(out)
	case "merge":
		if len(args) != 3 {
			return errors.New(usage)
		}
		return Merge(args[1], args[2])
	case "prune":
		return Prune(args[1], args[2:])
	default:
		return errors.New(usage)
	}
}
