package stats

import (
	"errors"
	"math"
	"testing"
)

func ttestApproxEqual(got, want, tol float64) bool {
	if math.IsNaN(got) && math.IsNaN(want) {
		return true
	}
	if math.IsInf(got, 0) && math.IsInf(want, 0) {
		return math.Signbit(got) == math.Signbit(want)
	}
	return math.Abs(got-want) <= tol
}

func TestTTest(t *testing.T) {
	cases := []struct {
		name         string
		data1, data2 Float64Data
		popMean      float64
		wantErr      error
		wantTNaN     bool
		wantPNaN     bool
		wantTZero    bool
		wantPOne     bool
	}{
		{
			name:     "empty input",
			data1:    Float64Data{},
			data2:    nil,
			popMean:  0,
			wantErr:  ErrEmptyInput,
			wantTNaN: true,
			wantPNaN: true,
		},
		{
			name:     "one-sample single element bounds",
			data1:    Float64Data{5},
			data2:    nil,
			popMean:  5,
			wantErr:  ErrBounds,
			wantTNaN: true,
			wantPNaN: true,
		},
		{
			name:      "one-sample zero variance equal mean",
			data1:     Float64Data{3, 3, 3},
			data2:     nil,
			popMean:   3,
			wantErr:   nil,
			wantTZero: true,
			wantPOne:  true,
		},
		{
			name:     "one-sample zero variance different mean",
			data1:    Float64Data{2, 2, 2},
			data2:    nil,
			popMean:  5,
			wantErr:  ErrBounds,
			wantTNaN: true,
			wantPNaN: true,
		},
		{
			name:     "two-sample insufficient total size",
			data1:    Float64Data{1},
			data2:    Float64Data{2},
			popMean:  0,
			wantErr:  ErrBounds,
			wantTNaN: true,
			wantPNaN: true,
		},
		{
			name:      "two-sample equal means",
			data1:     Float64Data{1, 2, 3},
			data2:     Float64Data{1, 2, 3},
			popMean:   0,
			wantErr:   nil,
			wantTZero: true,
			wantPOne:  true,
		},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			tStat, pVal, err := TTest(tc.data1, tc.data2, tc.popMean)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if tc.wantErr != nil {
				// when error expected, t and p should be NaN
				if !math.IsNaN(tStat) || !math.IsNaN(pVal) {
					t.Fatalf("expected NaN results on error, got t=%v p=%v", tStat, pVal)
				}
				return
			}
			if tc.wantTNaN && !math.IsNaN(tStat) {
				t.Fatalf("expected t to be NaN, got %v", tStat)
			}
			if tc.wantPNaN && !math.IsNaN(pVal) {
				t.Fatalf("expected p to be NaN, got %v", pVal)
			}
			if tc.wantTZero && math.Abs(tStat) > 1e-12 {
				t.Fatalf("expected t approx 0, got %v", tStat)
			}
			if tc.wantPOne && math.Abs(pVal-1.0) > 1e-12 {
				t.Fatalf("expected p approx 1, got %v", pVal)
			}
		})
	}
}

func TestRegIncBeta_EdgeCases(t *testing.T) {
	// x == 0
	if got := regIncBeta(2, 3, 0); got != 0 {
		t.Fatalf("regIncBeta with x=0 expected 0, got %v", got)
	}
	// x == 1
	if got := regIncBeta(2, 3, 1); got != 1 {
		t.Fatalf("regIncBeta with x=1 expected 1, got %v", got)
	}
	// typical value, result should be within [0,1]
	val := regIncBeta(2, 3, 0.5)
	if val < 0 || val > 1 {
		t.Fatalf("regIncBeta returned out of range value %v", val)
	}
}

func TestLgammaBeta(t *testing.T) {
	a, b := 2.5, 4.0
	got := lgammaBeta(a, b)
	la, _ := math.Lgamma(a)
	lb, _ := math.Lgamma(b)
	lab, _ := math.Lgamma(a + b)
	want := la + lb - lab
	if !ttestApproxEqual(got, want, 1e-12) {
		t.Fatalf("lgammaBeta mismatch: got %v want %v", got, want)
	}
}

func TestClampTiny(t *testing.T) {
	// value near zero
	if got := clampTiny(1e-40); got != 1e-30 {
		t.Fatalf("clampTiny near zero expected 1e-30, got %v", got)
	}
	// normal value unchanged
	v := 0.123
	if got := clampTiny(v); got != v {
		t.Fatalf("clampTiny normal value changed: got %v want %v", got, v)
	}
}

func TestTSf(t *testing.T) {
	// t = 0 should give survival = 0.5 for any df > 0
	df := 10.0
	if got := tSf(0, df); math.Abs(got-0.5) > 1e-12 {
		t.Fatalf("tSf(0, %v) expected 0.5, got %v", df, got)
	}
	// result should be between 0 and 1 for typical inputs
	val := tSf(1.2, 5)
	if val < 0 || val > 1 {
		t.Fatalf("tSf returned out of range value %v", val)
	}
}

func TestTTest_OneSample_Uncovered(t *testing.T) {
	cases := []struct {
		name    string
		data    Float64Data
		popMean float64
		wantT   float64
		wantP   float64
		wantErr error
	}{
		{
			name:    "nonZeroVariance",
			data:    Float64Data{1, 2, 3, 4, 5},
			popMean: 0,
			wantT:   0, // placeholder, computed in test
			wantP:   0,
			wantErr: nil,
		},
		{
			name:    "zeroVarianceMatch",
			data:    Float64Data{5, 5, 5},
			popMean: 5,
			wantT:   0,
			wantP:   1,
			wantErr: nil,
		},
		{
			name:    "zeroVarianceMismatch",
			data:    Float64Data{5, 5, 5},
			popMean: 4,
			wantT:   math.NaN(),
			wantP:   math.NaN(),
			wantErr: ErrBounds,
		},
	}

	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			gotT, gotP, err := TTest(tc.data, nil, tc.popMean)
			if tc.wantErr != nil {
				if err == nil || !errors.Is(err, tc.wantErr) {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error %v", err)
			}

			if tc.name == "nonZeroVariance" {
				mean, _ := Mean(tc.data)
				sd, _ := StandardDeviationSample(tc.data)
				se := sd / math.Sqrt(float64(tc.data.Len()))
				expectedT := (mean - tc.popMean) / se
				df := float64(tc.data.Len() - 1)
				expectedP := 2 * tSf(math.Abs(expectedT), df)

				if !ttestApproxEqual(gotT, expectedT, 1e-9) {
					t.Fatalf("t mismatch: got %v want %v", gotT, expectedT)
				}
				if !ttestApproxEqual(gotP, expectedP, 1e-9) {
					t.Fatalf("pvalue mismatch: got %v want %v", gotP, expectedP)
				}
			} else {
				if !ttestApproxEqual(gotT, tc.wantT, 1e-9) {
					t.Fatalf("t mismatch: got %v want %v", gotT, tc.wantT)
				}
				if !ttestApproxEqual(gotP, tc.wantP, 1e-9) {
					t.Fatalf("pvalue mismatch: got %v want %v", gotP, tc.wantP)
				}
			}
		})
	}
}
