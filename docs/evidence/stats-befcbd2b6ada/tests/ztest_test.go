package stats

import (
	"errors"
	"math"
	"testing"
)

func ztestFloatEqual(a, b float64) bool {
	const eps = 1e-9
	if math.IsNaN(a) && math.IsNaN(b) {
		return true
	}
	if math.IsInf(a, 0) || math.IsInf(b, 0) {
		return a == b
	}
	return math.Abs(a-b) <= eps
}

func TestZTest_EmptyInput(t *testing.T) {
	var empty Float64Data
	_, _, err := ZTest(empty, nil, 0, 1)
	if !errors.Is(err, ErrEmptyInput) {
		t.Fatalf("expected ErrEmptyInput, got %v", err)
	}
}

func TestZTest_TwoSample_ErrorBounds(t *testing.T) {
	d1 := Float64Data{1, 2, 3}
	d2 := Float64Data{4, 5, 6}
	_, _, err := ZTest(d1, d2, 0, 0) // populationStdDev <= 0
	if !errors.Is(err, ErrBounds) {
		t.Fatalf("expected ErrBounds for non‑positive stddev, got %v", err)
	}
}

func TestZTest_OneSample_ErrorBounds(t *testing.T) {
	d1 := Float64Data{1, 2, 3}
	_, _, err := ZTest(d1, nil, 0, -1) // populationStdDev <= 0
	if !errors.Is(err, ErrBounds) {
		t.Fatalf("expected ErrBounds for non‑positive stddev, got %v", err)
	}
}

func TestZTest_TwoSample_Basic(t *testing.T) {
	// identical data sets => equal means => Z should be 0, pvalue ≈ 1
	d1 := Float64Data{1, 2, 3}
	d2 := Float64Data{1, 2, 3}
	z, p, err := ZTest(d1, d2, 0, 1)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !ztestFloatEqual(z, 0) {
		t.Errorf("expected Z≈0, got %v", z)
	}
	expectedP := 2 * NormSf(math.Abs(z), 0, 1)
	if !ztestFloatEqual(p, expectedP) {
		t.Errorf("pvalue mismatch: got %v, want %v", p, expectedP)
	}
	if !ztestFloatEqual(p, 1) {
		t.Errorf("expected pvalue≈1 for zero Z, got %v", p)
	}
}

func TestZTest_OneSample_Basic(t *testing.T) {
	// mean equals populationMean => Z=0, pvalue≈1
	d1 := Float64Data{2, 2, 2}
	popMean := 2.0
	popStd := 1.0
	z, p, err := ZTest(d1, nil, popMean, popStd)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !ztestFloatEqual(z, 0) {
		t.Errorf("expected Z≈0, got %v", z)
	}
	expectedP := 2 * NormSf(math.Abs(z), 0, 1)
	if !ztestFloatEqual(p, expectedP) {
		t.Errorf("pvalue mismatch: got %v, want %v", p, expectedP)
	}
	if !ztestFloatEqual(p, 1) {
		t.Errorf("expected pvalue≈1 for zero Z, got %v", p)
	}
}
