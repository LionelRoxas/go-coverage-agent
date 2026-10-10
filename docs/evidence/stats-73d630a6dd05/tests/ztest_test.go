package stats

import (
	"errors"
	"math"
	"testing"
)

func TestZTest_EmptyInput(t *testing.T) {
	var data Float64Data
	z, p, err := ZTest(data, nil, 0, 1)
	if !errors.Is(err, ErrEmptyInput) {
		t.Fatalf("expected ErrEmptyInput, got %v", err)
	}
	if !math.IsNaN(z) || !math.IsNaN(p) {
		t.Fatalf("expected NaN results for empty input, got z=%v p=%v", z, p)
	}
}

func TestZTest_OneSample_BadStdDev(t *testing.T) {
	data := Float64Data{1, 2, 3}
	_, _, err := ZTest(data, nil, 2, 0) // non‑positive stddev
	if !errors.Is(err, ErrBounds) {
		t.Fatalf("expected ErrBounds for non‑positive stddev, got %v", err)
	}
}

func TestZTest_OneSample(t *testing.T) {
	data := Float64Data{2, 4, 6, 8}
	popMean := 5.0
	popStdDev := 2.0
	// expected values using the same formula as ZTest
	mean, _ := Mean(data)
	n := float64(data.Len())
	se := popStdDev / math.Sqrt(n)
	wantZ := (mean - popMean) / se
	wantP := 2 * NormSf(math.Abs(wantZ), 0, 1)

	gotZ, gotP, err := ZTest(data, nil, popMean, popStdDev)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if math.Abs(gotZ-wantZ) > 1e-9 {
		t.Fatalf("z mismatch: got %v want %v", gotZ, wantZ)
	}
	if math.Abs(gotP-wantP) > 1e-9 {
		t.Fatalf("pvalue mismatch: got %v want %v", gotP, wantP)
	}
}

func TestZTest_TwoSample_BadStdDev(t *testing.T) {
	d1 := Float64Data{1, 2, 3}
	d2 := Float64Data{4, 5, 6}
	_, _, err := ZTest(d1, d2, 0, -1) // non‑positive stddev
	if !errors.Is(err, ErrBounds) {
		t.Fatalf("expected ErrBounds for non‑positive stddev in two‑sample, got %v", err)
	}
}

func TestZTest_TwoSample(t *testing.T) {
	d1 := Float64Data{1, 2, 3, 4}
	d2 := Float64Data{2, 3, 4, 5}
	popStdDev := 1.5

	mean1, _ := Mean(d1)
	mean2, _ := Mean(d2)
	n1 := float64(d1.Len())
	n2 := float64(d2.Len())
	se := popStdDev * math.Sqrt(1.0/n1+1.0/n2)
	wantZ := (mean1 - mean2) / se
	wantP := 2 * NormSf(math.Abs(wantZ), 0, 1)

	gotZ, gotP, err := ZTest(d1, d2, 0, popStdDev)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if math.Abs(gotZ-wantZ) > 1e-9 {
		t.Fatalf("z mismatch: got %v want %v", gotZ, wantZ)
	}
	if math.Abs(gotP-wantP) > 1e-9 {
		t.Fatalf("pvalue mismatch: got %v want %v", gotP, wantP)
	}
}
