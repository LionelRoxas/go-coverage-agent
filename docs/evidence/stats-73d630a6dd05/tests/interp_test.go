package stats

import (
	"errors"
	"math"
	"testing"
)

func interpApproxEqual(a, b float64) bool {
	const eps = 1e-9
	if math.IsNaN(a) && math.IsNaN(b) {
		return true
	}
	if math.IsInf(a, 0) || math.IsInf(b, 0) {
		return a == b
	}
	return math.Abs(a-b) <= eps
}

func TestInterp_Uncovered(t *testing.T) {
	// 1. Empty input
	t.Run("empty x", func(t *testing.T) {
		_, err := Interp(Float64Data{}, Float64Data{0, 1}, Float64Data{0, 1})
		if !errors.Is(err, ErrEmptyInput) {
			t.Fatalf("expected ErrEmptyInput, got %v", err)
		}
	})
	t.Run("empty xp", func(t *testing.T) {
		_, err := Interp(Float64Data{0}, Float64Data{}, Float64Data{})
		if !errors.Is(err, ErrEmptyInput) {
			t.Fatalf("expected ErrEmptyInput, got %v", err)
		}
	})

	// 2. Size mismatch
	t.Run("size mismatch", func(t *testing.T) {
		_, err := Interp(Float64Data{0}, Float64Data{0, 1}, Float64Data{0})
		if !errors.Is(err, ErrSize) {
			t.Fatalf("expected ErrSize, got %v", err)
		}
	})

	// 3. Bounds checks on xp
	t.Run("xp contains NaN", func(t *testing.T) {
		_, err := Interp(Float64Data{0}, Float64Data{math.NaN(), 1}, Float64Data{0, 1})
		if !errors.Is(err, ErrBounds) {
			t.Fatalf("expected ErrBounds for NaN in xp, got %v", err)
		}
	})
	t.Run("xp not strictly increasing", func(t *testing.T) {
		_, err := Interp(Float64Data{0}, Float64Data{0, 0}, Float64Data{0, 1})
		if !errors.Is(err, ErrBounds) {
			t.Fatalf("expected ErrBounds for non‑increasing xp, got %v", err)
		}
	})

	// 4. NaN in x propagates to output
	t.Run("NaN in x", func(t *testing.T) {
		out, err := Interp(Float64Data{math.NaN()}, Float64Data{0, 1}, Float64Data{0, 1})
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if len(out) != 1 || !math.IsNaN(out[0]) {
			t.Fatalf("expected NaN output, got %v", out)
		}
	})

	// 5. x below first xp
	t.Run("x below first xp", func(t *testing.T) {
		out, err := Interp(Float64Data{-5}, Float64Data{0, 10}, Float64Data{100, 200})
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if out[0] != 100 {
			t.Fatalf("expected first fp value 100, got %v", out[0])
		}
	})

	// 6. x above last xp
	t.Run("x above last xp", func(t *testing.T) {
		out, err := Interp(Float64Data{20}, Float64Data{0, 10}, Float64Data{100, 200})
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if out[0] != 200 {
			t.Fatalf("expected last fp value 200, got %v", out[0])
		}
	})

	// 7. Exact knot hit
	t.Run("exact knot", func(t *testing.T) {
		out, err := Interp(Float64Data{10}, Float64Data{0, 10, 20}, Float64Data{0, 100, 200})
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if out[0] != 100 {
			t.Fatalf("expected fp at knot 100, got %v", out[0])
		}
	})

	// 8. Normal interpolation (no overflow)
	t.Run("regular interpolation", func(t *testing.T) {
		out, err := Interp(Float64Data{5}, Float64Data{0, 10}, Float64Data{0, 20})
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if !interpApproxEqual(out[0], 10) {
			t.Fatalf("expected interpolated 10, got %v", out[0])
		}
	})

	// 9. Overflow spacing handling
	t.Run("overflow spacing", func(t *testing.T) {
		// xp difference overflows to +Inf
		xp := Float64Data{-1e308, 1e308}
		fp := Float64Data{0, 2}
		out, err := Interp(Float64Data{0}, xp, fp)
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if !interpApproxEqual(out[0], 1) {
			t.Fatalf("expected interpolated 1 with overflow handling, got %v", out[0])
		}
	})
}
