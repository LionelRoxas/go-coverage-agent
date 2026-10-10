package stats

import (
	"errors"
	"math"
	"testing"
)

func ztestApproxEqual(t *testing.T, got, want, tol float64) {
	if math.IsNaN(want) {
		if !math.IsNaN(got) {
			t.Errorf("expected NaN, got %v", got)
		}
		return
	}
	if math.IsInf(want, 0) {
		if !math.IsInf(got, 0) || (want > 0) != (got > 0) {
			t.Errorf("expected %v Inf, got %v", want, got)
		}
		return
	}
	if diff := math.Abs(got - want); diff > tol {
		t.Errorf("values differ: got %v, want %v (diff %v > %v)", got, want, diff, tol)
	}
}

func TestZTest_EmptyInput(t *testing.T) {
	var data Float64Data
	z, p, err := ZTest(data, nil, 0, 1)
	if !errors.Is(err, ErrEmptyInput) {
		t.Fatalf("expected ErrEmptyInput, got %v", err)
	}
	if !math.IsNaN(z) || !math.IsNaN(p) {
		t.Errorf("expected NaN results, got z=%v p=%v", z, p)
	}
}

func TestZTest_TwoSample_BoundsError(t *testing.T) {
	data1 := Float64Data{1, 2, 3}
	data2 := Float64Data{4, 5, 6}
	_, _, err := ZTest(data1, data2, 0, 0) // populationStdDev <= 0
	if !errors.Is(err, ErrBounds) {
		t.Fatalf("expected ErrBounds, got %v", err)
	}
}

func TestZTest_OneSample_BoundsError(t *testing.T) {
	data1 := Float64Data{1, 2, 3}
	_, _, err := ZTest(data1, nil, 0, -1) // populationStdDev <= 0
	if !errors.Is(err, ErrBounds) {
		t.Fatalf("expected ErrBounds, got %v", err)
	}
}

func TestZTest_TwoSample_Normal(t *testing.T) {
	data1 := Float64Data{1, 2, 3}
	data2 := Float64Data{4, 5, 6}
	popStd := 2.0
	z, p, err := ZTest(data1, data2, 0, popStd)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	// Expected calculations
	mean1 := 2.0
	mean2 := 5.0
	n1 := float64(len(data1))
	n2 := float64(len(data2))
	se := popStd * math.Sqrt(1.0/n1+1.0/n2)
	wantZ := (mean1 - mean2) / se
	wantP := 2 * NormSf(math.Abs(wantZ), 0, 1)
	ztestApproxEqual(t, z, wantZ, 1e-9)
	ztestApproxEqual(t, p, wantP, 1e-9)
}

func TestZTest_OneSample_Normal(t *testing.T) {
	data1 := Float64Data{2, 4, 6}
	popMean := 5.0
	popStd := 3.0
	z, p, err := ZTest(data1, nil, popMean, popStd)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	mean1 := 4.0
	n1 := float64(len(data1))
	se := popStd / math.Sqrt(n1)
	wantZ := (mean1 - popMean) / se
	wantP := 2 * NormSf(math.Abs(wantZ), 0, 1)
	ztestApproxEqual(t, z, wantZ, 1e-9)
	ztestApproxEqual(t, p, wantP, 1e-9)
}
