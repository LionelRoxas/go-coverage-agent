// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
// Package mut is the mutation-test fixture: Add gets a strong test, IsAdult a weak one (tests/integration).
package mut

// Add returns a + b.
func Add(a, b int) int {
	return a + b
}

// IsAdult reports whether age is 18 or more.
func IsAdult(age int) bool {
	return age >= 18
}
