package stats

import (
	"math"
	"testing"
)

func interpApproxEqual(got, want float64) bool {
	const eps = 1e-12
	if math.IsNaN(got) && math.IsNaN(want) {
		return true
	}
	return math.Abs(got-want) <= eps
}

func TestInterp_EmptyInput(t *testing.T) {
	_, err := Interp(Float64Data{}, Float64Data{0, 1}, Float64Data{0, 1})
	if err != ErrEmptyInput {
		t.Fatalf("expected ErrEmptyInput, got %v", err)
	}
	_, err = Interp(Float64Data{0}, Float64Data{}, Float64Data{})
	if err != ErrEmptyInput {
		t.Fatalf("expected ErrEmptyInput for empty xp, got %v", err)
	}
}

func TestInterp_SizeMismatch(t *testing.T) {
	_, err := Interp(Float64Data{0}, Float64Data{0, 1}, Float64Data{0})
	if err != ErrSize {
		t.Fatalf("expected ErrSize, got %v", err)
	}
}

func TestInterp_NaNInXp(t *testing.T) {
	xp := Float64Data{math.NaN(), 1}
	fp := Float64Data{0, 1}
	_, err := Interp(Float64Data{0.5}, xp, fp)
	if err != ErrBounds {
		t.Fatalf("expected ErrBounds for NaN in xp, got %v", err)
	}
}

func TestInterp_NonIncreasingXp(t *testing.T) {
	xp := Float64Data{0, 0}
	fp := Float64Data{0, 1}
	_, err := Interp(Float64Data{0}, xp, fp)
	if err != ErrBounds {
		t.Fatalf("expected ErrBounds for non‑strict xp, got %v", err)
	}
}

func TestInterp_NaNInX(t *testing.T) {
	x := Float64Data{math.NaN(), 0.5}
	xp := Float64Data{0, 1}
	fp := Float64Data{0, 1}
	out, err := Interp(x, xp, fp)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !math.IsNaN(out[0]) {
		t.Errorf("expected NaN output for NaN input, got %v", out[0])
	}
	if !interpApproxEqual(out[1], 0.5) {
		t.Errorf("expected interpolated 0.5, got %v", out[1])
	}
}

func TestInterp_BoundaryValues(t *testing.T) {
	x := Float64Data{-1, 2}
	xp := Float64Data{0, 1}
	fp := Float64Data{10, 20}
	out, err := Interp(x, xp, fp)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !interpApproxEqual(out[0], 10) {
		t.Errorf("expected fp[0] for below range, got %v", out[0])
	}
	if !interpApproxEqual(out[1], 20) {
		t.Errorf("expected fp[last] for above range, got %v", out[1])
	}
}

func TestInterp_ExactKnot(t *testing.T) {
	x := Float64Data{0.5}
	xp := Float64Data{0, 0.5, 1}
	fp := Float64Data{0, 5, 10}
	out, err := Interp(x, xp, fp)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !interpApproxEqual(out[0], 5) {
		t.Errorf("expected exact fp at knot, got %v", out[0])
	}
}

func TestInterp_Interpolation(t *testing.T) {
	x := Float64Data{0.25}
	xp := Float64Data{0, 1}
	fp := Float64Data{0, 10}
	out, err := Interp(x, xp, fp)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	want := 2.5
	if !interpApproxEqual(out[0], want) {
		t.Errorf("expected %v, got %v", want, out[0])
	}
}

func TestInterp_OverflowDiff(t *testing.T) {
	xp := Float64Data{math.MaxFloat64, math.Inf(1)}
	fp := Float64Data{1, 2}
	x := Float64Data{math.MaxFloat64 * 0.9}
	out, err := Interp(x, xp, fp)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !interpApproxEqual(out[0], fp[0]) {
		t.Errorf("expected fp[0] due to overflow handling, got %v", out[0])
	}
}
