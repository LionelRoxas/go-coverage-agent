package stats

import (
	"errors"
	"math"
	"testing"
)

func ttestApproxEqual(a, b float64) bool {
	const eps = 1e-9
	if math.IsNaN(a) && math.IsNaN(b) {
		return true
	}
	if math.IsInf(a, 0) && math.IsInf(b, 0) && (math.Signbit(a) == math.Signbit(b)) {
		return true
	}
	return math.Abs(a-b) <= eps
}

func TestTTest_EmptyInput(t *testing.T) {
	_, _, err := TTest(Float64Data{}, nil, 0)
	if !errors.Is(err, ErrEmptyInput) {
		t.Fatalf("expected ErrEmptyInput, got %v", err)
	}
}

func TestTTest_OneSampleBounds(t *testing.T) {
	data := Float64Data{5}
	_, _, err := TTest(data, nil, 0)
	if !errors.Is(err, ErrBounds) {
		t.Fatalf("expected ErrBounds for n<2, got %v", err)
	}
}

func TestTTest_OneSampleZeroSDMatch(t *testing.T) {
	data := Float64Data{3, 3, 3}
	tstat, p, err := TTest(data, nil, 3)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if tstat != 0 {
		t.Errorf("expected t=0, got %v", tstat)
	}
	if p != 1.0 {
		t.Errorf("expected p=1.0, got %v", p)
	}
}

func TestTTest_OneSampleZeroSDMismatch(t *testing.T) {
	data := Float64Data{2, 2, 2}
	_, _, err := TTest(data, nil, 5)
	if !errors.Is(err, ErrBounds) {
		t.Fatalf("expected ErrBounds when sd=0 and mean!=popMean, got %v", err)
	}
}

func TestTTest_TwoSampleBounds(t *testing.T) {
	d1 := Float64Data{1}
	d2 := Float64Data{2}
	_, _, err := TTest(d1, d2, 0)
	if !errors.Is(err, ErrBounds) {
		t.Fatalf("expected ErrBounds for total n<3, got %v", err)
	}
}

func TestTTest_TwoSampleNormal(t *testing.T) {
	d1 := Float64Data{1, 2, 3}
	d2 := Float64Data{4, 5, 6}
	tstat, p, err := TTest(d1, d2, 0)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	// manual calculation
	mean1, _ := Mean(d1)
	mean2, _ := Mean(d2)
	var1, _ := SampleVariance(d1)
	var2, _ := SampleVariance(d2)
	n1, n2 := d1.Len(), d2.Len()
	df := float64(n1 + n2 - 2)
	pooledVar := (float64(n1-1)*var1 + float64(n2-1)*var2) / df
	se := math.Sqrt(pooledVar * (1.0/float64(n1) + 1.0/float64(n2)))
	expectedT := (mean1 - mean2) / se
	expectedP := 2 * tSf(math.Abs(expectedT), df)
	if !ttestApproxEqual(tstat, expectedT) {
		t.Errorf("t statistic mismatch: got %v want %v", tstat, expectedT)
	}
	if !ttestApproxEqual(p, expectedP) {
		t.Errorf("p-value mismatch: got %v want %v", p, expectedP)
	}
	if p < 0 || p > 1 {
		t.Errorf("p-value out of range [0,1]: %v", p)
	}
}

func TestRegIncBeta_EdgeCases(t *testing.T) {
	if v := regIncBeta(2, 3, 0); v != 0 {
		t.Errorf("regIncBeta with x=0 expected 0, got %v", v)
	}
	if v := regIncBeta(2, 3, 1); v != 1 {
		t.Errorf("regIncBeta with x=1 expected 1, got %v", v)
	}
}

func TestRegIncBeta_NormalCase(t *testing.T) {
	// I_0.5(2,3) = 11/16 = 0.6875
	got := regIncBeta(2, 3, 0.5)
	want := 0.6875
	if math.Abs(got-want) > 1e-9 {
		t.Errorf("regIncBeta(2,3,0.5) = %v, want %v", got, want)
	}
}

func TestLgammaBeta_Consistency(t *testing.T) {
	a, b := 2.5, 4.1
	got := lgammaBeta(a, b)
	la, _ := math.Lgamma(a)
	lb, _ := math.Lgamma(b)
	lab, _ := math.Lgamma(a + b)
	want := la + lb - lab
	if math.Abs(got-want) > 1e-12 {
		t.Errorf("lgammaBeta mismatch: got %v want %v", got, want)
	}
}

func TestClampTiny_Edge(t *testing.T) {
	if v := clampTiny(1e-31); v != 1e-30 {
		t.Errorf("clampTiny near zero expected 1e-30, got %v", v)
	}
	if v := clampTiny(-1e-31); v != 1e-30 {
		t.Errorf("clampTiny negative near zero expected 1e-30, got %v", v)
	}
}

func TestClampTiny_Normal(t *testing.T) {
	val := 0.123
	if v := clampTiny(val); v != val {
		t.Errorf("clampTiny unchanged value expected %v, got %v", val, v)
	}
}

func TestTSf_TZero(t *testing.T) {
	df := 10.0
	got := tSf(0, df)
	if math.Abs(got-0.5) > 1e-12 {
		t.Errorf("tSf(0, %v) = %v, want 0.5", df, got)
	}
}
